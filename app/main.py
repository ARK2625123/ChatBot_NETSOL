# app/main.py - Fixed version with proper collection boolean checks
import os
import uuid
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, Request, Query, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware

# Fixed: Use absolute imports instead of relative imports
from app.db import get_user_messages_collection, get_user_files_collection
from app.model import ChatIn, ChatMessage, FileMetadata, UserSwitchRequest
from app.llm.gemini import ask_gemini
from app.rag.retriever import multi_user_retriever
from app.agent.langgraph_agent import ChatbotAgent
from app.file_handler import file_handler

app = FastAPI()

# Initialize the LangGraph agent
def rag_wrapper(user_id: str, query: str):
    """Wrapper function for RAG retrieval to be used by the agent"""
    return multi_user_retriever.query_user_documents(user_id, query)

chatbot_agent = ChatbotAgent(rag_wrapper)

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

@app.on_event("startup")
def startup_event():
    """Initialize any necessary components on startup"""
    print("[STARTUP] Multi-user RAG chatbot initialized")
    print("[STARTUP] Supported users: user1, user2, user3")

# ---- Chat endpoints ----
@app.post("/chat")
async def chat(
    request: Request,
    body: ChatIn,
    include_citations: bool = Query(False),
):
    """Main chat endpoint with multi-user support"""
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    user_id = body.user_id
    
    # Validate user_id
    if user_id not in ["user1", "user2", "user3"]:
        raise HTTPException(status_code=400, detail="Invalid user_id. Must be user1, user2, or user3")
    
    # Get user's message collection
    messages_collection = get_user_messages_collection(user_id)
    if messages_collection is None:  # ✅ FIXED: Explicit None comparison
        raise HTTPException(status_code=500, detail="Database error")
    
    try:
        # Use LangGraph agent to process the query
        answer = chatbot_agent.run(body.message, user_id)
        
        # Store user message
        user_message = ChatMessage(
            user_id=user_id,
            thread_id="default",
            role="user",
            content=body.message,
            request_id=req_id,
            created_at=datetime.utcnow(),
        )
        messages_collection.insert_one(user_message.model_dump())
        
        # Store bot message
        bot_message = ChatMessage(
            user_id=user_id,
            thread_id="default",
            role="assistant",
            content=answer,
            request_id=req_id,
            created_at=datetime.utcnow(),
        )
        messages_collection.insert_one(bot_message.model_dump())
        
        # Prepare response
        resp = {
            "request_id": req_id,
            "answer": answer,
            "user_id": user_id
        }
        
        # Add citations if requested
        if include_citations:
            try:
                # Get RAG context for citations
                _, raw_docs = multi_user_retriever.query_user_documents(user_id, body.message, top_k=3)
                if raw_docs:
                    citations = []
                    for doc in raw_docs:
                        source = doc.metadata.get("source", "unknown")
                        page = doc.metadata.get("page", "N/A")
                        citations.append({
                            "source": source,
                            "page": page,
                            "snippet": doc.page_content[:180]
                        })
                    resp["citations"] = citations
            except Exception as e:
                print(f"Error getting citations: {e}")
        
        return resp
        
    except Exception as e:
        print(f"Chat error for {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Chat processing error: {str(e)}")

@app.get("/chat/history/{user_id}")
async def get_chat_history(user_id: str, limit: int = Query(50, ge=1, le=200)):
    """Get chat history for a specific user"""
    # Ensure user_id is valid
    if user_id not in ["user1", "user2", "user3"]:
        raise HTTPException(status_code=400, detail="Invalid user_id")
    
    # Get the messages collection for the user
    messages_collection = get_user_messages_collection(user_id)
    if messages_collection is None:  # ✅ FIXED: Explicit None comparison
        raise HTTPException(status_code=500, detail="Database error")
    
    try:
        # Fetch the chat history from MongoDB (sorted by created_at descending)
        messages_cursor = messages_collection.find({"user_id": user_id}).sort("created_at", -1).limit(limit)
        
        # Convert the cursor to a list and reverse it to chronological order
        messages_list = list(messages_cursor)
        messages_list.reverse()

        # Prepare the chat history response
        history = []
        for msg in messages_list:
            # Handle different field names (in case fields vary)
            role = msg.get("role", "user")  # Default to 'user' if role is missing
            content = msg.get("content", "")  # Default to empty if content is missing

            # Convert timestamp to ISO format if it exists
            timestamp = msg.get("created_at")
            timestamp = timestamp.isoformat() if timestamp else None

            history.append({
                "role": role,
                "content": content,
                "timestamp": timestamp,
            })
        
        return {"user_id": user_id, "history": history}
        
    except Exception as e:
        print(f"Error getting history for {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving chat history: {str(e)}")

# ---- File management endpoints ----
@app.post("/files/upload")
async def upload_file(
    user_id: str = Form(...),
    file: UploadFile = File(...)
):
    """Upload a file for a specific user"""
    print(f"Received request to upload file for user: {user_id}")  # Debugging message
    
    # Check if user_id is valid
    if user_id not in ["user1", "user2", "user3"]:
        print(f"Invalid user_id: {user_id}")  # Debugging message
        raise HTTPException(status_code=400, detail="Invalid user_id")
    
    try:
        print(f"Preparing to upload file: {file.filename}")  # Debugging message
        file_metadata = await file_handler.upload_file(user_id, file)
        
        # Debugging the response from file_handler.upload_file
        print(f"File uploaded successfully: {file_metadata.original_filename}, Processed: {file_metadata.processed}")  
        
        return {
            "message": "File uploaded successfully",
            "user_id": user_id,
            "filename": file_metadata.original_filename,
            "processed": file_metadata.processed
        }
    
    except HTTPException as http_error:
        print(f"HTTP error occurred: {str(http_error)}")  # Debugging message
        raise
    
    except Exception as e:
        print(f"Unexpected error during file upload: {str(e)}")  # Debugging message
        raise HTTPException(status_code=500, detail=f"File upload error: {str(e)}")

@app.get("/files/{user_id}")
async def get_user_files(user_id: str):
    """Get files uploaded by a specific user"""
    print(f"Fetching files for user: {user_id}")  # Debugging message
    
    try:
        # ❌ OLD CODE - Wrong collection and wrong boolean check:
        # user_files_collection = get_user_messages_collection(user_id)
        # if user_files_collection:
        
        # ✅ FIXED CODE - Correct collection and explicit None comparison:
        user_files_collection = get_user_files_collection(user_id)  # Use files collection, not messages
        print(f"User files collection for {user_id}: {user_files_collection}")  # Debugging message
        
        if user_files_collection is None:  # ✅ FIXED: Explicit None comparison
            print(f"User files collection not found for user: {user_id}")  # Debugging message
            raise HTTPException(status_code=500, detail="User files collection not found.")
        
        # ✅ FIXED: Actually fetch files from the files collection
        user_files_cursor = user_files_collection.find({"user_id": user_id})
        user_files = []
        
        for file_doc in user_files_cursor:
            # Convert ObjectId to string for JSON serialization
            file_doc["_id"] = str(file_doc["_id"])
            # Convert datetime to ISO string if present
            if "upload_time" in file_doc and file_doc["upload_time"]:
                file_doc["upload_time"] = file_doc["upload_time"].isoformat()
            user_files.append(file_doc)
        
        print(f"Files retrieved for user {user_id}: {len(user_files)} files")  # Debugging message
        
        return {"user_id": user_id, "files": user_files}
    
    except Exception as e:
        print(f"Error getting files for {user_id}: {str(e)}")  # Debugging message
        raise HTTPException(status_code=500, detail=f"Error getting files for user {user_id}: {str(e)}")

@app.delete("/files/{user_id}/{filename}")
async def delete_file(user_id: str, filename: str):
    """Delete a file for a specific user"""
    if user_id not in ["user1", "user2", "user3"]:
        raise HTTPException(status_code=400, detail="Invalid user_id")
    
    try:
        # Find the internal filename
        files_collection = get_user_files_collection(user_id)
        
        # ✅ FIXED: Explicit None comparison
        if files_collection is None:
            raise HTTPException(status_code=500, detail="Database error")
        
        file_data = files_collection.find_one({"user_id": user_id, "original_filename": filename})
        
        if not file_data:
            raise HTTPException(status_code=404, detail="File not found")
        
        success = file_handler.delete_user_file(user_id, file_data["filename"])
        
        if success:
            return {"message": f"File '{filename}' deleted successfully", "user_id": user_id}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete file")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting file {filename} for {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")


@app.delete("/chat/history/{user_id}")
async def clear_chat_history(user_id: str):
    """Clear chat history for a specific user"""
    if user_id not in ["user1", "user2", "user3"]:
        raise HTTPException(status_code=400, detail="Invalid user_id")
    
    try:
        messages_collection = get_user_messages_collection(user_id)
        if messages_collection is None:
            raise HTTPException(status_code=500, detail="Database error")
        
        result = messages_collection.delete_many({"user_id": user_id})
        return {
            "message": f"Chat history cleared for {user_id}",
            "deleted_messages": result.deleted_count
        }
    except Exception as e:
        print(f"Error clearing history for {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error clearing history: {str(e)}")
    

# ---- User management endpoints ----
@app.get("/users")
async def get_available_users():
    """Get list of available users"""
    return {"users": ["user1", "user2", "user3"]}

@app.get("/users/{user_id}/status")
async def get_user_status(user_id: str):
    """Get status of a specific user"""
    try:
        user_collection = get_user_messages_collection(user_id)
        if user_collection is None:
            raise HTTPException(status_code=500, detail="User collection not found.")
        
        message_count = user_collection.count_documents({"user_id": user_id})
        
        # Get files collection to check file count
        files_collection = get_user_files_collection(user_id)
        file_count = 0
        processed_files = 0
        uploaded_files = []
        
        if files_collection is not None:
            file_count = files_collection.count_documents({"user_id": user_id})
            processed_files = files_collection.count_documents({"user_id": user_id, "processed": True})
            
            # Get list of uploaded file names
            files_cursor = files_collection.find({"user_id": user_id}, {"original_filename": 1})
            uploaded_files = [f["original_filename"] for f in files_cursor]
        
        user_status = {
            "user_id": user_id, 
            "status": "active",
            "message_count": message_count,
            "file_count": file_count,
            "processed_files": processed_files,  # ✅ Added this field
            "uploaded_files": uploaded_files     # ✅ Added this field
        }
        return user_status
        
    except Exception as e:
        print(f"Error getting status for {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting user status: {str(e)}")

# ---- Health check ----
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "features": {
            "multi_user": True,
            "file_upload": True,
            "rag": True,
            "web_search": True,
            "langgraph": True
        }
    }