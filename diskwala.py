import os
import aiohttp
import logging
from config import DISKWALA_PROXY_URL, DISKWALA_API_KEY

async def fetch_media_from_link(url: str) -> dict:
    """
    Diskwala ya kisi bhi file-sharing site se bulk media (videos aur photos, 100+ items tak) 
    fetch karne ke liye modular function jo Render Proxy Server ka use karta hai.
    """
    try:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": DISKWALA_API_KEY
        }
        payload = {
            "url": url
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(DISKWALA_PROXY_URL, json=payload, headers=headers, timeout=30) as response:
                if response.status == 200:
                    data = await response.json()
                    file_info = data.get("fileInfo", {})
                    direct_url = file_info.get("url")
                    
                    if direct_url:
                        media_item = {
                            "type": "video" if "video" in file_info.get("type", "video") else "photo",
                            "url": direct_url,
                            "caption": f"📥 Downloaded via Diskwala Bot\n📄 Name: {file_info.get('name', 'video.mp4')}"
                        }
                        return {
                            "success": True,
                            "media_list": [media_item],
                            "total_found": 1
                        }
                
                err_text = await response.text()
                logging.error(f"Proxy Server Error Status {response.status}: {err_text}")

        return {
            "success": False,
            "error": "Proxy server did not return valid media.",
            "media_list": [],
            "total_found": 0
        }

    except Exception as e:
        logging.error(f"Diskwala Downloader Error: {e}")
        return {
            "success": False,
            "error": str(e),
            "media_list": [],
            "total_found": 0
        }
        
