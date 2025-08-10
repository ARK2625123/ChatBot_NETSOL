# app/main.py
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import (
    FastAPI, Request, Query, UploadFile, File, HTTPException, Form, Header
)
from fastapi.middleware.cors import CORSMiddleware

from dotenv import load_dotenv
load_dotenv()

from .db import messages, threads
from .model import ChatIn, ChatMessage
from .llm.gemini import ask_gemini
from .tools.tavily_tool import tavily_available, web_search  # optional
from .rag.rag_build import build_or_update_index
from .rag.retriever import load_thread_retriever  # loads index by thread-id

STORAGE_ROOT = Path("storage")     # storage/<thread_id>/*
INDEX_ROOT   = Path("rag_index")   # rag_index/<thread_id>/*

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- request id ----------
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    rid = str(uuid.uuid4())
    request.state.request_id = rid
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response

# ---------- per-thread retriever cache ----------
RetrieverType = Any
retriever_cache: Dict[str, RetrieverType] = {}  # thread_id -> retriever

@app.on_event("startup")
def startup():
    print("[RAG] Ready. Per-thread retrievers created lazily on first use.")

def _load_retriever(thread_id: str) -> Optional[RetrieverType]:
    r = retriever_cache.get(thread_id)
    if r is None:
        r = load_thread_retriever(thread_id)  # your helper should read rag_index/<thread_id>
        retriever_cache[thread_id] = r
    return r

def _invalidate(thread_id: str) -> None:
    retriever_cache.pop(thread_id, None)

def _ensure_thread_id(tid: Optional[str]) -> str:
    return tid or f"t_{uuid.uuid4().hex[:10]}"

def _resolve_thread_id(
    request: Request,
    thread_id_q: Optional[str],
    thread_id_f: Optional[str],
    thread_id_h: Optional[str],
) -> str:
    """
    Accept thread_id from query, form, or header.
    If still missing, mint a new id (don't 422) so uploads never fail.
    """
    tid = thread_id_q or thread_id_f or thread_id_h
    return _ensure_thread_id(tid)

# ---------- RAG core ----------
def _answer_with_rag(question: str, thread_id: str):
    context_blocks = []
    docs = []

    retriever = None
    try:
        retriever = _load_retriever(thread_id)
    except Exception:
        retriever = None

    if retriever is not None:
        try:
            docs = retriever.invoke(question)
        except AttributeError:
            docs = retriever.get_relevant_documents(question)

        for d in docs[:3]:
            src = d.metadata.get("source", "unknown")
            context_blocks.append(f"[DOC:{src}]\n{d.page_content}")

    # optional web fallback (kept same)
    if not context_blocks and tavily_available():
        hits = web_search(question, k=3)
        for h in hits:
            context_blocks.append(f"[WEB:{h.get('url')}]\n{h.get('content','')[:800]}")

    if not context_blocks:
        context_blocks.append("(No documents uploaded for this thread yet.)")

    prompt = f"""You are a helpful analyst.
Use ONLY the provided context to answer. If the context is insufficient, say you don't know.

Question:
{question}

Context:
{'\n\n'.join(context_blocks)}

Answer with 2-4 sentences.
"""
    answer = ask_gemini(prompt).strip()
    return answer, docs

# ---------- uploads (thread-scoped) ----------
@app.post("/upload")
async def upload_file(
    request: Request,
    thread_id_q: Optional[str] = Query(None),
    thread_id_f: Optional[str] = Form(None),
    thread_id_h: Optional[str] = Header(None, alias="X-Thread-ID"),
    file: UploadFile = File(...),
):
    thread_id = _resolve_thread_id(request, thread_id_q, thread_id_f, thread_id_h)

    thread_store = STORAGE_ROOT / thread_id
    thread_store.mkdir(parents=True, exist_ok=True)

    dest = thread_store / file.filename
    dest.write_bytes(await file.read())

    index_dir = INDEX_ROOT / thread_id
    try:
        build_or_update_index([dest], str(index_dir))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Indexing failed: {e}")

    _invalidate(thread_id)
    return {"ok": True, "thread_id": thread_id, "filename": file.filename}

@app.post("/ingest")
async def ingest(
    request: Request,
    thread_id_q: Optional[str] = Query(None),
    thread_id_f: Optional[str] = Form(None),
    thread_id_h: Optional[str] = Header(None, alias="X-Thread-ID"),
    files: List[UploadFile] = File(...),
):
    thread_id = _resolve_thread_id(request, thread_id_q, thread_id_f, thread_id_h)

    tmp_dir = STORAGE_ROOT / thread_id / "ingest_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    for uf in files:
        p = tmp_dir / f"{uuid.uuid4().hex}_{uf.filename}"
        p.write_bytes(await uf.read())
        saved_paths.append(p)

    index_dir = INDEX_ROOT / thread_id
    try:
        build_or_update_index(saved_paths, str(index_dir))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Indexing failed: {e}")

    _invalidate(thread_id)
    return {"ok": True, "thread_id": thread_id, "files": [p.name for p in saved_paths]}

# ---------- threads & history (unchanged API) ----------
def _thread_doc(thread_id: str, user_id: str):
    return {"thread_id": thread_id, "user_id": user_id, "created_at": datetime.utcnow(), "archived": False}

@app.post("/threads")
def create_thread(user_id: str):
    tid = _ensure_thread_id(None)
    threads.update_one(
        {"thread_id": tid, "user_id": user_id},
        {"$setOnInsert": _thread_doc(tid, user_id)},
        upsert=True
    )
    return {"thread_id": tid}

@app.get("/threads")
def list_threads(user_id: str):
    pipeline = [
        {"$match": {"user_id": user_id, "archived": False}},
        {"$lookup": {
            "from": "messages",
            "let": {"tid": "$thread_id", "uid": "$user_id"},
            "pipeline": [
                {"$match": {"$expr": {"$and": [
                    {"$eq": ["$thread_id", "$$tid"]},
                    {"$eq": ["$user_id", "$$uid"]}
                ]}}},
                {"$sort": {"created_at": -1}},
                {"$limit": 1},
                {"$project": {"created_at": 1}}
            ],
            "as": "last"
        }},
        {"$addFields": {"last_at": {"$ifNull": [{"$arrayElemAt": ["$last.created_at", 0]}, "$created_at"]}}},
        {"$sort": {"last_at": -1}},
        {"$project": {"_id": 0, "thread_id": 1, "last_at": 1}}
    ]
    return {"threads": list(threads.aggregate(pipeline))}

@app.get("/threads/{thread_id}/history")
def thread_history(thread_id: str, user_id: str, limit: int = 100):
    cur = messages.find({"user_id": user_id, "thread_id": thread_id}).sort("created_at", 1).limit(limit)
    hist = [{"role": m.get("role"), "content": m.get("content")} for m in cur]
    return {"messages": hist}

# ---------- chat ----------
@app.post("/chat")
async def chat(request: Request, body: ChatIn):
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    thread_id = _ensure_thread_id(body.thread_id)

    user_msg = ChatMessage(
        user_id=body.user_id,
        thread_id=thread_id,
        role="user",
        content=body.message,
        request_id=req_id,
    ).model_dump()
    user_msg["created_at"] = datetime.utcnow()
    messages.insert_one(user_msg)

    answer, _ = _answer_with_rag(body.message, thread_id)

    bot_msg = ChatMessage(
        user_id=body.user_id,
        thread_id=thread_id,
        role="assistant",
        content=answer,
        request_id=req_id,
    ).model_dump()
    bot_msg["created_at"] = datetime.utcnow()
    messages.insert_one(bot_msg)

    return {"request_id": req_id, "thread_id": thread_id, "answer": answer}
