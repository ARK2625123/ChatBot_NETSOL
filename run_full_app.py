#!/usr/bin/env python3
"""
NETSOL Multi-User RAG Chatbot - Complete Application Launcher
This script starts both the backend API and frontend web interface
"""

import subprocess
import sys
import time
import threading
import signal
import os
from pathlib import Path

class ApplicationLauncher:
    def __init__(self):
        self.backend_process = None
        self.frontend_process = None
        self.running = True
        
    def start_backend(self):
        """Start the FastAPI backend server"""
        print("🚀 Starting Backend API Server...")
        try:
            self.backend_process = subprocess.Popen([
                sys.executable, "run_server.py"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            # Give backend time to start
            time.sleep(5)
            
            if self.backend_process.poll() is None:
                print("✅ Backend API started successfully")
                return True
            else:
                print("❌ Backend failed to start")
                return False
                
        except Exception as e:
            print(f"❌ Error starting backend: {e}")
            return False
    
    def start_frontend(self):
        """Start the Gradio frontend"""
        print("🌐 Starting Frontend Web Interface...")
        try:
            self.frontend_process = subprocess.Popen([
                sys.executable, "run_frontend.py"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            time.sleep(3)
            
            if self.frontend_process.poll() is None:
                print("✅ Frontend started successfully")
                return True
            else:
                print("❌ Frontend failed to start")
                return False
                
        except Exception as e:
            print(f"❌ Error starting frontend: {e}")
            return False
    
    def monitor_processes(self):
        """Monitor both processes and handle output"""
        def read_output(process, name):
            try:
                for line in iter(process.stdout.readline, ''):
                    if self.running and line.strip():
                        print(f"[{name}] {line.strip()}")
            except:
                pass
        
        if self.backend_process:
            threading.Thread(target=read_output, args=(self.backend_process, "BACKEND"), daemon=True).start()
        
        if self.frontend_process:
            threading.Thread(target=read_output, args=(self.frontend_process, "FRONTEND"), daemon=True).start()
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signal"""
        print("\n🛑 Shutting down application...")
        self.stop()
        sys.exit(0)
    
    def stop(self):
        """Stop both processes"""
        self.running = False
        
        if self.frontend_process:
            try:
                self.frontend_process.terminate()
                self.frontend_process.wait(timeout=5)
                print("✅ Frontend stopped")
            except:
                self.frontend_process.kill()
                print("⚠️ Frontend force stopped")
        
        if self.backend_process:
            try:
                self.backend_process.terminate()
                self.backend_process.wait(timeout=5)
                print("✅ Backend stopped")
            except:
                self.backend_process.kill()
                print("⚠️ Backend force stopped")
    
    def run(self):
        """Run the complete application"""
        # Set up signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        print("="*60)
        print("🤖 NETSOL Multi-User RAG Chatbot")
        print("="*60)
        
        # Check environment
        env_file = Path(".env")
        if not env_file.exists():
            print("⚠️ No .env file found. Please create one with your API keys.")
            print("See .env.example for required variables.")
            print("Continuing anyway (some features may not work)...")
        
        # Start backend
        if not self.start_backend():
            print("❌ Failed to start backend. Exiting.")
            return
        
        # Start frontend
        if not self.start_frontend():
            print("❌ Failed to start frontend. Stopping backend.")
            self.stop()
            return
        
        # Monitor processes
        self.monitor_processes()
        
        print("\n" + "="*60)
        print("🎉 Application started successfully!")
        print("="*60)
        print("🔧 Backend API: http://127.0.0.1:8000")
        print("📚 API Docs: http://127.0.0.1:8000/docs")
        print("🌐 Frontend: http://127.0.0.1:7860")
        print("🔄 Health Check: http://127.0.0.1:8000/health")
        print("="*60)
        print("\n⚙️ Available Features:")
        print("  • 👥 Multi-user support (user1, user2, user3)")
        print("  • 📁 File upload and processing")
        print("  • 📄 RAG document analysis")
        print("  • 🔍 Web search integration (Tavily)")
        print("  • 🧠 Smart decision making (LangGraph)")
        print("  • 💬 Chat history per user")
        print("  • 🗑️ File and chat management")
        print("\n🛑 Press Ctrl+C to stop the application")
        print("="*60)
        
        try:
            # Keep the main thread alive
            while self.running:
                # Check if processes are still running
                if self.backend_process and self.backend_process.poll() is not None:
                    print("❌ Backend process died unexpectedly")
                    break
                
                if self.frontend_process and self.frontend_process.poll() is not None:
                    print("❌ Frontend process died unexpectedly")
                    break
                
                time.sleep(1)
        
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

def main():
    """Main entry point"""
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        sys.exit(1)
    
    # Check if required files exist
    required_files = [
        "run_server.py",
        "run_frontend.py", 
        "gradio_app.py",
        "app/main.py"
    ]
    
    missing_files = [f for f in required_files if not Path(f).exists()]
    if missing_files:
        print(f"❌ Missing required files: {', '.join(missing_files)}")
        sys.exit(1)
    
    # Create directories if they don't exist
    Path("uploads").mkdir(exist_ok=True)
    Path("app").mkdir(exist_ok=True)
    
    # Run the application
    launcher = ApplicationLauncher()
    launcher.run()

if __name__ == "__main__":
    main()