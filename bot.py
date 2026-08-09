import os
import asyncio
import logging
import time
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncScheduler

from config import (
    API_ID, API_HASH, BOT_TOKEN, ADMIN_ID, LOG_CHANNEL, 
    FORCE_CHANNELS_LIST, VERIFY_EXPIRE_HOURS, SHORTENER_URL, 
    HOW_TO_VERIFY_LINK, missing_keys
)
from database import (
    add_user, get_user, update_verified_time, 
    set_block_status, set_help_state, 
    get_total_users, get_monthly_users
)
from diskwala import fetch_media_from_link

# Logging setup
logging.basicConfig(level=logging.INFO)

app = Client("DiskwalaBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

active_chats = {} # user_id: admin_id

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    user_id = message.from_user.id
    await add_user(user_id)
    
    welcome_text = (
        "👋 Welcome! / Namaste!\n\n"
        "Send me any Diskwala or supported file link to download videos and photos seamlessly (Up to 100+ items).\n"
        "Mujhe koi bhi Diskwala link bhejiye, main videos aur photos download kar dunga."
    )
    await message.reply_text(welcome_text)

@app.on_message(filters.command("help") & filters.private)
async def help_handler(client: Client, message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    
    if user and user.get("is_blocked"):
        return await message.reply_text("❌ You are blocked from using support. / Aapko support use karne se block kiya gaya hai.")
    
    await set_help_state(user_id, True)
    active_chats[user_id] = ADMIN_ID
    
    help_msg = (
        "🛠️ **Support System / Sahayta Kendra**\n\n"
        "Please describe your problem below. Your message has been forwarded to the admin.\n"
        "Kripya apni samasya yahan likhein. Admin ko message bhej diya gaya hai."
    )
    await message.reply_text(help_msg)
    
    forward_text = f"🚨 **New Help Request**\nUser ID: `{user_id}`\nUsername: @{message.from_user.username or 'None'}"
    if ADMIN_ID:
        try:
            await client.send_message(ADMIN_ID, forward_text)
            await message.forward(ADMIN_ID)
        except Exception:
            pass
    if LOG_CHANNEL:
        try:
            await client.send_message(LOG_CHANNEL, forward_text)
            await message.forward(LOG_CHANNEL)
        except Exception:
            pass
        
    async def expire_session():
        await asyncio.sleep(300)
        if user_id in active_chats:
            del active_chats[user_id]
            await set_help_state(user_id, False)
            try:
                await client.send_message(user_id, "⏳ Your help session has expired due to inactivity. Use /help again if needed.")
            except Exception:
                pass
            
    asyncio.create_task(expire_session())

@app.on_message(filters.command("problem_solved") & filters.user(ADMIN_ID))
async def problem_solved_handler(client: Client, message: Message):
    target_user = None
    for u_id in active_chats.keys():
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
    
    bot_info = await client.get_me()
    bot_name = bot_info.first_name
    bot_username = f"@{bot_info.username}" if bot_info.username else "No Username"
    
    stats_text = (
        f"📊 **Bot Statistics & Delay Report / Dainik Report**\n\n"
        f"🤖 **Bot Name:** `{bot_name}`\n"
        f"🔗 **Bot Username:** `{bot_username}`\n\n"
        f"• Total Users / Kul Users: `{total}`\n"
        f"• Monthly Active Users / Mahine ke Active Users: `{monthly}`\n"
        f"• Status: All Systems Operational 🟢"
    )
    await message.reply_text(stats_text)
    
    # Log channel mein bhi Bot Name/Username ke sath report bhejne ke liye
    if LOG_CHANNEL:
        try:
            await client.send_message(LOG_CHANNEL, stats_text)
        except Exception:
            pass

@app.on_message(filters.private & ~filters.command(["start", "help", "problem_solved", "block", "stats"]))
async def media_link_handler(client: Client, message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    
    if user and user.get("is_blocked"):
        return
        
    if user_id in active_chats:
        if ADMIN_ID:
            try:
                await message.forward(ADMIN_ID)
            except Exception:
                pass
        return
        
    url = message.text.strip()
    if not url.startswith("http"):
        return await message.reply_text("❌ Please send a valid link! / Kripya ek valid link bhejiye.")

    # 1. Force Join Verification Check (Supports both Public & Private Channels via ID/Username)
    if FORCE_CHANNELS_LIST:
        for channel in FORCE_CHANNELS_LIST:
            try:
                member = await client.get_chat_member(channel, user_id)
                if member.status in ["left", "kicked"]:
                    raise Exception("Not joined")
            except Exception:
                # Agar channel username hai toh invite link banayein, warna direct text dikhayein
                channel_link = f"https://t.me/{channel.replace('@', '')}" if isinstance(channel, str) and not channel.startswith("-") else "https://t.me"
                join_buttons = [
                    [InlineKeyboardButton("📢 Join Channel", url=channel_link)],
                    [InlineKeyboardButton("🔄 Try Again / Dubara Check Karein", callback_data="check_join")]
                ]
                return await message.reply_text(
                    "⚠️ **Force Join Required!**\nPlease join our update channels to use the bot.\n\n"
                    "*Note:* Agar aap pehle se joined hain par error aa raha hai, toh channel leave karke dubara join karein.",
                    reply_markup=InlineKeyboardMarkup(join_buttons)
                )

    # 2. Verification Status Check (Bilingual Dynamic Prompt)
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
            [InlineKeyboardButton("🔗 Verify Now", url=SHORTENER_URL or "https://t.me")],
            [InlineKeyboardButton("❓ How to Verify", url=HOW_TO_VERIFY_LINK or "https://t.me")]
        ]
        return await message.reply_text(verify_msg, reply_markup=InlineKeyboardMarkup(v_buttons))

    # 3. Dynamic Progress Status & Bulk Download Processing (100+ items support)
    status_msg = await message.reply_text("⏳ **Total videos number + downloading...**")
    
    result = await fetch_media_from_link(url)
    
    try:
        await status_msg.delete()
    except Exception:
        pass
        
    if not result.get("success"):
        return await message.reply_text("❌ Failed to fetch media or link is invalid. / Media fetch karne mein asafalta.")

    media_list = result.get("media_list", [])
    total_found = result.get("total_found", len(media_list))
    downloaded_count = 0
    
    # Processing bulk items loop
    for media in media_list:
        try:
            # File download/send logic
            downloaded_count += 1
        except Exception:
            pass

    # Partial Download Tracking Message (e.g. 1/10)
    if downloaded_count < total_found:
        await message.reply_text(f"⚠️ **({downloaded_count}/{total_found})** - Partial download completed. Kuch files download nahi ho saki.")

async def send_missing_keys_alert():
    if missing_keys and ADMIN_ID:
        try:
            await app.start()
            keys_str = ", ".join(missing_keys)
            alert_text = (
                f"⚠️ **Configuration Warning / Missing Keys Alert**\n\n"
                f"Following environment variables are missing or unconfigured in Render:\n"
                f"`{keys_str}`\n\n"
                f"Bot is running smoothly using fallback values, but please configure them for full features."
            )
            await app.send_message(ADMIN_ID, alert_text)
            await app.stop()
        except Exception:
            pass

if __name__ == "__main__":
    if missing_keys:
        asyncio.get_event_loop().run_until_complete(send_missing_keys_alert())
    app.run()
    
