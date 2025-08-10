# app/rag/retriever.py
from pathlib import Path
from functools import lru_cache
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

EMBED_MODEL = "all-MiniLM-L6-v2"
BASE_INDEX_ROOT = Path("rag_index")

@lru_cache(maxsize=64)
def load_thread_retriever(thread_id: str):
    """
    Loads FAISS retriever for a specific thread. Returns None if index doesn’t exist yet.
    """
    index_dir = BASE_INDEX_ROOT / thread_id
    if not (index_dir / "index.faiss").exists():
        return None
    embedder = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    vs = FAISS.load_local(str(index_dir), embedder, allow_dangerous_deserialization=True)
    return vs.as_retriever(search_kwargs={"k": 4})
