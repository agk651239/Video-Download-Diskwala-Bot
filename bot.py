import os
import asyncio
import logging
import time
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncScheduler

from database import (
    add_user, get_user, update_verified_time, 
    set_block_status, set_help_state, 
    get_total_users, get_monthly_users
)
from diskwala import fetch_media_from_link

# Logging setup
logging.basicConfig(level=logging.INFO)

# Environment Variables Configuration (Nothing Hardcoded)
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "0"))
FORCE_CHANNELS = [ch.strip() for ch in os.environ.get("FORCE_CHANNELS", "").split(",") if ch.strip()]
VERIFY_EXPIRE_HOURS = int(os.environ.get("VERIFY_EXPIRE_HOURS", "12"))
SHORTENER_URL = os.environ.get("SHORTENER_URL", "")
SHORTENER_API = os.environ.get("SHORTENER_API", "")
HOW_TO_VERIFY_LINK = os.environ.get("HOW_TO_VERIFY_LINK", "https://youtube.com")

app = Client("DiskwalaBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Active Admin Chat Sessions Map
active_chats = {} # user_id: admin_id

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    user_id = message.from_user.id
    await add_user(user_id)
    
    welcome_text = (
        "👋 Welcome! / Namaste!\n\n"
        "Send me any Diskwala or supported file link to download videos and photos seamlessly.\n"
        "Mujhe koi bhi Diskwala link bhejiye, main videos aur photos download kar dunga."
    )
    await message.reply_text(welcome_text)

@app.on_message(filters.command("help") & filters.private)
async def help_handler(client: Client, message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    
    if user and user.get("is_blocked"):
        return await message.reply_text("❌ You are blocked from using support.")
    
    await set_help_state(user_id, True)
    active_chats[user_id] = ADMIN_ID
    
    help_msg = (
        "🛠️ **Support System / Sahayta Kendra**\n\n"
        "Please describe your problem below. Your message has been forwarded to the admin.\n"
        "Kripya apni samasya yahan likhein. Admin ko message bhej diya gaya hai."
    )
    await message.reply_text(help_msg)
    
    # Forward to Admin and Log Channel
    forward_text = f"🚨 **New Help Request**\nUser ID: `{user_id}`\nUsername: @{message.from_user.username or 'None'}"
    if ADMIN_ID:
        await client.send_message(ADMIN_ID, forward_text)
        await message.forward(ADMIN_ID)
    if LOG_CHANNEL:
        await client.send_message(LOG_CHANNEL, forward_text)
        await message.forward(LOG_CHANNEL)
        
    # 5 Minutes Session Timeout Logic
    async def expire_session():
        await asyncio.sleep(300)
        if user_id in active_chats:
            del active_chats[user_id]
            await set_help_state(user_id, False)
            await client.send_message(user_id, "⏳ Your help session has expired due to inactivity. Use /help again if needed.")
            
    asyncio.create_task(expire_session())

@app.on_message(filters.command("problem_solved") & filters.user(ADMIN_ID))
async def problem_solved_handler(client: Client, message: Message):
    if not message.reply_to_message:
        return await message.reply_text("Reply to a user's forwarded message or provide context.")
    
    # Extract user ID from reply text if possible, or handle generic closure
    # For robust handling, look up active chats
    target_user = None
    for u_id, a_id in list(active_chats.items()):
        target_user = u_id
        break
        
    if target_user:
        del active_chats[target_user]
        await set_help_state(target_user, False)
        await client.send_message(target_user, "✅ Your issue has been marked as resolved by the admin. /start to continue.")
        await message.reply_text(f"Session closed for user `{target_user}`.")
    else:
        await message.reply_text("No active help session found.")

@app.on_message(filters.command("block") & filters.user(ADMIN_ID))
async def block_user_handler(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/block <user_id>`")
    target_id = int(message.command[1])
    await set_block_status(target_id, True)
    await message.reply_text(f"🚫 User `{target_id}` has been blocked.")

@app.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def stats_handler(client: Client, message: Message):
    total = await get_total_users()
    start_of_month = time.time() - (30 * 86400)
    monthly = await get_monthly_users(start_of_month)
    
    stats_text = (
        f"📊 **Bot Statistics / Ankde**\n\n"
        f"• Total Users / Kul Users: `{total}`\n"
        f"• Monthly Active Users: `{monthly}`"
    )
    await message.reply_text(stats_text)

@app.on_message(filters.private & ~filters.command(["start", "help", "problem_solved", "block", "stats"]))
async def media_link_handler(client: Client, message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    
    if user and user.get("is_blocked"):
        return
        
    # Handle active admin chat forwarding
    if user_id in active_chats:
        if ADMIN_ID:
            await message.forward(ADMIN_ID)
        return
        
    url = message.text.strip()
    if not url.startswith("http"):
        return await message.reply_text("❌ Please send a valid link! / Kripya ek valid link bhejiye.")

    # 1. Force Join Verification Check
    if FORCE_CHANNELS:
        for channel in FORCE_CHANNELS:
            try:
                member = await client.get_chat_member(channel, user_id)
                if member.status in ["left", "kicked"]:
                    raise Exception("Not joined")
            except Exception:
                join_buttons = [[InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{channel.replace('@', '')}")],
                                [InlineKeyboardButton("🔄 Try Again / Dubara Check Karein", callback_data="check_join")]]
                return await message.reply_text(
                    "⚠️ **Force Join Required!**\nPlease join our update channels to use the bot.\n\n"
                    "*Note:* Agar aap pehle se joined hain par error aa raha hai, toh channel leave karke dubara join karein.",
                    reply_markup=InlineKeyboardMarkup(join_buttons)
                )

    # 2. Verification Status Check
    current_time = time.time()
    verified_time = user.get("verified_time", 0) if user else 0
    expire_limit = VERIFY_EXPIRE_HOURS * 3600
    
    if (current_time - verified_time) > expire_limit:
        verify_msg = (
            f"🔐 **Verification Required / Verification Zaroori Hai**\n\n"
            f"Verify once to get unlimited Videos download for the next {VERIFY_EXPIRE_HOURS} hours.\n"
            f"Agle {VERIFY_EXPIRE_HOURS} ghante tak unlimited videos download karne ke liye verify karein."
        )
        v_buttons = [
            [InlineKeyboardButton("🔗 Verify Now", url=SHORTENER_URL)],
            [InlineKeyboardButton("❓ How to Verify", url=HOW_TO_VERIFY_LINK)]
        ]
        return await message.reply_text(verify_msg, reply_markup=InlineKeyboardMarkup(v_buttons))

    # 3. Dynamic Progress Status & Bulk Download Processing
    status_msg = await message.reply_text("⏳ **Total videos number + downloading...**")
    
    result = await fetch_media_from_link(url)
    
    # Delete downloading status prompt immediately after fetching
    try:
        await status_msg.delete()
    except Exception:
        pass
        
    if not result.get("success") or not result.get("media_list"):
        return await message.reply_text("❌ Failed to fetch media or link is invalid. / Media fetch karne mein asafalta.")

    media_list = result["media_list"]
    total_found = len(media_list)
    downloaded_count = 0
    
    # Simulating bulk media processing (up to 100+ items)
    for media in media_list:
        try:
            # Send file logic here (Photo/Video)
            # await client.send_video(user_id, media['url'], caption="...")
            downloaded_count += 1
        except Exception:
            pass

    # Partial Download Tracking Message (e.g. 1/10)
    if downloaded_count < total_found:
        await message.reply_text(f"⚠️ ({downloaded_count}/{total_found}) - Partial download completed. Kuch files download nahi ho saki.")

if __name__ == "__main__":
    app.run()
  
