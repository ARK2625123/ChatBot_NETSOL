# app/llm/gemini.py
import os
import google.generativeai as genai

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "models/gemini-1.5-flash")

def _configure():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY missing in env")
    genai.configure(api_key=api_key)

def ask_gemini(prompt: str) -> str:
    _configure()
    model = genai.GenerativeModel(GEMINI_MODEL)
    resp = model.generate_content(prompt)
    return resp.text or ""
