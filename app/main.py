
import os
import uuid
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .db import messages
from .model import ChatIn, ChatMessage
from .llm.gemini import ask_gemini
from .rag.retriever import load_retriever

# No file upload
# STORAGE_PDF = os.getenv("RAG_PDF_PATH", "data/test.pdf")
# INDEX_DIR = os.getenv("RAG_INDEX_DIR", "rag_index/")

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


@app.on_event("startup")
def _startup():
    global retriever
    retriever = load_retriever("rag_index")  # Static index location for now
    print("[RAG] Retriever ready.")


@app.post("/chat")
async def chat(
    request: Request,
    body: ChatIn,
    include_citations: bool = Query(False),
):
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    user_id = body.user_id  # we are assuming a single user in this case

    # Get last 5 chat messages from DB (regardless of thread ID)
    messages_cursor = messages.find({"user_id": user_id}).sort("created_at", -1).limit(5)
    chat_history = [{"role": m["role"], "content": m["content"]} for m in messages_cursor]

    # Prepare context: concatenate the last 5 messages for RAG context
    context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history])

    # Add user question to context
    context += f"\nUser: {body.message}\nAssistant:"

    # Get answer from RAG
    answer, raw_docs = _answer_with_rag(context)

    # Store user message
    messages.insert_one(ChatMessage(
        user_id=body.user_id,
        thread_id="t1",  # Single thread logic, no need for thread ID
        role="user",
        content=body.message,
        request_id=req_id,
        created_at=datetime.utcnow(),
    ).model_dump())

    # Store bot message
    messages.insert_one(ChatMessage(
        user_id=body.user_id,
        thread_id="t1",
        role="assistant",
        content=answer,
        request_id=req_id,
        created_at=datetime.utcnow(),
    ).model_dump())

    # Prepare response
    resp = {
        "request_id": req_id,
        "answer": answer,
    }

    if include_citations and raw_docs:
        citations = []
        for d in raw_docs[:3]:  # limit citations to top 3
            src = d.metadata.get("source", "unknown")
            page = d.metadata.get("page", "N/A")
            citations.append({"source": src, "page": page, "snippet": d.page_content[:180]})
        resp["citations"] = citations

    return resp
