# app/rag/retriever.py - Fixed version with proper collection boolean checks
import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from app.db import get_user_files_collection

class MultiUserRetriever:
    def __init__(self):
        self.embedding_model = self._get_embeddings()
        self.user_retrievers = {}  # Cache retrievers per user
    
    def _get_embeddings(self):
        """Get embedding model"""
        return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    
    def _get_user_index_dir(self, user_id: str) -> str:
        """Get index directory for specific user"""
        return f"rag_index_{user_id}"
    
    def build_user_index(self, user_id: str, file_paths: List[str]) -> bool:
        """Build or update index for a specific user"""
        index_dir = Path(self._get_user_index_dir(user_id))
        index_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            docs = []
            for file_path in file_paths:
                if not Path(file_path).exists():
                    print(f"Warning: File not found: {file_path}")
                    continue
                
                loader = PyPDFLoader(file_path)
                file_docs = loader.load()
                
                # Add user metadata to each document
                for doc in file_docs:
                    doc.metadata["user_id"] = user_id
                    doc.metadata["source"] = Path(file_path).name
                
                docs.extend(file_docs)
            
            if not docs:
                print(f"No documents loaded for user {user_id}")
                return False
            
            # Split documents
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000, 
                chunk_overlap=150
            )
            chunks = splitter.split_documents(docs)
            
            # Create vector store
            vs = FAISS.from_documents(chunks, self.embedding_model)
            vs.save_local(str(index_dir))
            
            # Clear cached retriever to force reload
            if user_id in self.user_retrievers:
                del self.user_retrievers[user_id]
            
            print(f"Built index for {user_id} with {len(chunks)} chunks")
            return True
            
        except Exception as e:
            print(f"Error building index for {user_id}: {e}")
            return False
    
    def get_user_retriever(self, user_id: str):
        """Get retriever for specific user, load if not cached"""
        if user_id in self.user_retrievers:
            return self.user_retrievers[user_id]
        
        index_dir = self._get_user_index_dir(user_id)
        index_path = Path(index_dir)
        
        if not index_path.exists():
            print(f"No index found for user {user_id}")
            return None
        
        try:
            vs = FAISS.load_local(
                index_dir, 
                self.embedding_model, 
                allow_dangerous_deserialization=True
            )
            retriever = vs.as_retriever(search_kwargs={"k": 6})
            self.user_retrievers[user_id] = retriever
            return retriever
        except Exception as e:
            print(f"Error loading retriever for {user_id}: {e}")
            return None
    
    def query_user_documents(self, user_id: str, query: str, top_k: int = 4) -> Tuple[str, List]:
        """Query documents for a specific user"""
        retriever = self.get_user_retriever(user_id)
        
        if not retriever:  # ✅ This is fine - retriever is not a MongoDB collection
            return "No documents available for this user.", []
        
        try:
            raw_docs = retriever.get_relevant_documents(query)[:top_k]
            
            if not raw_docs:
                return "No relevant information found in your documents.", []
            
            context_blocks = []
            for doc in raw_docs:
                source = doc.metadata.get("source", "unknown")
                page = doc.metadata.get("page")
                tag = f"{source}#p{page}" if page is not None else source
                context_blocks.append(f"[SOURCE: {tag}]\n{doc.page_content}")
            
            context_text = "\n\n".join(context_blocks)
            return context_text, raw_docs
            
        except Exception as e:
            print(f"Error querying documents for {user_id}: {e}")
            return "Error retrieving documents.", []
    
    def add_file_to_user_index(self, user_id: str, file_path: str) -> bool:
        """Add a single file to user's existing index"""
        # Get existing files for this user
        files_collection = get_user_files_collection(user_id)
        
        # ❌ OLD CODE - This causes the error:
        # if not files_collection:
        #     return False
        
        # ✅ FIXED CODE - Explicit None comparison:
        if files_collection is None:
            print(f"Files collection not available for user {user_id}")
            return False
        
        # Get all file paths for this user
        user_files = list(files_collection.find({"user_id": user_id, "processed": True}))
        file_paths = [f["file_path"] for f in user_files]
        
        # Add new file
        if file_path not in file_paths:
            file_paths.append(file_path)
        
        # Rebuild index with all files
        return self.build_user_index(user_id, file_paths)
    
    def get_user_file_list(self, user_id: str) -> List[str]:
        """Get list of files for a user"""
        files_collection = get_user_files_collection(user_id)
        
        # ❌ OLD CODE:
        # if not files_collection:
        #     return []
        
        # ✅ FIXED CODE - Explicit None comparison:
        if files_collection is None:
            return []
        
        user_files = list(files_collection.find({"user_id": user_id, "processed": True}))
        return [f["original_filename"] for f in user_files]

# Global retriever instance
multi_user_retriever = MultiUserRetriever()