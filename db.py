
from pymongo import MongoClient



client = MongoClient("mongodb+srv://arkstar2625123:Allstar12@cluster0n.o0vpqxy.mongodb.net/"
)

# Choose your database
db = client["chat_db"]  

# Choose your collection
collection = db["chat_history"]  



# Insert a test message
collection.insert_one({
    "user_id": "user123",
    "thread_id": "thread456",
    "role": "user",
    "message": "Hello, this is a test!",
    
})

# Retrieve and print the message
result = collection.find_one({"user_id": "user123"})
print(result)