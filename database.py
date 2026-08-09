import os
import time
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "TelegramBotDB")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

users_collection = db["users"]
chats_collection = db["chats"]

async def add_user(user_id: int):
    exists = await users_collection.find_one({"user_id": user_id})
    if not exists:
        await users_collection.insert_one({
            "user_id": user_id,
            "joined_date": time.time(),
            "verified_time": 0,
            "is_blocked": False,
            "waiting_help": False
        })

async def get_user(user_id: int):
    return await users_collection.find_one({"user_id": user_id})

async def update_verified_time(user_id: int, v_time: float):
    await users_collection.update_one({"user_id": user_id}, {"$set": {"verified_time": v_time}}, upsert=True)

async def set_block_status(user_id: int, status: bool):
    await users_collection.update_one({"user_id": user_id}, {"$set": {"is_blocked": status}}, upsert=True)

async def set_help_state(user_id: int, state: bool):
    await users_collection.update_one({"user_id": user_id}, {"$set": {"waiting_help": state}}, upsert=True)

async def get_total_users():
    return await users_collection.count_documents({})

async def get_monthly_users(start_timestamp: float):
    return await users_collection.count_documents({"joined_date": {"$gte": start_timestamp}})
  
