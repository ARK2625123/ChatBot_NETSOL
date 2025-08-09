# app/rag/retriever.py
from pathlib import Path
from typing import Optional

from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

INDEX_DIR = "rag_index"
EMBED_MODEL = "all-MiniLM-L6-v2"

_retriever = None  # cache in-memory


def load_retriever() -> Optional[object]:
    """
    Loads the FAISS index built by rag_build.py and returns a LangChain retriever.
    Returns None if the index isn't present.
    """
    global _retriever
    if _retriever is not None:
        return _retriever

    index_path = Path(INDEX_DIR)
    if not index_path.exists():
        print(f"[RAG] Index folder not found at: {index_path.resolve()}")
        return None

    try:
        embedder = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
        vectordb = FAISS.load_local(
            INDEX_DIR,
            embedder,
            allow_dangerous_deserialization=True,  # needed for FAISS
        )
        _retriever = vectordb.as_retriever(search_kwargs={"k": 4})
        print("[RAG] FAISS retriever loaded.")
        return _retriever
    except Exception as e:
        print(f"[RAG] Failed to load FAISS index: {e}")
        return None
