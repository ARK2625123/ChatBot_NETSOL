# app/main.py
import os
import uuid
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .db import messages
from .model import ChatIn, ChatMessage
from .llm.gemini import ask_gemini
from .rag.retriever import load_retriever, build_or_update_index

STORAGE_PDF = os.getenv("RAG_PDF_PATH", "data/test.pdf")
INDEX_DIR = os.getenv("RAG_INDEX_DIR", "rag_index/")

app = FastAPI()
retriever = None  # loaded at startup

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- request id middleware ----
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    rid = str(uuid.uuid4())
    request.state.request_id = rid
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response


def _ensure_index():
    """
    Build/refresh the FAISS index from STORAGE_PDF into INDEX_DIR if needed.
    """
    if not os.path.exists(STORAGE_PDF):
        raise FileNotFoundError(
            f"RAG PDF not found at {STORAGE_PDF}. Put your file there or set RAG_PDF_PATH."
        )
    os.makedirs(INDEX_DIR, exist_ok=True)
    # Rebuild if index appears missing OR if PDF is newer than index folder
    idx_mtime = max((os.path.getmtime(os.path.join(INDEX_DIR, p))
                    for p in os.listdir(INDEX_DIR)), default=0.0) if os.listdir(INDEX_DIR) else 0.0
    pdf_mtime = os.path.getmtime(STORAGE_PDF)
    if idx_mtime < pdf_mtime:
        print(f"[RAG] Building/refreshing index from {STORAGE_PDF} → {INDEX_DIR}")
        build_or_update_index([STORAGE_PDF], INDEX_DIR)
    else:
        print(f"[RAG] Using existing index in {INDEX_DIR}")


@app.on_event("startup")
def _startup():
    global retriever
    _ensure_index()
    retriever = load_retriever(INDEX_DIR)
    print("[RAG] Retriever ready.")


def _answer_with_rag(question: str, top_k: int = 4):
    """
    Retrieves top-k chunks (if retriever available), builds a prompt,
    calls Gemini, and returns (answer, raw_docs).
    """
    raw_docs: List = []
    context_blocks = []

    if retriever is not None:
        try:
            raw_docs = retriever.get_relevant_documents(question)[:top_k]
        except Exception:
            raw_docs = []

        for d in raw_docs:
            src = d.metadata.get("source", "unknown")
            page = d.metadata.get("page")
            tag = f"{src}#p{page}" if page is not None else src
            context_blocks.append(f"[SOURCE: {tag}]\n{d.page_content}")
    else:
        context_blocks.append("(No index loaded)")

    context_text = "\n\n".join(context_blocks)
    prompt = f"""You are a helpful analyst. Use ONLY the context to answer.
If unsure from context, say you don't know.

Question:
{question}

Context:
{context_text}

Answer in 2–4 sentences.
"""
    answer = ask_gemini(prompt).strip()
    return answer, raw_docs


@app.post("/chat")
async def chat(
    request: Request,
    body: ChatIn,
    include_citations: bool = Query(False),
):
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    thread_id = body.thread_id or "t1"  # keep a single logical thread

    # store user message
    messages.insert_one(ChatMessage(
        user_id=body.user_id,
        thread_id=thread_id,
        role="user",
        content=body.message,
        request_id=req_id,
    ).model_dump())

    # RAG + Gemini
    answer, raw_docs = _answer_with_rag(body.message)

    # store bot message
    messages.insert_one(ChatMessage(
        user_id=body.user_id,
        thread_id=thread_id,
        role="assistant",
        content=answer,
        request_id=req_id,
    ).model_dump())

    resp = {"request_id": req_id, "thread_id": thread_id, "answer": answer}

    if include_citations and raw_docs:
        citations, seen = [], set()
        for d in raw_docs[:3]:
            src = d.metadata.get("source", "unknown")
            page = d.metadata.get("page")
            key = (src, page)
            if key in seen:
                continue
            seen.add(key)
            text = d.page_content or ""
            snippet = text[:180] + ("…" if len(text) > 180 else "")
            citations.append({"source": src, "page": page, "snippet": snippet})
        resp["citations"] = citations

    return resp


@app.post("/rebuild_index")
def rebuild_index():
    """
    Force a rebuild of the FAISS index from STORAGE_PDF.
    Handy if you replace storage/test.pdf while the server is running.
    """
    global retriever
    if not os.path.exists(STORAGE_PDF):
        raise HTTPException(404, f"Not found: {STORAGE_PDF}")
    build_or_update_index([STORAGE_PDF], INDEX_DIR)
    retriever = load_retriever(INDEX_DIR)
    return {"ok": True, "index_dir": INDEX_DIR, "source": STORAGE_PDF}
