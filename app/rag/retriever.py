# app/rag/retriever.py
from pathlib import Path
from typing import List

from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings

def _emb():
    # light & fast
    return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

def build_or_update_index(file_paths: List[str], index_dir: str):
    index_dir = Path(index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)

    docs = []
    for p in file_paths:
        loader = PyPDFLoader(p)
        docs.extend(loader.load())

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    chunks = splitter.split_documents(docs)

    for c in chunks:
        # keep basic metadata for citations
        c.metadata["source"] = Path(c.metadata.get("source", p)).name
        # PyPDFLoader already sets "page" (0-based). Keep it.

    vs = FAISS.from_documents(chunks, _emb())
    vs.save_local(str(index_dir))

def load_retriever(index_dir: str):
    vs = FAISS.load_local(index_dir, _emb(), allow_dangerous_deserialization=True)
    return vs.as_retriever(search_kwargs={"k": 6})
