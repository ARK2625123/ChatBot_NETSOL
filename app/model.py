# app/model.py
from pydantic import BaseModel
from typing import Optional, List
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
    created_at: datetime = datetime.utcnow()
    request_id: Optional[str] = None

class FileMetadata(BaseModel):
    user_id: str
    filename: str
    original_filename: str
    file_path: str
    file_size: int
    content_type: str
    upload_time: datetime = datetime.utcnow()
    processed: bool = False
    index_path: Optional[str] = None

class UserSwitchRequest(BaseModel):
    user_id: str