import os
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import PyMongoError
from chromadb import HttpClient
from sentence_transformers import SentenceTransformer
from huggingface_hub import InferenceClient
from dotenv import load_dotenv
from bson.objectid import ObjectId
from datetime import datetime

# --- 1. Load .env and Initialize ---
load_dotenv()
app = Flask(__name__)
CORS(app) 

# --- 2. Client Initialization (Global) ---
hf_token = os.getenv("HF_TOKEN")
hf_client = InferenceClient(
    "meta-llama/Meta-Llama-3-8B-Instruct",
    token=hf_token
)

mongo_url = os.getenv("MONGO_URL")
mongo_client = MongoClient(mongo_url)
db = mongo_client.get_database("chatbot_db") # Get DB from MONGO_URL
chat_history_collection = db.get_collection("conversations")
print("✅ Successfully connected to MongoDB Atlas.")

print("Loading embedding model (this may take a while)...")
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
print("✅ Embedding model ('all-MiniLM-L6-v2') has been successfully loaded.")

try:
    chroma_client = HttpClient(host='localhost', port=8000)
    knowledge_collection = chroma_client.get_collection(
        name="website_knowledge"
    )
    print("✅ Successfully connected to ChromaDB (localhost:8000).")
except Exception as e:
    print(f"❌ FAILED to connect to ChromaDB. Make sure the 'chroma run...' server is running. Error: {e}")

# --- 3. Frontend Endpoints ---
@app.route("/")
def home():
    """Display the landing page (index.html)"""
    return render_template("index.html")

@app.route("/chat")
def chat_page():
    """Display the main chat page (chat.html)"""
    return render_template("chat.html")

# --- 4. API Endpoint - Get All History (for F5 refresh) ---
@app.route("/api/conversations", methods=["GET"])
def get_conversations():
    user_id = request.args.get("userId")
    if not user_id:
        return jsonify({"error": "userId is required"}), 400
    
    try:
        convos = list(chat_history_collection.find(
            {"userId": user_id}
        ).sort("updatedAt", -1)) # Sort by most recent
        
        conversations_list = []
        for convo in convos:
            conversations_list.append({
                "id": str(convo.get('_id')),
                "title": convo.get("title", "New Chat"),
                "messages": convo.get("messages", []),
                "createdAt": convo.get("createdAt")
            })
        return jsonify(conversations_list)
    except Exception as e:
        print(f"Error in /api/conversations GET: {e}")
        return jsonify({"error": "Failed to retrieve conversations"}), 500

# --- 5. API Endpoint (FOR “CLEAR ALL”) ---
@app.route("/api/conversations", methods=["DELETE"])
def clear_conversations():
    """
    Delete ALL conversations for one user ID.
    """
    data = request.json
    user_id = data.get("userId")
    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    try:
        result = chat_history_collection.delete_many({"userId": user_id})
        print(f"Successfully deleted {result.deleted_count} conversations for userId {user_id}.")
        return jsonify({
            "message": "History successfully deleted", 
            "deleted_count": result.deleted_count
        })
    except Exception as e:
        print(f"Error in /api/conversations DELETE: {e}")
        return jsonify({"error": "Failed to delete history"}), 500

# --- 6. Main Chat API Endpoint ---
@app.route("/api/chat", methods = ["POST"])
def handle_chat():
    try:
        data = request.json
        user_message = data.get("message")
        user_id = data.get("userId")
        conversation_id = data.get("conversationId") # Can be 'null', 'temp-...', or a real ObjectId

        if not user_message or not user_id:
            return jsonify({"error": "'message' and 'userId' parameters are required."}), 400
        
        history = []
        user_message_doc = {"role": "user", "content": user_message, "timestamp": datetime.now()}
        real_convo_id_obj = None # Will hold the valid Mongo ObjectId

        # --- 1. (CRUD) Validate ID and Get Conversation ---
        if conversation_id:
            try:
                # Try to convert. If successful, it's a real ID.
                real_convo_id_obj = ObjectId(conversation_id)
            except Exception as e: # bson.errors.InvalidId
                # If it Fails (it's 'temp-...' or invalid), treat it as a new chat.
                real_convo_id_obj = None 
            
        if real_convo_id_obj:
            # This is an EXISTING CHAT (valid ID)
            current_convo = chat_history_collection.find_one({
                "_id": real_convo_id_obj,
                "userId": user_id
            })
            if current_convo:
                history = current_convo.get("messages", [])[-6:]
        # If real_convo_id_obj is None, history remains [] (empty)
        
        # --- 2. (RAG) - Perform RAG ---
        print(f"Searching for context for: \"{user_message}\"")
        query_embedding = embedding_model.encode(user_message).tolist()
        results = knowledge_collection.query(
            query_embeddings=[query_embedding],
            n_results=5 
        )
        context = "\n\n".join(results['documents'][0])
        print("Context found.")
        
        # --- 3. (RAG) Build Prompt (Using new instructions) ---
        system_prompt = """You are the 'Enviro Education Tools Product Selector & System Designer'. Your answers are for technical professionals who use American English.

Your task is to answer the user's question *strictly* and *only* based on the context provided. The context provided IS the information from https://enviroeducationtools.com/.
- Do not use any products, information, or technologies from other websites.
- Do not mention any other websites.
- Do not suggest prices or pricing information.

If the user asks 'about Enviro Education Tools' or 'where are you based', use the following information:
'Enviro Education Tools, based in Atlanta, Georgia, United States, is recognized as one of the leading global suppliers of advanced B2B and B2G (to a lesser degree, B2B2C, B2D) technologies in the world. For four decades,  Enviro Education Tools has served its customers in the U.S. and Canada, including many Fortune 500 companies, leading R&D firms, prestigious universities, and U.S. and Canadian government agencies. Asset Track Pro has invested heavily in R&D of its products and systems, has stringent quality assurance processes, and provides top-notch expert support remotely or onsite.'

If the answer is not in the context, say: 'I'm sorry, I do not have specific information on that topic from https://enviroeducationtools.com/'
"""
        formatted_history = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history])
        user_prompt = f"Context:\n{context}\n\nChat History:\n{formatted_history}\n\nQuestion:\n{user_message}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # --- 4. (RAG) Call Llama 3 API ---
        print("Calling Hugging Face API...")
        response = hf_client.chat_completion(messages=messages, max_tokens=250, temperature=0.1)
        ai_response = response.choices[0].message.content
        
        # --- 4.5. Add Mandatory Disclaimer ---
        disclaimer = "\n\nThe above is suggested by Enviro Education Tools AI and may not be as good as what our human experts can provide. Please contact our experts for further."
        ai_response += disclaimer # Append disclaimer to AI response
        
        # --- 5. (CRUD) Save AI response to MongoDB ---
        ai_message_doc = {"role": "assistant", "content": ai_response, "timestamp": datetime.now()}
        
        final_convo_id_str = ""
        
        if real_convo_id_obj: # Existing chat (ID was valid)
            chat_history_collection.update_one(
                {"_id": real_convo_id_obj},
                {
                    "$push": {"messages": {"$each": [user_message_doc, ai_message_doc]}},
                    "$set": {"updatedAt": datetime.now()}
                }
            )
            final_convo_id_str = str(real_convo_id_obj)
            
        else: # New chat (ID was 'null' or 'temp-...')
            title = user_message[:30] + "..." if len(user_message) > 30 else user_message
            new_convo_doc = {
                "userId": user_id,
                "title": title,
                "messages": [user_message_doc, ai_message_doc], # Add user & AI messages
                "createdAt": datetime.now(),
                "updatedAt": datetime.now()
            }
            insert_result = chat_history_collection.insert_one(new_convo_doc)
            final_convo_id_str = str(insert_result.inserted_id) # Get the NEW _id
            
        print("Conversation saved to MongoDB.")

        # --- 6. Send response ---
        return jsonify({"answer": ai_response, "conversationId": final_convo_id_str})

    except Exception as e:
        print(f"Error in /api/chat: {e}")
        return jsonify({"error": "An error occurred on the server"}), 500

# --- 7. Run the Server ---
if __name__ == "__main__":
    app.run(port=5000, debug=True)