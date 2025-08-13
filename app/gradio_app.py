import os
import uuid
import requests
import gradio as gr

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")

# ---------- simple API helpers ----------
def api_chat(user_id: str, message: str):
    payload = {"user_id": user_id, "message": message}
    r = requests.post(f"{API_BASE}/chat", json=payload, params={"include_citations": False})
    r.raise_for_status()
    data = r.json()
    return data["answer"]

# ---------- gradio callbacks ----------
def init_state():
    # generate a stable user_id for local testing
    return {"user_id": f"user_{uuid.uuid4().hex[:8]}"}

def send_message(message, chat, state):
    if not message.strip():
        return gr.update(), chat, state, gr.update(visible=True, value="Type something first.")
    chat = chat + [(message, None)]
    try:
        answer = api_chat(state["user_id"], message)
        chat[-1] = (message, answer)
        notice = gr.update(visible=False)
    except requests.HTTPError as e:
        notice = gr.update(visible=True, value=f"Chat error: {e}")
    return "", chat, state, notice

# ---------- UI ----------
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("## NETSOL Chat — RAG")
    state = gr.State(init_state())

    chat = gr.Chatbot(height=420)
    msg = gr.Textbox(label="Message", placeholder="Ask something…")
    send = gr.Button("Send", variant="primary")

    send.click(send_message, inputs=[msg, chat, state], outputs=[msg, chat, state])

if __name__ == "__main__":
    demo.launch(server_port=7860, show_error=True)
