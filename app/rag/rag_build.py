# app/rag/rag_build.py
import os
from pathlib import Path
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
EMBED_MODEL = "all-MiniLM-L6-v2"

def load_docs(paths):
    docs = []
    for p in paths:
        p = Path(p)
        if not p.exists():
            continue
        if p.suffix.lower() == ".pdf":
            docs.extend(PyPDFLoader(str(p)).load())
        else:
            docs.extend(TextLoader(str(p), encoding="utf-8").load())
    return docs

def build_or_update_index(input_paths, index_dir: str):
    """
    Creates or updates a FAISS index at index_dir from the given input files.
    """
    Path(index_dir).mkdir(parents=True, exist_ok=True)
    docs = load_docs(input_paths)
    if not docs:
        raise RuntimeError("No documents loaded for indexing.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
    )
    chunks = splitter.split_documents(docs)
    embedder = HuggingFaceEmbeddings(model_name=EMBED_MODEL)

    # create new OR merge into existing
    if (Path(index_dir) / "index.faiss").exists():
        vs = FAISS.load_local(index_dir, embedder, allow_dangerous_deserialization=True)
        vs.add_documents(chunks)
        vs.save_local(index_dir)
    else:
        vs = FAISS.from_documents(chunks, embedder)
        vs.save_local(index_dir)
