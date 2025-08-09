# app/db.py
import os
from pymongo import MongoClient, ASCENDING, DESCENDING
from dotenv import load_dotenv
import certifi

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")

client = MongoClient(
    MONGODB_URI,
    tlsCAFile=certifi.where(),  # ensures valid SSL cert
    serverSelectionTimeoutMS=30000
)

db = client["chatbot"]
messages = db["messages"]
