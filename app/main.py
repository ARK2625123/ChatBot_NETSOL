# app/main.py
import uuid
from fastapi import FastAPI, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from .db import messages
from .model import ChatIn, ChatMessage
from datetime import datetime
from pymongo import ASCENDING, DESCENDING
import logging

app = FastAPI()
log = logging.getLogger("uvicorn.error")

# Allow CORS for dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Attach request_id to every request
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

# Startup: create indexes
@app.on_event("startup")
def create_indexes():
    try:
        messages.create_index([("user_id", ASCENDING), ("thread_id", ASCENDING), ("ts", DESCENDING)])
        messages.create_index([("request_id", ASCENDING)])
        log.info("MongoDB indexes ensured.")
    except Exception as e:
        log.error(f"Mongo index creation failed: {e}")

# Health check
@app.get("/health")
async def health():
    return {"status": "ok"}

# Chat endpoint
@app.post("/chat")
async def chat(request: Request, body: ChatIn):
    req_id = request.state.request_id
    thread_id = body.thread_id or f"t_{uuid.uuid4().hex[:10]}"

    # Store user message
    user_msg = ChatMessage(
        user_id=body.user_id,
        thread_id=thread_id,
        role="user",
        content=body.message,
        ts=datetime.utcnow(),
        request_id=req_id
    ).model_dump()
    messages.insert_one(user_msg)

    # Placeholder assistant reply (later replaced with RAG/LangGraph)
    bot_reply = "Got it! (LLM reply will go here.)"
    bot_msg = ChatMessage(
        user_id=body.user_id,
        thread_id=thread_id,
        role="assistant",
        content=bot_reply,
        ts=datetime.utcnow(),
        request_id=req_id
    ).model_dump()
    messages.insert_one(bot_msg)

    return {
        "request_id": req_id,
        "thread_id": thread_id,
        "answer": bot_reply
    }

# History endpoint
@app.get("/history")
async def history(
    user_id: str = Query(...),
    thread_id: str = Query(...),
    limit: int = Query(50, ge=1, le=200)
):
    cursor = messages.find({"user_id": user_id, "thread_id": thread_id}).sort("ts", 1).limit(limit)
    docs = [
        {
            "role": d["role"],
            "content": d["content"],
            "ts": d.get("ts"),
            "request_id": d.get("request_id")
        }
        for d in cursor
    ]
    return {"count": len(docs), "messages": docs}
