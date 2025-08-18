# app/file_handler.py - Fixed version with proper collection boolean checks
import os
import uuid
import shutil
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from fastapi import UploadFile, HTTPException

from .db import get_user_files_collection
from .model import FileMetadata
from .rag.retriever import multi_user_retriever

class FileHandler:
    def __init__(self):
        self.upload_dir = Path("uploads")
        self.upload_dir.mkdir(exist_ok=True)
        
        # Create user-specific directories
        for user_id in ["user1", "user2", "user3"]:
            user_dir = self.upload_dir / user_id
            user_dir.mkdir(exist_ok=True)
    
    def _get_user_upload_dir(self, user_id: str) -> Path:
        """Get upload directory for specific user"""
        user_dir = self.upload_dir / user_id
        user_dir.mkdir(exist_ok=True)
        return user_dir
    
    def _is_valid_file_type(self, filename: str) -> bool:
        """Check if file type is supported"""
        allowed_extensions = {'.pdf', '.txt', '.docx', '.doc'}
        return Path(filename).suffix.lower() in allowed_extensions
    
    async def upload_file(self, user_id: str, file: UploadFile) -> FileMetadata:
        """Upload and process a file for a specific user"""
        if not self._is_valid_file_type(file.filename):
            raise HTTPException(
                status_code=400,
                detail=f"File type not supported. Allowed types: PDF, TXT, DOC, DOCX"
            )
        
        # Generate unique filename
        file_id = str(uuid.uuid4())
        file_extension = Path(file.filename).suffix
        unique_filename = f"{file_id}{file_extension}"
        
        # Get user upload directory
        user_dir = self._get_user_upload_dir(user_id)
        file_path = user_dir / unique_filename
        
        try:
            # Save file
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Create file metadata
            file_metadata = FileMetadata(
                user_id=user_id,
                filename=unique_filename,
                original_filename=file.filename,
                file_path=str(file_path),
                file_size=file_path.stat().st_size,
                content_type=file.content_type or "application/octet-stream",
                upload_time=datetime.utcnow(),
                processed=False
            )
            
            # Save to database
            files_collection = get_user_files_collection(user_id)
            
            # ❌ OLD CODE - This causes the error:
            # if files_collection:
            #     files_collection.insert_one(file_metadata.model_dump())
            
            # ✅ FIXED CODE - Explicit None comparison:
            if files_collection is not None:
                files_collection.insert_one(file_metadata.model_dump())
            else:
                raise HTTPException(status_code=500, detail="Database connection failed")
            
            # Process file (add to RAG index)
            success = await self._process_file(user_id, str(file_path))
            
            if success:
                # Update processed status
                files_collection.update_one(
                    {"filename": unique_filename, "user_id": user_id},
                    {"$set": {"processed": True}}
                )
                file_metadata.processed = True
            
            return file_metadata
            
        except Exception as e:
            # Clean up file if processing failed
            if file_path.exists():
                file_path.unlink()
            raise HTTPException(status_code=500, detail=f"File processing error: {str(e)}")
    
    async def _process_file(self, user_id: str, file_path: str) -> bool:
        """Process file and add to user's RAG index"""
        try:
            # Add file to user's index
            success = multi_user_retriever.add_file_to_user_index(user_id, file_path)
            return success
        except Exception as e:
            print(f"Error processing file {file_path} for {user_id}: {e}")
            return False
    
    def get_user_files(self, user_id: str) -> List[FileMetadata]:
        """Get all files for a user"""
        files_collection = get_user_files_collection(user_id)
        
        # ❌ OLD CODE:
        # if files_collection is None:
        #     return []
        
        # ✅ FIXED CODE - Explicit None comparison:
        if files_collection is None:
            return []
        
        files_data = list(files_collection.find({"user_id": user_id}))
        return [FileMetadata(**file_data) for file_data in files_data]
    
    def delete_user_file(self, user_id: str, filename: str) -> bool:
        """Delete a file for a specific user"""
        try:
            files_collection = get_user_files_collection(user_id)
            
            # ❌ OLD CODE:
            # if files_collection is None:
            #     return False
            
            # ✅ FIXED CODE - Explicit None comparison:
            if files_collection is None:
                return False
            
            # Find file metadata
            file_data = files_collection.find_one({"user_id": user_id, "filename": filename})
            if not file_data:
                return False
            
            # Delete physical file
            file_path = Path(file_data["file_path"])
            if file_path.exists():
                file_path.unlink()
            
            # Remove from database
            files_collection.delete_one({"user_id": user_id, "filename": filename})
            
            # Rebuild index without this file
            remaining_files = list(files_collection.find({"user_id": user_id, "processed": True}))
            file_paths = [f["file_path"] for f in remaining_files]
            
            if file_paths:
                multi_user_retriever.build_user_index(user_id, file_paths)
            else:
                # No files left, clear index
                index_dir = Path(f"rag_index_{user_id}")
                if index_dir.exists():
                    shutil.rmtree(index_dir)
                # Clear cached retriever
                if user_id in multi_user_retriever.user_retrievers:
                    del multi_user_retriever.user_retrievers[user_id]
            
            return True
            
        except Exception as e:
            print(f"Error deleting file {filename} for {user_id}: {e}")
            return False

# Global file handler instance
file_handler = FileHandler()