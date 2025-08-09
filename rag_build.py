# rag_build.py
import os
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

INDEX_DIR = "rag_index"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
EMBED_MODEL = "all-MiniLM-L6-v2"

def load_docs(paths):
    docs = []
    for p in paths:
        p = Path(p)
        if not p.exists():
            print(f"[WARN] Skipping missing file: {p}")
            continue
        if p.suffix.lower() == ".pdf":
            loader = PyPDFLoader(str(p))
            docs.extend(loader.load())
        else:
            loader = TextLoader(str(p), encoding="utf-8")
            docs.extend(loader.load())
    return docs

def build_index(input_paths):
    print("[1/3] Loading documents...")
    docs = load_docs(input_paths)
    if not docs:
        raise RuntimeError("No documents loaded. Check file paths.")

    print(f"   Loaded {len(docs)} root documents")

    print("[2/3] Splitting...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP
    )
    chunks = splitter.split_documents(docs)
    print(f"   Created {len(chunks)} chunks")

    print("[3/3] Embedding + FAISS...")
    embedder = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vs = FAISS.from_documents(chunks, embedder)

    Path(INDEX_DIR).mkdir(exist_ok=True)
    vs.save_local(INDEX_DIR)
    print(f"✅ Saved FAISS index to ./{INDEX_DIR}")

if __name__ == "__main__":
    # Put your PDF(s) here (use relative paths from project root)
    sources = [
        r"data\test.pdf"
    ]
    build_index(sources)
