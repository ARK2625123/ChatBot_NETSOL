import os
import requests
import gradio as gr
from typing import List, Tuple, Dict, Optional

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")

# ---------- API helpers ----------
def api_chat(user_id: str, message: str):
    """Send chat message to API"""
    payload = {"user_id": user_id, "message": message}
    r = requests.post(f"{API_BASE}/chat", json=payload, params={"include_citations": False})
    r.raise_for_status()
    return r.json()

def api_get_history(user_id: str):
    """Get chat history for user"""
    r = requests.get(f"{API_BASE}/chat/history/{user_id}")
    r.raise_for_status()
    return r.json()["history"]

def api_upload_file(user_id: str, file_path: str):
    """Upload file for user"""
    with open(file_path, 'rb') as f:
        files = {'file': f}
        data = {'user_id': user_id}
        r = requests.post(f"{API_BASE}/files/upload", files=files, data=data)
        r.raise_for_status()
        return r.json()

def api_get_user_files(user_id: str):
    """Get user's files"""
    r = requests.get(f"{API_BASE}/files/{user_id}")
    r.raise_for_status()
    return r.json()["files"]

def api_delete_file(user_id: str, filename: str):
    """Delete user's file"""
    r = requests.delete(f"{API_BASE}/files/{user_id}/{filename}")
    r.raise_for_status()
    return r.json()

def api_get_user_status(user_id: str):
    """Get user status"""
    r = requests.get(f"{API_BASE}/users/{user_id}/status")
    r.raise_for_status()
    return r.json()

def api_clear_history(user_id: str):
    """Clear user's chat history"""
    r = requests.delete(f"{API_BASE}/chat/history/{user_id}")
    r.raise_for_status()
    return r.json()

# ---------- State management ----------
def init_state():
    """Initialize application state"""
    return {
        "current_user": "user1",
        "chat_histories": {
            "user1": [],
            "user2": [],
            "user3": []
        }
    }

def load_user_history(user_id: str, state: dict):
    """Load chat history for user"""
    try:
        history = api_get_history(user_id)
        # Convert to gradio chat format
        chat_history = []
        for msg in history:
            if msg["role"] == "user":
                chat_history.append([msg["content"], None])
            elif msg["role"] == "assistant" and chat_history:
                chat_history[-1][1] = msg["content"]
        
        state["chat_histories"][user_id] = chat_history
        return chat_history, state
    except Exception as e:
        print(f"Error loading history for {user_id}: {e}")
        return [], state

# ---------- Gradio callbacks ----------
def switch_user(new_user: str, state: dict):
    """Switch to different user"""
    state["current_user"] = new_user
    
    # Load user's history
    chat_history, state = load_user_history(new_user, state)
    
    # Get user status
    try:
        status = api_get_user_status(new_user)
        status_text = f"**User: {new_user}**\n📝 Messages: {status['message_count']}\n📁 Files: {status['file_count']} ({status['processed_files']} processed)\n📋 Documents: {', '.join(status['uploaded_files']) if status['uploaded_files'] else 'None'}"
    except Exception as e:
        status_text = f"**User: {new_user}**\nError loading status: {str(e)}"
    
    # Get user files
    try:
        files = api_get_user_files(new_user)
        file_list = "\n".join([f"• {f['filename']} ({'✓' if f['processed'] else '⏳'})" for f in files]) if files else "No files uploaded"
    except Exception as e:
        file_list = f"Error loading files: {str(e)}"
    
    return (
        chat_history,  # chatbot
        state,         # state
        status_text,   # user status
        file_list,     # file list
        gr.update()    # clear any notices
    )

def send_message(message: str, chat: List, state: dict):
    """Send message to current user's chat"""
    if not message.strip():
        return "", chat, state, gr.update(visible=True, value="Please type a message.")
    
    current_user = state["current_user"]
    
    # Add user message to chat
    chat = chat + [[message, None]]
    
    try:
        # Send to API
        response = api_chat(current_user, message)
        answer = response["answer"]
        
        # Update chat with bot response
        chat[-1][1] = answer
        
        # Update state
        state["chat_histories"][current_user] = chat
        
        return "", chat, state, gr.update(visible=False)
        
    except requests.HTTPError as e:
        error_msg = f"Chat error: {e.response.status_code} - {e.response.text if e.response else 'Unknown error'}"
        return "", chat, state, gr.update(visible=True, value=error_msg)
    except Exception as e:
        return "", chat, state, gr.update(visible=True, value=f"Error: {str(e)}")

def upload_file(file, state: dict):
    """Upload file for current user"""
    if not file:
        return gr.update(), gr.update(visible=True, value="Please select a file to upload.")
    
    current_user = state["current_user"]
    
    try:
        result = api_upload_file(current_user, file.name)
        
        # Refresh file list
        files = api_get_user_files(current_user)
        file_list = "\n".join([f"• {f['filename']} ({'✓' if f['processed'] else '⏳'})" for f in files]) if files else "No files uploaded"
        
        success_msg = f"✅ File '{result['filename']}' uploaded successfully!"
        if result['processed']:
            success_msg += " Ready for queries."
        else:
            success_msg += " Processing in background..."
        
        return file_list, gr.update(visible=True, value=success_msg)
        
    except requests.HTTPError as e:
        error_detail = e.response.json().get("detail", "Unknown error") if e.response else "Unknown error"
        return gr.update(), gr.update(visible=True, value=f"Upload error: {error_detail}")
    except Exception as e:
        return gr.update(), gr.update(visible=True, value=f"Upload error: {str(e)}")

def refresh_user_info(state: dict):
    """Refresh current user's information"""
    current_user = state["current_user"]
    
    try:
        # Get user status
        status = api_get_user_status(current_user)
        status_text = f"**User: {current_user}**\n📝 Messages: {status['message_count']}\n📁 Files: {status['file_count']} ({status['processed_files']} processed)\n📋 Documents: {', '.join(status['uploaded_files']) if status['uploaded_files'] else 'None'}"
        
        # Get user files
        files = api_get_user_files(current_user)
        file_list = "\n".join([f"• {f['filename']} ({'✓' if f['processed'] else '⏳'})" for f in files]) if files else "No files uploaded"
        
        return status_text, file_list, gr.update(visible=True, value="✅ Information refreshed!")
        
    except Exception as e:
        return gr.update(), gr.update(), gr.update(visible=True, value=f"Refresh error: {str(e)}")

def clear_history(state: dict):
    """Clear current user's chat history"""
    current_user = state["current_user"]
    
    try:
        result = api_clear_history(current_user)
        
        # Clear local chat
        chat = []
        state["chat_histories"][current_user] = chat
        
        return chat, state, gr.update(visible=True, value=f"✅ Cleared {result['deleted_messages']} messages for {current_user}")
        
    except Exception as e:
        return gr.update(), state, gr.update(visible=True, value=f"Clear history error: {str(e)}")

# ---------- UI ----------
def create_interface():
    with gr.Blocks(theme=gr.themes.Soft(), title="NETSOL Multi-User RAG Chatbot") as demo:
        # Initialize state
        state = gr.State(init_state())
        
        # Header
        gr.Markdown("# 🤖 NETSOL Multi-User RAG Chatbot")
        gr.Markdown("*Upload documents, ask questions, and get AI-powered answers with web search capabilities*")
        
        with gr.Row():
            # Left column - Chat
            with gr.Column(scale=2):
                # User selection
                with gr.Row():
                    user_dropdown = gr.Dropdown(
                        choices=["user1", "user2", "user3"],
                        value="user1",
                        label="Select User",
                        interactive=True
                    )
                    refresh_btn = gr.Button("🔄 Refresh", size="sm")
                
                # Chat interface
                chatbot = gr.Chatbot(height=400, label="Chat History")
                
                with gr.Row():
                    msg_input = gr.Textbox(
                        label="Message",
                        placeholder="Ask about your documents or any topic...",
                        scale=4
                    )
                    send_btn = gr.Button("Send", variant="primary", scale=1)
                
                # Action buttons
                with gr.Row():
                    clear_btn = gr.Button("🗑️ Clear History", variant="secondary")
                
                # Status messages
                chat_notice = gr.HTML(visible=False)
        
            # Right column - File management and user info
            with gr.Column(scale=1):
                # User status
                user_status = gr.Markdown("**User: user1**\n📝 Messages: 0\n📁 Files: 0")
                
                # File upload
                gr.Markdown("### 📁 File Upload")
                file_upload = gr.File(
                    label="Upload Document",
                    file_types=[".pdf", ".txt", ".doc", ".docx"],
                    type="filepath"
                )
                upload_btn = gr.Button("📤 Upload", variant="primary")
                
                # File list
                gr.Markdown("### 📋 Uploaded Files")
                file_list = gr.Textbox(
                    label="Files",
                    value="No files uploaded",
                    interactive=False,
                    lines=5
                )
                
                # Upload status
                upload_notice = gr.HTML(visible=False)
        
        # Event handlers
        
        # User switching
        user_dropdown.change(
            fn=switch_user,
            inputs=[user_dropdown, state],
            outputs=[chatbot, state, user_status, file_list, chat_notice]
        )
        
        # Chat
        send_btn.click(
            fn=send_message,
            inputs=[msg_input, chatbot, state],
            outputs=[msg_input, chatbot, state, chat_notice]
        )
        
        msg_input.submit(
            fn=send_message,
            inputs=[msg_input, chatbot, state],
            outputs=[msg_input, chatbot, state, chat_notice]
        )
        
        # File upload
        upload_btn.click(
            fn=upload_file,
            inputs=[file_upload, state],
            outputs=[file_list, upload_notice]
        )
        
        # Refresh
        refresh_btn.click(
            fn=refresh_user_info,
            inputs=[state],
            outputs=[user_status, file_list, upload_notice]
        )
        
        # Clear history
        clear_btn.click(
            fn=clear_history,
            inputs=[state],
            outputs=[chatbot, state, chat_notice]
        )
        
        # Load initial user data
        demo.load(
            fn=switch_user,
            inputs=[gr.State("user1"), state],
            outputs=[chatbot, state, user_status, file_list, chat_notice]
        )
    
    return demo

if __name__ == "__main__":
    demo = create_interface()
    demo.launch(server_port=7860, show_error=True)