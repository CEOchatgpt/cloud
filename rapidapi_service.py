# rapidapi_service.py
import aiohttp
import logging
from channel_cache import save_media_to_channel, send_to_telegram_api
from index_manager import IndexManager
from database import get_user_mode

logger = logging.getLogger(__name__)

async def get_instagram_media(url: str, env, chat_id: int):
    """تابع اصلی دانلود و هماهنگی دیتابیس تلگرامی در کلودفلر"""
    idx_manager = IndexManager(env)
    index = await idx_manager.load_index()
    
    # ۱. چک کردن اینکه آیا این لینک قبلاً دانلود شده و در ایندکس هست؟
    if url in index:
        logger.info("Media found in index, forwarding...")
        msg_ids = index[url]["message_ids"]
        channel_id = index[url]["channel_id"]
        
        # فوروارد کردن فایل‌ها از کانال دیتابیس برای کاربر (سریع‌ترین حالت ممکن)
        for msg_id in msg_ids:
            payload = {
                "chat_id": chat_id,
                "from_chat_id": channel_id,
                "message_id": msg_id
            }
            await send_to_telegram_api("forwardMessage", payload, env.BOT_TOKEN)
        return

    # ۲. اگر در دیتابیس نبود -> دریافت اطلاعات از RapidAPI
    headers = {
        "X-RapidAPI-Key": env.RAPIDAPI_KEY,
        "X-RapidAPI-Host": "instagram120.p.rapidapi.com"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://instagram120.p.rapidapi.com/api/instagram/links?url={url}", headers=headers) as response:
            if response.status != 200:
                await send_to_telegram_api("sendMessage", {"chat_id": chat_id, "text": "خطا در ارتباط با اینستاگرام! ❌"}, env.BOT_TOKEN)
                return
            
            data = await response.json()
            
            # استخراج مدیاها و کپشن از خروجی API
            media_items = []
            caption = data.get("caption", "Downloaded via Bot")
            
            if "urls" in data:
                for item in data["urls"]:
                    media_items.append({
                        "type": "video" if item.get("is_video") else "photo",
                        "url": item.get("url")
                    })
            
            if not media_items:
                await send_telegram_api("sendMessage", {"chat_id": chat_id, "text": "محتوایی یافت نشد یا لینک خصوصی است! ❌"}, env.BOT_TOKEN)
                return

            # ۳. آپلود در کانال‌های دیتابیس تلگرامت بر اساس فرمت انتخابی کاربر
            user_mode = await get_user_mode(chat_id, env)
            content_type = "reel" if "reel" in url else "post"
            
            # ذخیره در کانال دیتابیس و گرفتن شناسه پیام‌ها
            msg_ids = await save_media_to_channel(content_type, media_items, caption, env)
            channel_id = getattr(env, f"{content_type.upper()}_CHANNEL_ID", env.POST_CHANNEL_ID)

            # ۴. ذخیره این رکورد در فایل جی‌سان ایندکس (روی Cloudflare KV)
            index[url] = {
                "message_ids": msg_ids,
                "channel_id": channel_id,
                "type": content_type
            }
            await idx_manager.save_index(index)

            # ۵. حالا فوروارد یا فرستادن مستقیم برای کاربر اصلی
            for msg_id in msg_ids:
                payload = {
                    "chat_id": chat_id,
                    "from_chat_id": channel_id,
                    "message_id": msg_id
                }
                await send_to_telegram_api("forwardMessage", payload, env.BOT_TOKEN)
