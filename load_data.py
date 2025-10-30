import pandas as pd
from sentence_transformers import SentenceTransformer
from chromadb import HttpClient
import sys

# --- 1. Inisialisasi Klien & Model ---
print("Menghubungkan ke ChromaDB di localhost:8000...")
try:
    # Kita terhubung ke server yang sama dengan app.py
    client = HttpClient(host='localhost', port=8000)
    collection = client.get_or_create_collection(name="website_knowledge")
    print("✅ Berhasil terhubung ke ChromaDB.")
except Exception as e:
    print(f"❌ GAGAL terhubung ke ChromaDB. Pastikan server ChromaDB berjalan.")
    print(f"Error: {e}")
    sys.exit(1)

print("Memuat model embedding 'all-MiniLM-L6-v2' (ini mungkin butuh waktu)...")
model = SentenceTransformer('all-MiniLM-L6-v2')
print("✅ Model embedding berhasil dimuat.")

# --- 2. Baca File CSV ---
file_path = "knowledge_base_FINAL_COMBINED.csv" # Pastikan nama file ini benar
try:
    df = pd.read_csv(file_path)
    df = df.fillna('')
    print(f"✅ Berhasil memuat {len(df)} chunk dari {file_path}.")
except FileNotFoundError:
    print(f"❌ Error: File {file_path} tidak ditemukan.")
    sys.exit(1)

# --- 3. Siapkan Data ---
documents = df['chunk_text'].tolist()
metadatas = df[['main_topic', 'chunk_title', 'src_url']].to_dict('records')
ids = df['chunk_id'].tolist()

# --- 4. BUAT EMBEDDING (Bagian Paling Penting) ---
# app.py membuat embedding 'on-the-fly' untuk 1 pertanyaan
# Script ini membuat embedding untuk SEMUA dokumen sekaligus
print(f"Memulai proses embedding untuk {len(documents)} dokumen...")
embeddings = model.encode(documents, show_progress_bar=True)
print("✅ Embedding selesai.")

# --- 5. Tambahkan ke ChromaDB ---
# Hapus data lama (jika ada) agar tidak duplikat
try:
    collection.delete(ids=ids)
    print("Data lama di collection berhasil dihapus.")
except Exception as e:
    print("Tidak ada data lama untuk dihapus, melanjutkan...")

print("Menambahkan data baru ke ChromaDB (dalam batch)...")
batch_size = 100
for i in range(0, len(ids), batch_size):
    print(f"  Menambahkan batch {i//batch_size + 1}...")
    
    collection.add(
        embeddings=embeddings[i:i+batch_size].tolist(),
        documents=documents[i:i+batch_size],
        metadatas=metadatas[i:i+batch_size],
        ids=ids[i:i+batch_size]
    )

print(f"🎉 SEMUA SELESAI! {collection.count()} dokumen berhasil disimpan di ChromaDB.")