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
db = mongo_client.get_database("chatbot_db")
chat_history_collection = db.get_collection("conversations")
print("✅ Successfully connected to MongoDB Atlas.")

print("Loading model embedding (this may take a while)...")
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
print("✅ The embedding model (‘all-MiniLM-L6-v2’) has been successfully loaded.")

try:
    chroma_client = HttpClient(host='localhost', port=8000)
    knowledge_collection = chroma_client.get_collection(
        name="website_knowledge"
    )
    print("✅ Successfully connected to ChromaDB (localhost:8000).")
except Exception as e:
    print(f"❌ Failed to connect to ChromaDB. Make sure the chroma run... server is running. Error: {e}")

# --- 3. Endpoint Frontend ---
# @app.route("/")
# def home():
#     return render_template("chat.html")

@app.route("/")
def home():
    """Display the landing page (index.html)"""
    return render_template("index.html")

@app.route("/chat")
def chat_page():
    """Display the main chat page (chat.html)"""
    return render_template("chat.html")

# --- 4. Endpoint API - Take ALL History (untuk F5) ---
@app.route("/api/conversations", methods=["GET"])
def get_conversations():
    user_id = request.args.get("userId")
    if not user_id:
        return jsonify({"error": "userId is required"}), 400
    
    try:
        convos = list(chat_history_collection.find(
            {"userId": user_id}
        ).sort("updatedAt", -1))
        
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
        print(f"Error di /api/conversations GET: {e}")
        return jsonify({"error": "Failed to retrieve conversation"}), 500

# --- 5. NEW API ENDPOINT (FOR “CLEAR ALL”) ---
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
        # Delete all documents in MongoDB that match the userId
        result = chat_history_collection.delete_many({"userId": user_id})
        
        print(f"Successfully deleted {result.deleted_count} conversation for userId {user_id}.")
        return jsonify({
            "message": "History successfully deleted", 
            "deleted_count": result.deleted_count
        })

    except Exception as e:
        print(f"Error di /api/conversations DELETE: {e}")
        return jsonify({"error": "Failed to delete history"}), 500

# --- 6. Endpoint API Chat (Main) ---
@app.route("/api/chat", methods = ["POST"])
def handle_chat():
    try:
        data = request.json
        user_message = data.get("message")
        user_id = data.get("userId")
        conversation_id = data.get("conversationId") # Active chat ID, can be null

        if not user_message or not user_id:
            return jsonify({"error": "The 'message' dan 'userId' parameters are required."}), 400
        
        history = []
        user_message_doc = {"role": "user", "content": user_message, "timestamp": datetime.now()}

        # --- 1. (CRUD) Retrieve/Create Conversation ---
        if conversation_id:
            # This is an existing chat
            current_convo = chat_history_collection.find_one({
                "_id": ObjectId(conversation_id),
                "userId": user_id
            })
            if current_convo:
                history = current_convo.get("messages", [])[-6:]
        
        # --- 2. (RAG) - Perform RAG (Same as before) ---
        print(f"Searching for context for: \"{user_message}\"")
        query_embedding = embedding_model.encode(user_message).tolist()
        results = knowledge_collection.query(
            query_embeddings=[query_embedding],
            n_results=1 
        )
        context = "\n\n".join(results['documents'][0])
        print("Konteks ditemukan.")
        
        # --- 3. (RAG) For prompt ---
        system_prompt = """You are a precise assistant. Answer *strictly* and *only* based on the context provided. 
                        Do not add any information, pollutants, or applications that are not *explicitly* mentioned in the text. 
                        If the context provides conflicting information (like for different products), only use the information from the *single most relevant* chunk."""
        formatted_history = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history])
        user_prompt = f"Context:\n{context}\n\nChat History:\n{formatted_history}\n\nQuestion:\n{user_message}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # --- 4. (RAG) Call the Llama 3 API ---
        print("Calling Hugging Face API...")
        response = hf_client.chat_completion(messages=messages, max_tokens=250, temperature=0.1)
        ai_response = response.choices[0].message.content
        
        # --- 5. (CRUD) Save the AI response to MongoDB ---
        ai_message_doc = {"role": "assistant", "content": ai_response, "timestamp": datetime.now()}
        
        if conversation_id: # Existing chat
            chat_history_collection.update_one(
                {"_id": ObjectId(conversation_id)},
                {
                    "$push": {"messages": {"$each": [user_message_doc, ai_message_doc]}},
                    "$set": {"updatedAt": datetime.now()}
                }
            )
        else: # New chat
            title = user_message[:30] + "..." if len(user_message) > 30 else user_message
            new_convo_doc = {
                "userId": user_id,
                "title": title,
                "messages": [user_message_doc, ai_message_doc], # Directly append user & AI
                "createdAt": datetime.now(),
                "updatedAt": datetime.now()
            }
            insert_result = chat_history_collection.insert_one(new_convo_doc)
            conversation_id = insert_result.inserted_id # Get the new _id
            
        print("Conversation successfully saved to MongoDB.")

        # --- 6. Send the response ---
        return jsonify({"answer": ai_response, "conversationId": str(conversation_id)})

    except Exception as e:
        print(f"Error di /api/chat: {e}")
        return jsonify({"error": "Server error occurred"}), 500

# --- 7. Run the Server ---
if __name__ == "__main__":
    app.run(port=5000, debug=True)