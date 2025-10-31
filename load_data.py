import pandas as pd
from sentence_transformers import SentenceTransformer
from chromadb import HttpClient
import sys
from dotenv import load_dotenv
import os

# --- 1. Muat .env ---
load_dotenv()
CHROMA_HOST = os.getenv("CHROMA_HOST")
CHROMA_API_KEY = os.getenv("CHROMA_API_KEY")

if not CHROMA_HOST or not CHROMA_API_KEY:
    print("❌ Error: CHROMA_HOST atau CHROMA_API_KEY tidak ditemukan di .env")
    sys.exit(1)

# --- 2. Inisialisasi Klien (Terhubung ke Cloud) ---
print(f"Menghubungkan ke ChromaDB Cloud di {CHROMA_HOST}...")
try:
    # GANTI 'HttpClient(host='localhost', port=8000)' DENGAN INI:
    client = HttpClient(
        host=CHROMA_HOST,
        headers={"Authorization": f"Bearer {CHROMA_API_KEY}"}
    )
    collection = client.get_or_create_collection(name="website_knowledge")
    print("✅ Berhasil terhubung ke ChromaDB Cloud.")
except Exception as e:
    print(f"❌ GAGAL terhubung ke ChromaDB Cloud. Cek .env Anda. Error: {e}")
    sys.exit(1)

# ... (Sisa kode load_data.py Anda tetap SAMA) ...
# (Memuat 'all-MiniLM-L6-v2', membaca CSV, membuat embedding, dan 'collection.add')