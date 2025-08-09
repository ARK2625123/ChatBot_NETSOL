# app/models.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ChatIn(BaseModel):
    user_id: str
    thread_id: Optional[str] = None
    message: str

class ChatMessage(BaseModel):
    user_id: str
    thread_id: str
    role: str               # "user" or "assistant"
    content: str
    ts: datetime = datetime.utcnow()
    request_id: Optional[str] = None
