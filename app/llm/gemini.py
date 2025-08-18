# app/llm/gemini.py
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
else:
    print("Warning: GOOGLE_API_KEY not found. Gemini will not work.")

def ask_gemini(prompt: str, model_name: str = "gemini-1.5-flash") -> str:
    """
    Send a prompt to Gemini and get response
    
    Args:
        prompt: The prompt to send
        model_name: Gemini model to use (default: gemini-1.5-flash)
    
    Returns:
        Generated response text
    """
    if not GOOGLE_API_KEY:
        return "Error: Google API key not configured. Please set GOOGLE_API_KEY environment variable."
    
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        
        if response.text:
            return response.text
        else:
            return "Error: No response generated from Gemini."
            
    except Exception as e:
        print(f"Gemini API error: {e}")
        return f"Error: Failed to get response from Gemini. {str(e)}"

def ask_gemini_with_history(messages: list, model_name: str = "gemini-1.5-flash") -> str:
    """
    Send conversation history to Gemini
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        model_name: Gemini model to use
        
    Returns:
        Generated response text
    """
    if not GOOGLE_API_KEY:
        return "Error: Google API key not configured."
    
    try:
        model = genai.GenerativeModel(model_name)
        
        # Convert messages to Gemini format
        chat = model.start_chat(history=[])
        
        # Add conversation history
        conversation_text = ""
        for msg in messages:
            role = "User" if msg["role"] == "user" else "Assistant"
            conversation_text += f"{role}: {msg['content']}\n"
        
        response = chat.send_message(conversation_text)
        
        if response.text:
            return response.text
        else:
            return "Error: No response generated from Gemini."
            
    except Exception as e:
        print(f"Gemini chat API error: {e}")
        return f"Error: Failed to get response from Gemini. {str(e)}"