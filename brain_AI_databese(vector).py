"""
=============================================================================
brain_AI_databese(vector).py (AI RAG ENGINE BUILDER)
=============================================================================
This file is the core of the Retrieval-Augmented Generation (RAG) system.
Read this file fourth.

It takes the raw text laws (from the CSV datasets) and mathematically 
converts them into a 1024-Dimensional Chroma Vector Database using the 
fine-tuned BGE-M3 embedding model. This allows Llama 3 to instantly 
search and retrieve relevant laws when a user asks a question.
"""
import pandas as pd
import glob
import os
import shutil
import torch
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

# --- CONFIGURATION ---
# Cleaned dataset folder produced by clean_and_optimize_datasets.py
DATA_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cleaned_datasets")
# Absolute path so the DB is always built in the project folder
DB_FOLDER   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "law_db")

# ── Embedding model — fine-tuned on Egyptian law (+49.63% MRR) ───────────────
_FINETUNED_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "fine_tuning", "outputs", "bge_m3_finetuned", "model"
)
# Fall back to base model if the fine-tuned checkpoint is not present
MODEL_NAME = _FINETUNED_PATH if os.path.isdir(_FINETUNED_PATH) else "BAAI/bge-m3"

def load_all_csvs(folder_path):
    all_files = glob.glob(os.path.join(folder_path, "*.csv"))
    if not all_files:
        print(f"❌ No CSV files found in: {folder_path}")
        return pd.DataFrame()

    df_list = []
    print(f"📂 Found {len(all_files)} files. Loading...")
    
    for file in all_files:
        try:
            df = pd.read_csv(file)
        except UnicodeDecodeError:
            try: df = pd.read_csv(file, encoding='windows-1256')
            except: continue
            
        if 'text' not in df.columns:
            potential_cols = [c for c in df.columns if 'content' in c.lower() or 'text' in c.lower() or 'مادة' in c.lower()]
            if potential_cols: df['text'] = df[potential_cols[0]]
            else: continue

        df['law_file'] = os.path.basename(file)
        if 'source' not in df.columns: df['source'] = os.path.basename(file)
        df_list.append(df)
        print(f"   ✅ Loaded {os.path.basename(file)}")
        
    return pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()

def create_vector_db(df):
    print("✂️  Splitting text chunks...")
    chunks = [
        Document(
            page_content=str(row.get('text', '')),
            metadata={"source": str(row.get('source', 'N/A')), "file": str(row.get('law_file', 'N/A'))}
        )
        for row in df.to_dict(orient='records')
    ]

    print(f"🧠 Loading High-Quality Model: {MODEL_NAME}...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    embedding_model = HuggingFaceEmbeddings(
        model_name=MODEL_NAME,
        model_kwargs={'device': device},
        encode_kwargs={'normalize_embeddings': True}
    )
    
    if os.path.exists(DB_FOLDER): shutil.rmtree(DB_FOLDER)

    print(f"💾 Building Database in '{DB_FOLDER}' (This takes time)...")
    Chroma.from_documents(documents=chunks, embedding=embedding_model, persist_directory=DB_FOLDER)
    print("✅ Database created successfully!")

if __name__ == "__main__":
    if not os.path.exists(DATA_FOLDER): print(f"❌ Folder '{DATA_FOLDER}' missing.")
    else:
        df = load_all_csvs(DATA_FOLDER)
        if not df.empty: create_vector_db(df)