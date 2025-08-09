# app/main.py
import uuid
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, Request, Query
from fastapi.middleware.cors import CORSMiddleware

from .db import messages
from .model import ChatIn, ChatMessage
from .rag.retriever import load_retriever
from .llm.gemini import ask_gemini

app = FastAPI()
retriever = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- request id middleware (safe to keep) ----
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    rid = str(uuid.uuid4())
    request.state.request_id = rid
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response


@app.on_event("startup")
def _startup():
    global retriever
    retriever = load_retriever()


def _ensure_thread_id(thread_id: Optional[str]) -> str:
    return thread_id or f"t_{uuid.uuid4().hex[:10]}"


def _answer_with_rag(question: str, top_k: int = 4):
    """
    Retrieves top-k chunks (if retriever available), builds a prompt,
    calls Gemini, and returns (answer, raw_docs).
    raw_docs are the retrieved LangChain Documents; we decide later
    whether to expose citations to the client.
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
            context_blocks.append(f"[SOURCE: {src}]\n{d.page_content}")
    else:
        context_blocks.append("(No index loaded)")

    context_text = "\n\n".join(context_blocks)
    prompt = f"""You are a helpful analyst. Use ONLY the context to answer.
If unsure from context, say you don't know.

Question:
{question}

Context:
{context_text}

Answer with 2-4 sentences.
"""

    answer = ask_gemini(prompt).strip()
    return answer, raw_docs


@app.post("/chat")
async def chat(
    request: Request,
    body: ChatIn,
    include_citations: bool = Query(False),
):
    # be defensive: if middleware didn’t run, synthesize an id
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    thread_id = _ensure_thread_id(body.thread_id)

    # store user message (lean)
    user_msg = ChatMessage(
        user_id=body.user_id,
        thread_id=thread_id,
        role="user",
        content=body.message,
        request_id=req_id,
    ).model_dump()
    messages.insert_one(user_msg)

    # RAG + Gemini
    answer, raw_docs = _answer_with_rag(body.message)

    # store bot message (lean)
    bot_msg = ChatMessage(
        user_id=body.user_id,
        thread_id=thread_id,
        role="assistant",
        content=answer,
        request_id=req_id,
    ).model_dump()
    messages.insert_one(bot_msg)

    # build response
    resp = {
        "request_id": req_id,
        "thread_id": thread_id,
        "answer": answer,
    }

    # optional tiny citations (NOT stored in DB)
    if include_citations and raw_docs:
        citations = []
        seen = set()
        for d in raw_docs[:3]:  # keep it small
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
