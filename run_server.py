#!/usr/bin/env python3
"""
NETSOL Multi-User RAG Chatbot Server
Run this script to start the FastAPI backend server
"""

import uvicorn
import sys
import os
from pathlib import Path

def main():
    print("🚀 Starting NETSOL Multi-User RAG Chatbot Server...")
    print("📍 Backend API will be available at: http://127.0.0.1:8000")
    print("📚 API Documentation: http://127.0.0.1:8000/docs")
    print("🔄 Health Check: http://127.0.0.1:8000/health")
    print("\n⚙️ Features enabled:")
    print("  • Multi-user support (user1, user2, user3)")
    print("  • File upload and processing")
    print("  • RAG document analysis")
    print("  • Web search integration (Tavily)")
    print("  • LangGraph decision making")
    print("\n🛑 Press Ctrl+C to stop the server\n")
    
    # Add the current directory to Python path so 'app' can be imported
    current_dir = Path(__file__).parent.absolute()
    if str(current_dir) not in sys.path:
        sys.path.insert(0, str(current_dir))
    
    # Set PYTHONPATH environment variable as well
    os.environ['PYTHONPATH'] = str(current_dir)
    
    # Run the FastAPI server
    uvicorn.run(
        "app.main:app",  # Use app.main instead of just main
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main()