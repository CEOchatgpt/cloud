# bot.py
import json
import re

# =====================================================================
# تابع استخراج لینک (که قبلاً توی فایل جداگانه بود و الان اینجا یکپارچه شده)
# =====================================================================
def extract_instagram_id(url_or_text: str) -> dict:
    patterns = {
        'post': r'instagram\\.com/p/([A-Za-z0-9_-]+)',
        'reel': r'instagram\\.com/reel/([A-Za-z0-9_-]+)',
        'tv': r'instagram\\.com/tv/([A-Za-z0-9_-]+)',
        'story': r'instagram\\.com/stories/([^/]+)/(\\d+)',
        'highlight': r'instagram\\.com/stories/highlights/(\\d+)',
    }
    
    for media_type, pattern in patterns.items():
        match = re.search(pattern, url_or_text)
        if match:
            if media_type in ['post', 'reel', 'tv']:
                return {
                    'type': media_type,
                    'id': match.group(1),
                    'full_id': f"{media_type}:{match.group(1)}"
                }
            elif media_type == 'story':
                return {
                    'type': 'story',
                    'username': match.group(1),
                    'story_id': match.group(2),
                    'full_id': f"story:{match.group(1)}:{match.group(2)}"
                }
            elif media_type == 'highlight':
                return {
                    'type': 'highlight',
                    'id': match.group(1),
                    'full_id': f"highlight:{match.group(1)}"
                }
    return None

# =====================================================================
# هسته اصلی ربات کلودفلر
# =====================================================================
async def on_fetch(request, env, ctx):
    """
    هر پیام یا دستوری در تلگرام بیاد، اول مستقیماً وارد این تابع کلودفلر میشه.
    """
    if request.method != "POST":
        return Response.new("Method Not Allowed", status=405)

    try:
        body = await request.text()
        update = json.loads(body)
        
        if "message" in update and "text" in update["message"]:
            message = update["message"]
            chat_id = message["chat"]["id"]
            text = message["text"]

            if text == "/start":
                await send_telegram_message(env.BOT_TOKEN, chat_id, "سلام آریان عزیز به ربات دانلودر پیشرفته اینستاگرام خوش آمدی! 🚀\nلطفاً لینک مورد نظرت رو بفرست.")
                return Response.new("OK", status=200)

            # بررسی لینک اینستاگرام با تابع داخلی
            extracted = extract_instagram_id(text)
            if extracted:
                await send_telegram_message(env.BOT_TOKEN, chat_id, "لینک شما دریافت شد. در حال پردازش و دانلود... ⚡")
                
                # فرستادن لینک به صف پس‌زمینه کلودفلر
                queue_data = {
                    "chat_id": chat_id,
                    "url": text,
                    "extracted": extracted
                }
                await env.DOWNLOAD_QUEUE.send(queue_data)
            else:
                await send_telegram_message(env.BOT_TOKEN, chat_id, "لطفاً یک لینک معتبر اینستاگرام بفرستید. ❌")

        return Response.new("OK", status=200)
        
    except Exception as e:
        return Response.new(str(e), status=500)


async def queue_handler(batch, env, ctx):
    """
    این پروسس در پس‌زمینه اجرا میشه؛ رکوئست به RapidAPI می‌زنه و فایل رو آپلود می‌کنه.
    """
    from rapidapi_service import get_instagram_media
    
    for message in batch.messages:
        data = message.body
        chat_id = data.get("chat_id")
        url = data.get("url")
        
        try:
            # فراخوانی تابع اصلی دانلود
            await get_instagram_media(url, env=env, chat_id=chat_id)
        except Exception as e:
            await send_telegram_message(env.BOT_TOKEN, chat_id, "متأسفانه در دانلود این لینک خطایی رخ داد. ⚠️")
        finally:
            message.ack() # حذف پیام از صف پس از پایان موفقیت‌آمیز


async def send_telegram_message(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    await fetch(url, method="POST", headers={"Content-Type": "application/json"}, body=json.dumps(payload))
