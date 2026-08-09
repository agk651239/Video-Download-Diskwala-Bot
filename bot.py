import os
import asyncio
import logging
import time
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiohttp import web

from config import (
    API_ID, API_HASH, BOT_TOKEN, ADMIN_ID, LOG_CHANNEL, 
    PUBLIC_CHANNELS, PRIVATE_CHANNELS, VERIFY_EXPIRE_HOURS, 
    SHORTENER_URL, SHORTENER_API, HOW_TO_VERIFY_LINK, missing_keys
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

# Render Web Service ke liye port 10000 par aiohttp server
async def handle(request):
    return web.Response(text="Bot is running successfully!")

async def start_web_server():
    app_web = web.Application()
    app_web.add_routes([web.get("/", handle)])
    runner = web.AppRunner(app_web)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    user_id = message.from_user.id
    await add_user(user_id)
    
    # Shortener verification return check (?start=verified)
    if len(message.command) > 1 and message.command[1] == "verified":
        await update_verified_time(user_id, time.time())
        return await message.reply_text(
            "✅ **वेरिफ़िकेशन सफल रहा! / Verification Successful!**\n\n"
            f"अब आप अगले {VERIFY_EXPIRE_HOURS} घंटों के लिए असीमित वीडियो डाउनलोड कर सकते हैं।\n"
            "Now you can download videos seamlessly. Send your link again!"
        )

    welcome_text = (
        "👋 **स्वागत है! / Welcome!**\n\n"
        "Send me any Diskwala or supported file link to download videos and photos seamlessly (Up to 100+ items).\n"
        "मुझे कोई भी डिस्कवाला या समर्थित फ़ाइल लिंक भेजें, मैं वीडियो और फ़ोटो आसानी से डाउनलोड कर दूंगा।"
    )
    await message.reply_text(welcome_text)

@app.on_message(filters.command("help") & filters.private)
async def help_handler(client: Client, message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    
    if user and user.get("is_blocked"):
        return await message.reply_text("❌ आपको सहायता उपयोग करने से ब्लॉक कर दिया गया है। / You are blocked from using support.")
    
    await set_help_state(user_id, True)
    active_chats[user_id] = ADMIN_ID
    
    help_msg = (
        "🛠️ **सहायता केंद्र / Support System**\n\n"
        "Please describe your problem below. Your message has been forwarded to the admin.\n"
        "कृपया अपनी समस्या नीचे लिखें। आपका संदेश एडमिन को भेज दिया गया है।"
    )
    await message.reply_text(help_msg)
    
    forward_text = f"🚨 **नया सहायता अनुरोध / New Help Request**\nयूज़र आईडी / User ID: `{user_id}`\nयूज़रनेम / Username: @{message.from_user.username or 'None'}"
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
                await client.send_message(user_id, "⏳ निष्क्रियता के कारण आपका सहायता सत्र समाप्त हो गया है। / Your help session has expired due to inactivity. Use /help again if needed.")
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
        await client.send_message(target_user, "✅ एडमिन द्वारा आपकी समस्या का समाधान कर दिया गया है। / Your issue has been marked as resolved by the admin. /start to continue.")
        await message.reply_text(f"यूज़र `{target_user}` के लिए सत्र बंद कर दिया गया है। / Session closed for user `{target_user}`.")
    else:
        await message.reply_text("कोई सक्रिय सहायता सत्र नहीं मिला। / No active help session found.")

@app.on_message(filters.command("block") & filters.user(ADMIN_ID))
async def block_user_handler(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("उपयोग / Usage: `/block <user_id>`")
    target_id = int(message.command[1])
    await set_block_status(target_id, True)
    await message.reply_text(f"🚫 यूज़र `{target_id}` को ब्लॉक कर दिया गया है। / User `{target_id}` has been blocked.")

@app.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def stats_handler(client: Client, message: Message):
    total = await get_total_users()
    start_of_month = time.time() - (30 * 86400)
    monthly = await get_monthly_users(start_of_month)
    
    bot_info = await client.get_me()
    bot_name = bot_info.first_name
    bot_username = f"@{bot_info.username}" if bot_info.username else "No Username"
    
    stats_text = (
        f"📊 **बोट सांख्यिकी रिपोर्ट / Bot Statistics Report**\n\n"
        f"🤖 **बोट का नाम / Bot Name:** `{bot_name}`\n"
        f"🔗 **बोट यूज़रनेम / Bot Username:** `{bot_username}`\n\n"
        f"• कुल यूज़र / Total Users: `{total}`\n"
        f"• मासिक सक्रिय यूज़र / Monthly Active Users: `{monthly}`\n"
        f"• स्थिति / Status: सभी प्रणालियाँ कार्यरत हैं / All Systems Operational 🟢"
    )
    await message.reply_text(stats_text)
    
    if LOG_CHANNEL:
        try:
            await client.send_message(LOG_CHANNEL, stats_text)
        except Exception:
            pass

@app.on_message(filters.private & ~filters.command(["start", "help", "problem_solved", "block", "stats"]))
async def media_link_handler(client: Client, message: Message):
    user_id = message.from_user.id
    is_admin = (user_id == ADMIN_ID)
    
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
        return await message.reply_text("❌ कृपया एक वैध लिंक भेजें! / Please send a valid link!")

    # 1. Public Force Channels Check (Admin ke liye bypass, agar khali ho ya false ho toh skip)
    if PUBLIC_CHANNELS and not is_admin:
        for channel in PUBLIC_CHANNELS:
            try:
                member = await client.get_chat_member(channel, user_id)
                if member.status in ["left", "kicked"]:
                    raise Exception("Not joined")
            except Exception:
                clean_channel = channel.replace("@", "").strip()
                channel_link = f"https://t.me/{clean_channel}"
                join_buttons = [
                    [InlineKeyboardButton("📢 पब्लिक चैनल ज्वाइन करें / Join Public Channel", url=channel_link)],
                    [InlineKeyboardButton("🔄 दोबारा जाँच करें / Try Again", callback_data="check_join")]
                ]
                return await message.reply_text(
                    "⚠️ **चैनल ज्वाइन करना अनिवार्य है! / Force Join Required!**\n\n"
                    "बोट का उपयोग करने के लिए कृपया हमारे पब्लिक चैनल को ज्वाइन करें।\nPlease join our public update channel to use the bot.\n\n"
                    "*नोट / Note:* यदि आप पहले से जुड़े हैं और त्रुटि आ रही है, तो चैनल छोड़कर दोबारा ज्वाइन करें।",
                    reply_markup=InlineKeyboardMarkup(join_buttons)
                )

    # 2. Private Force Channels Check (Admin ke liye bypass, ID ya direct URL support)
    if PRIVATE_CHANNELS and not is_admin:
        for channel in PRIVATE_CHANNELS:
            channel_link = "https://t.me"
            
            # Agar direct invite link diya gaya hai
            if "t.me/" in str(channel) or "+" in str(channel):
                channel_link = channel if channel.startswith("http") else f"https://t.me/{channel}"
                join_buttons = [
                    [InlineKeyboardButton("🔒 प्राइवेट चैनल ज्वाइन करें / Join Private Channel", url=channel_link)],
                    [InlineKeyboardButton("🔄 दोबारा जाँच करें / Try Again", callback_data="check_join")]
                ]
                return await message.reply_text(
                    "⚠️ **चैनल ज्वाइन करना अनिवार्य है! / Force Join Required!**\n\n"
                    "बोट का उपयोग करने के लिए कृपया हमारे प्राइवेट चैनल को ज्वाइन करें।\nPlease join our private update channel to use the bot.\n\n"
                    "*नोट / Note:* यदि आप पहले से जुड़े हैं और त्रुटि आ रही है, तो चैनल छोड़कर दोबारा ज्वाइन करें।",
                    reply_markup=InlineKeyboardMarkup(join_buttons)
                )

            try:
                ch_id = int(channel) if channel.startswith("-") or channel.isdigit() else channel
                member = await client.get_chat_member(ch_id, user_id)
                if member.status in ["left", "kicked"]:
                    raise Exception("Not joined")
            except Exception:
                try:
                    ch_id = int(channel) if channel.startswith("-") or channel.isdigit() else channel
                    chat = await client.get_chat(ch_id)
                    channel_link = chat.invite_link or (f"https://t.me/{chat.username}" if chat.username else "https://t.me")
                except Exception:
                    channel_link = "https://t.me"

                join_buttons = [
                    [InlineKeyboardButton("🔒 प्राइवेट चैनल ज्वाइन करें / Join Private Channel", url=channel_link)],
                    [InlineKeyboardButton("🔄 दोबारा जाँच करें / Try Again", callback_data="check_join")]
                ]
                return await message.reply_text(
                    "⚠️ **चैनल ज्वाइन करना अनिवार्य है! / Force Join Required!**\n\n"
                    "बोट का उपयोग करने के लिए कृपया हमारे प्राइवेट चैनल को ज्वाइन करें।\nPlease join our private update channel to use the bot.\n\n"
                    "*नोट / Note:* यदि आप पहले से जुड़े हैं और त्रुटि आ रही है, तो चैनल छोड़कर दोबारा ज्वाइन करें।",
                    reply_markup=InlineKeyboardMarkup(join_buttons)
                )

    # Verification Status Check (Admin ke liye bypass)
    if not is_admin:
        current_time = time.time()
        verified_time = user.get("verified_time", 0) if user else 0
        expire_limit = VERIFY_EXPIRE_HOURS * 3600
        
        if (current_time - verified_time) > expire_limit:
            import aiohttp
            import urllib.parse
            
            # Default fallback link agar shortener configure na ho
            final_verify_url = SHORTENER_URL or "https://t.me"
            
            # Shortener URL aur API ko match karke link generate karna
            if SHORTENER_URL and SHORTENER_API:
                try:
                    bot_info = await client.get_me()
                    callback_target_url = f"https://t.me/{bot_info.username}?start=verified"
                    
                    encoded_target = urllib.parse.quote(callback_target_url, safe='')
                    base_url = SHORTENER_URL.rstrip('/')
                    api_endpoint = f"{base_url}/api?api={SHORTENER_API}&url={encoded_target}"
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(api_endpoint, timeout=10) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                if isinstance(data, dict):
                                    shortened = data.get("shortenedUrl") or data.get("url") or data.get("short_url")
                                    if shortened:
                                        final_verify_url = shortened
                except Exception:
                    pass

            target_how_to_url = HOW_TO_VERIFY_LINK if HOW_TO_VERIFY_LINK and HOW_TO_VERIFY_LINK.startswith("http") else "https://t.me"

            verify_msg = (
                f"🔐 **वेरिफ़िकेशन आवश्यक है / Verification Required**\n\n"
                f"Verify once to get unlimited Videos download for the next {VERIFY_EXPIRE_HOURS} hours.\n"
                f"अगले {VERIFY_EXPIRE_HOURS} घंटों के लिए असीमित वीडियो डाउनलोड करने हेतु एक बार वेरिफ़ाई करें।"
            )
            v_buttons = [
                [InlineKeyboardButton("🔗 अभी वेरिफ़ाई करें / Verify Now", url=final_verify_url)],
                [InlineKeyboardButton("❓ वेरिफ़ाई कैसे करें? / How to Verify", url=target_how_to_url)]
            ]
            return await message.reply_text(verify_msg, reply_markup=InlineKeyboardMarkup(v_buttons))

    # Dynamic Progress Status & Bulk Download Processing
    status_msg = await message.reply_text("⏳ **कुल वीडियो गिने जा रहे हैं + डाउनलोड हो रहे हैं... / Total videos number + downloading...**")
    
    result = await fetch_media_from_link(url)
    
    try:
        await status_msg.delete()
    except Exception:
        pass
        
    if not result.get("success"):
        return await message.reply_text("❌ मीडिया फ़ेच करने में विफलता या लिंक अमान्य है। / Failed to fetch media or link is invalid.")

    media_list = result.get("media_list", [])
    total_found = result.get("total_found", len(media_list))
    
    if not media_list:
        return await message.reply_text("❌ इस लिंक में कोई मीडिया नहीं मिला। / No media found in this link.")

    downloaded_count = 0
    
    for media in media_list:
        try:
            media_url = media.get("url") or media.get("file_url")
            caption = media.get("caption", "Here is your video / photo!")
            
            if media_url:
                if media.get("type") == "photo" or media_url.endswith((".jpg", ".png", ".jpeg")):
                    await client.send_photo(chat_id=user_id, photo=media_url, caption=caption)
                else:
                    await client.send_video(chat_id=user_id, video=media_url, caption=caption)
                downloaded_count += 1
                await asyncio.sleep(1)
        except Exception as e:
            print(f"Error sending media: {e}")
            pass

    if downloaded_count == 0:
        await message.reply_text("❌ वीडियो भेजने में विफल रहा। / Failed to send media.")
    elif downloaded_count < total_found:
        await message.reply_text(f"⚠️ **({downloaded_count}/{total_found})** - आंशिक डाउनलोड पूर्ण हुआ। कुछ फ़ाइलें नहीं भेजी जा सकीं। / Partial download completed.")
    else:
        await message.reply_text(f"✅ **सभी {downloaded_count} फ़ाइलें सफलतापूर्वक भेज दी गई हैं! / All files sent successfully!**")

async def send_missing_keys_alert():
    if missing_keys and ADMIN_ID:
        try:
            await app.start()
            keys_str = ", ".join(missing_keys)
            alert_text = (
                f"⚠️ **कॉन्फ़िगरेशन चेतावनी / Missing Keys Alert**\n\n"
                f"रेंडर में निम्नलिखित पर्यावरण चर गायब या अनकॉफ़िगर हैं:\nFollowing environment variables are missing in Render:\n"
                f"`{keys_str}`"
            )
            await app.send_message(ADMIN_ID, alert_text)
            await app.stop()
        except Exception:
            pass

if __name__ == "__main__":
    if missing_keys:
        asyncio.get_event_loop().run_until_complete(send_missing_keys_alert())
    
    loop = asyncio.get_event_loop()
    loop.create_task(start_web_server())
    app.run()
                
