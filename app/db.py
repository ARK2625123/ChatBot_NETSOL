import os
from pymongo import MongoClient, ASCENDING, DESCENDING
from dotenv import load_dotenv
import certifi
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")

def get_database_client():
    """Get MongoDB client with proper error handling"""
    try:
        client = MongoClient(
            MONGODB_URI,
            tlsCAFile=certifi.where(),  # ensures valid SSL cert
            serverSelectionTimeoutMS=30000
        )
        # Test the connection
        client.admin.command('ping')
        logger.info("MongoDB connection successful")
        return client
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {str(e)}")
        raise

# Initialize client and database
client = get_database_client()
db = client["chatbot"]

# Multi-user structure: chatbot -> user1, user2, user3 -> messages
user1_messages = db["user1_messages"]
user2_messages = db["user2_messages"]
user3_messages = db["user3_messages"]

# File metadata for each user
user1_files = db["user1_files"]
user2_files = db["user2_files"]
user3_files = db["user3_files"]

# Users collection for status tracking
users_collection = db["users"]

# Helper function to get user's message collection
def get_user_messages_collection(user_id: str):
    collections = {
        "user1": user1_messages,
        "user2": user2_messages,
        "user3": user3_messages
    }
    collection = collections.get(user_id)
    if collection is None:  # ✅ FIXED: Explicit None comparison
        logger.error(f"Invalid user_id: {user_id}")
        return None
    return collection

# Helper function to get user's files collection
def get_user_files_collection(user_id: str):
    collections = {
        "user1": user1_files,
        "user2": user2_files,
        "user3": user3_files
    }
    collection = collections.get(user_id)
    
   
    
    # ✅ FIXED CODE - Explicit None comparison:
    if collection is None:
        logger.error(f"Invalid user_id: {user_id}")
        return None
    return collection

def get_user_status(user_id: str):
    """Get user status from database"""
    try:
        user = users_collection.find_one({"user_id": user_id})
        if user:
            return {
                "user_id": user_id,
                "status": user.get("status", "active"),
                "message_count": user.get("message_count", 0),
                "file_count": user.get("file_count", 0),
                "last_active": user.get("last_active")
            }
        else:
            # Create user if doesn't exist
            from datetime import datetime
            new_user = {
                "user_id": user_id,
                "status": "active",
                "created_at": datetime.utcnow(),
                "last_active": datetime.utcnow(),
                "message_count": 0,
                "file_count": 0
            }
            users_collection.insert_one(new_user)
            return new_user
    except Exception as e:
        logger.error(f"Error getting user status for {user_id}: {str(e)}")
        return {"user_id": user_id, "status": "error", "error": str(e)}

def update_user_activity(user_id: str, activity_type: str = "message"):
    """Update user's last activity and counts"""
    try:
        from datetime import datetime
        update_data = {"last_active": datetime.utcnow()}
        
        if activity_type == "message":
            update_data["$inc"] = {"message_count": 1}
        elif activity_type == "file":
            update_data["$inc"] = {"file_count": 1}
            
        users_collection.update_one(
            {"user_id": user_id},
            {"$set": update_data}
        )
    except Exception as e:
        logger.error(f"Error updating user activity for {user_id}: {str(e)}")

# Test database connection on import
try:
    # Test if collections exist by counting documents
    collection_names = db.list_collection_names()
    if collection_names is None:
        logger.warning("No collections found in database. Run 'python init_database.py' to initialize.")
    else:
        logger.info(f"Database connected successfully. Found {len(collection_names)} collections.")
except Exception as e:
    logger.error(f"Database connection test failed: {str(e)}")