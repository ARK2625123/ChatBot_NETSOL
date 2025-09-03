# **NETSOL Multi-User RAG Chatbot**

## **Overview**

This is a **multi-user AI-powered chatbot** built with **FastAPI**, **Gradio**, **MongoDB**, and **LangChain**. It allows multiple users to upload their documents, interact with the chatbot, and receive AI-powered responses. The chatbot leverages a **Retrieve-and-Generate (RAG)** pipeline with **FAISS** for efficient document retrieval. Additionally, **Tavily** is integrated for web search capabilities when needed.

The chatbot can:
- **Handle document uploads** per user.
- **Fetch document context** and provide responses based on the uploaded information.
- **Maintain a chat history** for each user.
- **Switch between the RAG pipeline** and **Tavily** search based on the user’s query.

---

## **Features**

- **Multi-user support**: Allows multiple users to upload documents and interact with their personalized chatbot instance.
- **Document Upload**: Users can upload documents, which are indexed and used for context in the chatbot.
- **Contextual Chat**: The chatbot remembers the user’s past messages and responses to provide relevant answers.
- **Tavily Integration**: Uses **Tavily** for web search when the RAG pipeline is insufficient.
- **MongoDB Backend**: Stores chat history, uploaded files, and user data in a structured MongoDB database.

---

## **Setup**

### **Prerequisites**
Ensure you have the following installed:
- **Python 3.8+**
- **MongoDB** (running locally or on a cloud provider)

You will also need to install the following dependencies:
```bash
pip install -r requirements.txt


