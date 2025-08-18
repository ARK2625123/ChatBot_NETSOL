#!/usr/bin/env python3
"""
NETSOL Multi-User RAG Chatbot Frontend
Run this script to start the Gradio web interface
"""

import sys
from pathlib import Path
import subprocess
import time
import requests

def check_backend():
    """Check if backend is running"""
    try:
        response = requests.get("http://127.0.0.1:8000/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def main():
    print("🌐 Starting NETSOL Multi-User RAG Chatbot Frontend...")
    
    # Check if backend is running
    if not check_backend():
        print("⚠️  Backend API is not running!")
        print("Please start the backend first by running: python run_server.py")
        print("Or run both together with: python run_full_app.py")
        print("\nWaiting for backend to start...")
        
        # Wait up to 30 seconds for backend
        for i in range(30):
            if check_backend():
                print("✅ Backend is now available!")
                break
            time.sleep(1)
            print(f"⏳ Waiting... ({i+1}/30)")
        else:
            print("❌ Backend still not available. Please check the backend server.")
            return
    
    print("✅ Backend API is running")
    print("🌐 Frontend will be available at: http://127.0.0.1:7860")
    print("\n⚙️ Features available:")
    print("  • Switch between user1, user2, user3")
    print("  • Upload PDF, TXT, DOC, DOCX files")
    print("  • Chat with your documents")
    print("  • Web search integration")
    print("  • Automatic decision making (RAG vs Search)")
    print("\n🛑 Press Ctrl+C to stop the frontend\n")
    
    # Import and run gradio app
    try:
        from gradio_app import create_interface
        demo = create_interface()
        demo.launch(server_port=7860, show_error=True, share=False)
    except ImportError as e:
        print(f"❌ Error importing gradio_app: {e}")
        print("Make sure gradio_app.py is in the same directory")
    except Exception as e:
        print(f"❌ Error starting frontend: {e}")

if __name__ == "__main__":
    main()