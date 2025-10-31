import pandas as pd
from sentence_transformers import SentenceTransformer
from chromadb import HttpClient
import sys

# --- 1. Initialize Client & Model ---
print("Connecting to ChromaDB at localhost:8000...")
try:
    # We connect to the same server as app.py
    client = HttpClient(host='localhost', port=8000)
    collection = client.get_or_create_collection(name="website_knowledge")
    print("✅ Successfully connected to ChromaDB.")
except Exception as e:
    print("❌ FAILED to connect to ChromaDB. Ensure the ChromaDB server is running.")
    print(f"Error: {e}")
    sys.exit(1)

print("Loading 'all-MiniLM-L6-v2' embedding model (this might take a moment)...")
model = SentenceTransformer('all-MiniLM-L6-v2')
print("✅ Embedding model successfully loaded.")

# --- 2. Read CSV File ---
file_path = "knowledge_base_FINAL_COMBINED.csv"  # Ensure this file name is correct
try:
    df = pd.read_csv(file_path)
    df = df.fillna('')
    print(f"✅ Successfully loaded {len(df)} chunks from {file_path}.")
except FileNotFoundError:
    print(f"❌ Error: File {file_path} not found.")
    sys.exit(1)

# --- 3. Prepare Data ---
documents = df['chunk_text'].tolist()
metadatas = df[['main_topic', 'chunk_title', 'src_url']].to_dict('records')
ids = df['chunk_id'].tolist()

# --- 4. CREATE EMBEDDINGS (The Most Important Part) ---
# app.py creates embeddings 'on-the-fly' for 1 question
# This script creates embeddings for ALL documents at once
print(f"Starting embedding process for {len(documents)} documents...")
embeddings = model.encode(documents, show_progress_bar=True)
print("✅ Embeddings complete.")

# --- 5. Add to ChromaDB ---
# Delete old data (if any) to prevent duplication
try:
    collection.delete(ids=ids)
    print("Old data in the collection successfully deleted.")
except Exception as e:
    print("No old data to delete, continuing...")

print("Adding new data to ChromaDB (in batches)...")
batch_size = 100
for i in range(0, len(ids), batch_size):
    print(f"  Adding batch {i//batch_size + 1}...")
    collection.add(
        embeddings=embeddings[i:i+batch_size].tolist(),
        documents=documents[i:i+batch_size],
        metadatas=metadatas[i:i+batch_size],
        ids=ids[i:i+batch_size]
    )

print(f"🎉 ALL DONE! {collection.count()} documents successfully stored in ChromaDB.")
