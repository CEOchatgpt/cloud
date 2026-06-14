# channel_cache.py
import logging
import json

logger = logging.getLogger(__name__)

async def send_to_telegram_api(method: str, payload: dict, token: str):
    """تابع مرکزی برای ارسال رکوئست به API تلگرام در کلودفلر"""
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        response = await fetch(url, method="POST", headers={"Content-Type": "application/json"}, body=json.dumps(payload))
        return await response.json()
    except Exception as e:
        logger.error(f"Telegram API Error ({method}): {e}")
        return None

async def save_media_to_channel(content_type: str, media_items: list, caption: str, env) -> list:
    """
    ارسال فایل‌ها به کانال دیتابیس تلگرامی شما.
    کانال‌های هدف بر اساس wrangler.toml خوانده می‌شوند.
    """
    token = env.BOT_TOKEN
    channel_id = getattr(env, f"{content_type.upper()}_CHANNEL_ID", env.POST_CHANNEL_ID)
    message_ids = []

    # ارسال به صورت تک فایل یا مالتی‌مدیا بر اساس متدهای تلگرام
    if len(media_items) == 1:
        item = media_items[0]
        method = "sendVideo" if item["type"] == "video" else "sendPhoto"
        key = "video" if item["type"] == "video" else "photo"
        
        payload = {
            "chat_id": channel_id,
            key: item["url"],
            "caption": caption
        }
        res = await send_to_telegram_api(method, payload, token)
        if res and res.get("ok"):
            message_ids.append(res["result"]["message_id"])
    else:
        # ارسال آلبوم (sendMediaGroup)
        media_group = []
        for i, item in enumerate(media_items):
            media_group.append({
                "type": item["type"],
                "media": item["url"],
                "caption": caption if i == 0 else ""
            })
        payload = {
            "chat_id": channel_id,
            "media": media_group
        }
        res = await send_to_telegram_api("sendMediaGroup", payload, token)
        if res and res.get("ok"):
            message_ids = [msg["message_id"] for msg in res["result"]]

    return message_ids
