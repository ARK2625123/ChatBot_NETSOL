import os
from pymongo import MongoClient, ASCENDING, DESCENDING
from dotenv import load_dotenv
import certifi
from datetime import datetime

load_dotenv()

def init_database():
    """Initialize the MongoDB database with required collections and sample data"""
    
    # Connect to MongoDB
    MONGODB_URI = os.getenv("MONGODB_URI")
    client = MongoClient(
        MONGODB_URI,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=30000
    )
    
    # Select database
    db = client["chatbot"]
    
    print("🔄 Initializing MongoDB database...")
    
    # Initialize collections for each user
    users = ["user1", "user2", "user3"]
    
    for user in users:
        print(f"📝 Setting up collections for {user}...")
        
        # Create message collection with sample welcome message
        messages_collection = db[f"{user}_messages"]
        sample_message = {
            "user_id": user,
            "message": "Welcome to NETSOL Multi-User RAG Chatbot!",
            "response": "Hello! I'm ready to help you with document analysis and questions. Upload a document to get started!",
            "timestamp": datetime.utcnow(),
            "message_type": "system"
        }
        
        # Insert sample message (this creates the collection)
        result = messages_collection.insert_one(sample_message)
        print(f"   ✅ Created {user}_messages collection with sample message")
        
        # Create files collection with placeholder
        files_collection = db[f"{user}_files"]
        sample_file_meta = {
            "user_id": user,
            "filename": "sample_placeholder.txt",
            "file_type": "placeholder",
            "upload_date": datetime.utcnow(),
            "file_size": 0,
            "status": "placeholder",
            "is_placeholder": True
        }
        
        # Insert sample file metadata (this creates the collection)
        files_collection.insert_one(sample_file_meta)
        print(f"   ✅ Created {user}_files collection with placeholder")
        
        # Create indexes for better performance
        messages_collection.create_index([("user_id", ASCENDING), ("timestamp", DESCENDING)])
        files_collection.create_index([("user_id", ASCENDING), ("upload_date", DESCENDING)])
        print(f"   ✅ Created indexes for {user}")
    
    # Create a general users collection for user status
    users_collection = db["users"]
    for user in users:
        user_doc = {
            "user_id": user,
            "status": "active",
            "created_at": datetime.utcnow(),
            "last_active": datetime.utcnow(),
            "message_count": 1,
            "file_count": 0
        }
        users_collection.insert_one(user_doc)
    
    print(f"   ✅ Created users collection with all user statuses")
    
    # Verify creation
    print("\n📊 Database initialization complete!")
    print("📈 Database statistics:")
    print(f"   Database name: chatbot")
    print(f"   Collections created: {len(db.list_collection_names())}")
    print(f"   Collections: {', '.join(db.list_collection_names())}")
    
    # Test connection to each collection
    print("\n🔍 Testing collections...")
    for collection_name in db.list_collection_names():
        count = db[collection_name].count_documents({})
        print(f"   {collection_name}: {count} documents")
    
    print("\n✅ Database initialization successful!")
    print("🚀 Your chatbot should now work properly!")
    
    client.close()

if __name__ == "__main__":
    init_database()