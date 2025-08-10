# gradio_app.py
import os
import uuid
import requests
import gradio as gr

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")
HTTP_TIMEOUT = float(os.getenv("GRADIO_HTTP_TIMEOUT", "6"))  # seconds

# ---------- simple API helpers ----------
def api_create_thread(user_id: str) -> str:
    r = requests.post(f"{API_BASE}/threads",
                      params={"user_id": user_id},
                      timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    return r.json()["thread_id"]

def api_list_threads(user_id: str):
    try:
        r = requests.get(f"{API_BASE}/threads",
                         params={"user_id": user_id},
                         timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        return r.json().get("threads", [])
    except Exception:
        # Never block the UI; show an empty list
        return []

def api_history(user_id: str, thread_id: str):
    r = requests.get(f"{API_BASE}/threads/{thread_id}/history",
                     params={"user_id": user_id, "limit": 200},
                     timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    return r.json().get("messages", [])

def api_chat(user_id: str, thread_id: str | None, message: str):
    payload = {"user_id": user_id, "thread_id": thread_id, "message": message}
    r = requests.post(f"{API_BASE}/chat",
                      json=payload,
                      params={"include_citations": False},
                      timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    return data["thread_id"], data["answer"]

def api_ingest(thread_id: str, file_paths: list[str]) -> dict:
    files = []
    for p in file_paths or []:
        files.append(("files", (os.path.basename(p), open(p, "rb"), "application/pdf")))
    data = {"thread_id": thread_id}
    try:
        r = requests.post(f"{API_BASE}/ingest",
                          files=files,
                          data=data,
                          headers={"X-Thread-ID": thread_id},
                          timeout=max(HTTP_TIMEOUT, 30))  # uploads can take longer
    finally:
        for _, f in files:
            try: f[1].close()
            except Exception: pass
    r.raise_for_status()
    return r.json()

# ---------- gradio callbacks ----------
def init_state():
    return {"user_id": f"user_{uuid.uuid4().hex[:8]}", "thread_id": None}

def refresh_threads(state):
    threads = api_list_threads(state["user_id"])
    choices = [t["thread_id"] for t in threads]
    # Always return a valid dropdown state even if choices is []
    value = state.get("thread_id") if state.get("thread_id") in choices else None
    return gr.Dropdown(choices=choices, value=value, label="Threads")

def select_thread(thread_id, state, chat):
    state["thread_id"] = thread_id
    chat_hist = []
    if thread_id:
        try:
            msgs = api_history(state["user_id"], thread_id)
            for m in msgs:
                if m["role"] == "user":
                    chat_hist.append((m["content"], None))
                else:
                    if chat_hist and chat_hist[-1][1] is None:
                        chat_hist[-1] = (chat_hist[-1][0], m["content"])
                    else:
                        chat_hist.append((None, m["content"]))
        except Exception:
            pass
    return chat_hist, state

def new_thread(state, thread_drop):
    try:
        tid = api_create_thread(state["user_id"])
    except Exception:
        # Fallback: generate a local id so UI keeps working
        tid = f"t_{uuid.uuid4().hex[:10]}"
    state["thread_id"] = tid
    threads = api_list_threads(state["user_id"])
    choices = [t["thread_id"] for t in threads]
    if tid not in choices:
        choices.insert(0, tid)
    return state, gr.Dropdown(choices=choices, value=tid, label="Threads")

def ensure_thread(state):
    if not state.get("thread_id"):
        state["thread_id"] = api_create_thread(state["user_id"])
    return state

def send_message(message, chat, state):
    if not message.strip():
        return gr.update(), chat, state, gr.update(visible=True, value="Type something first.")
    try:
        state = ensure_thread(state)
    except Exception:
        return "", chat, state, gr.update(visible=True, value="Could not create/select a thread.")
    chat = chat + [(message, None)]
    try:
        thread_id, answer = api_chat(state["user_id"], state["thread_id"], message)
        state["thread_id"] = thread_id
        chat[-1] = (message, answer)
        notice = gr.update(visible=False)
    except requests.HTTPError as e:
        notice = gr.update(visible=True, value=f"Chat error: {e}")
    except Exception as e:
        notice = gr.update(visible=True, value=f"Chat error: {type(e).__name__}")
    return "", chat, state, notice

def do_upload(files, state):
    if not files:
        return gr.update(visible=True, value="Please pick at least one PDF.")
    try:
        state = ensure_thread(state)
        data = api_ingest(state["thread_id"], files)
        if "thread_id" in data and data["thread_id"] != state["thread_id"]:
            state["thread_id"] = data["thread_id"]
        return gr.update(visible=True, value=f"Uploaded {len(files)} file(s) to thread {state['thread_id']} ✓")
    except requests.HTTPError as e:
        return gr.update(visible=True, value=f"Upload failed: {e}")
    except Exception as e:
        return gr.update(visible=True, value=f"Upload failed: {type(e).__name__}")

# ---------- UI ----------
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("## NETSOL Chat — per‑thread RAG")
    state = gr.State(init_state())

    with gr.Row():
        thread_drop = gr.Dropdown(label="Threads", choices=[], allow_custom_value=False)
        refresh_btn = gr.Button("↻ Refresh", size="sm")
        new_btn = gr.Button("＋ New thread", size="sm")
        info = gr.Markdown(visible=False)

    chat = gr.Chatbot(height=420)
    msg = gr.Textbox(label="Message", placeholder="Ask something…")
    send = gr.Button("Send", variant="primary")

    with gr.Row():
        files = gr.Files(label="Upload PDFs", file_count="multiple", type="filepath")
        upload_btn = gr.Button("Upload")

    demo.load(refresh_threads, inputs=state, outputs=thread_drop)   # no lambda; simpler
    refresh_btn.click(refresh_threads, inputs=state, outputs=thread_drop)
    new_btn.click(new_thread, inputs=[state, thread_drop], outputs=[state, thread_drop])

    thread_drop.change(select_thread, inputs=[thread_drop, state, chat], outputs=[chat, state])

    send.click(send_message, inputs=[msg, chat, state], outputs=[msg, chat, state, info])
    msg.submit(send_message, inputs=[msg, chat, state], outputs=[msg, chat, state, info])

    upload_btn.click(do_upload, inputs=[files, state], outputs=info)

if __name__ == "__main__":
    demo.launch(server_port=7860, show_error=True)
