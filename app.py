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

# --- 1. Muat .env dan Inisialisasi ---
load_dotenv()
app = Flask(__name__)
CORS(app) 

# --- 2. Inisialisasi Klien (Global) ---
hf_token = os.getenv("HF_TOKEN")
hf_client = InferenceClient(
    "meta-llama/Meta-Llama-3-8B-Instruct",
    token=hf_token
)

mongo_url = os.getenv("MONGO_URL")
mongo_client = MongoClient(mongo_url)
db = mongo_client.get_database("chatbot_db")
chat_history_collection = db.get_collection("conversations")
print("✅ Berhasil terkoneksi ke MongoDB Atlas.")

print("Memuat model embedding (ini mungkin butuh waktu)...")
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
print("✅ Model embedding ('all-MiniLM-L6-v2') berhasil dimuat.")

try:
    chroma_client = HttpClient(host='localhost', port=8000)
    knowledge_collection = chroma_client.get_collection(
        name="website_knowledge"
    )
    print("✅ Berhasil terkoneksi ke ChromaDB (localhost:8000).")
except Exception as e:
    print(f"❌ GAGAL terhubung ke ChromaDB. Pastikan server chroma run... berjalan. Error: {e}")

# --- 3. Endpoint Frontend ---
@app.route("/")
def home():
    return render_template("chat.html")

# --- 4. Endpoint API - Ambil SEMUA History (untuk F5) ---
@app.route("/api/conversations", methods=["GET"])
def get_conversations():
    user_id = request.args.get("userId")
    if not user_id:
        return jsonify({"error": "userId dibutuhkan"}), 400
    
    try:
        convos = list(chat_history_collection.find(
            {"userId": user_id}
        ).sort("updatedAt", -1))
        
        conversations_list = []
        for convo in convos:
            conversations_list.append({
                "id": str(convo.get('_id')),
                "title": convo.get("title", "Obrolan Baru"),
                "messages": convo.get("messages", []),
                "createdAt": convo.get("createdAt")
            })
        return jsonify(conversations_list)
    except Exception as e:
        print(f"Error di /api/conversations GET: {e}")
        return jsonify({"error": "Gagal mengambil percakapan"}), 500

# --- 5. ENDPOINT API BARU (UNTUK "CLEAR ALL") ---
@app.route("/api/conversations", methods=["DELETE"])
def clear_conversations():
    """
    Menghapus SEMUA percakapan untuk satu userId.
    """
    data = request.json
    user_id = data.get("userId")
    if not user_id:
        return jsonify({"error": "userId dibutuhkan"}), 400

    try:
        # Hapus semua dokumen di MongoDB yang cocok dengan userId
        result = chat_history_collection.delete_many({"userId": user_id})
        
        print(f"Berhasil menghapus {result.deleted_count} percakapan untuk userId {user_id}.")
        return jsonify({
            "message": "History berhasil dihapus", 
            "deleted_count": result.deleted_count
        })

    except Exception as e:
        print(f"Error di /api/conversations DELETE: {e}")
        return jsonify({"error": "Gagal menghapus history"}), 500

# --- 6. Endpoint API Chat (Utama) ---
@app.route("/api/chat", methods = ["POST"])
def handle_chat():
    try:
        data = request.json
        user_message = data.get("message")
        user_id = data.get("userId")
        conversation_id = data.get("conversationId") # ID chat yang aktif, bisa null

        if not user_message or not user_id:
            return jsonify({"error": "Parameter 'message' dan 'userId' dibutuhkan."}), 400
        
        history = []
        user_message_doc = {"role": "user", "content": user_message, "timestamp": datetime.now()}

        # --- 1. (CRUD) Ambil/Buat Percakapan ---
        if conversation_id:
            # Ini adalah obrolan yang sudah ada
            current_convo = chat_history_collection.find_one({
                "_id": ObjectId(conversation_id),
                "userId": user_id
            })
            if current_convo:
                history = current_convo.get("messages", [])[-6:]
        
        # --- 2. (RAG) - Lakukan RAG (Sama seperti sebelumnya) ---
        print(f"Mencari konteks untuk: \"{user_message}\"")
        query_embedding = embedding_model.encode(user_message).tolist()
        results = knowledge_collection.query(
            query_embeddings=[query_embedding],
            n_results=1 # <-- Anda bisa ganti ini ke 1 nanti
        )
        context = "\n\n".join(results['documents'][0])
        print("Konteks ditemukan.")
        
        # --- 3. (RAG) Buat prompt ---
        # <-- Anda bisa perketat prompt ini nanti
        system_prompt = """You are a precise assistant. Answer *strictly* and *only* based on the context provided. 
                        Do not add any information, pollutants, or applications that are not *explicitly* mentioned in the text. 
                        If the context provides conflicting information (like for different products), only use the information from the *single most relevant* chunk."""
        formatted_history = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history])
        user_prompt = f"Context:\n{context}\n\nChat History:\n{formatted_history}\n\nQuestion:\n{user_message}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # --- 4. (RAG) Panggil API Llama 3 ---
        print("Memanggil Hugging Face API...")
        response = hf_client.chat_completion(messages=messages, max_tokens=250, temperature=0.1)
        ai_response = response.choices[0].message.content
        
        # --- 5. (CRUD) Simpan balasan AI ke MongoDB ---
        ai_message_doc = {"role": "assistant", "content": ai_response, "timestamp": datetime.now()}
        
        if conversation_id: # Obrolan lama
            chat_history_collection.update_one(
                {"_id": ObjectId(conversation_id)},
                {
                    "$push": {"messages": {"$each": [user_message_doc, ai_message_doc]}},
                    "$set": {"updatedAt": datetime.now()}
                }
            )
        else: # Obrolan baru
            title = user_message[:30] + "..." if len(user_message) > 30 else user_message
            new_convo_doc = {
                "userId": user_id,
                "title": title,
                "messages": [user_message_doc, ai_message_doc], # Langsung tambahkan user & AI
                "createdAt": datetime.now(),
                "updatedAt": datetime.now()
            }
            insert_result = chat_history_collection.insert_one(new_convo_doc)
            conversation_id = insert_result.inserted_id # Ambil _id baru
            
        print("Percakapan berhasil disimpan ke MongoDB.")

        # --- 6. Kirim balasan ---
        return jsonify({"answer": ai_response, "conversationId": str(conversation_id)})

    except Exception as e:
        print(f"Error di /api/chat: {e}")
        return jsonify({"error": "Terjadi kesalahan di server"}), 500

# --- 7. Jalankan Server ---
if __name__ == "__main__":
    app.run(port=3001, debug=True)