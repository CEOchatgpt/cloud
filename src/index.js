export default {
  // ۱. مدیریت رکوئست‌های زنده تلگرام (Webhook)
  async fetch(request, env, ctx) {
    if (request.method !== 'POST') {
      return new Response('Method Not Allowed', { status: 405 });
    }

    try {
      const update = await request.json();
      ctx.waitUntil(handleTelegramUpdate(update, env));
      return new Response('OK', { status: 200 });
    } catch (err) {
      return new Response(err.message, { status: 500 });
    }
  },

  // ۲. پردازش پس‌زمینه لینک‌ها با سرور رندر تو
  async queue(batch, env, ctx) {
    for (const message of batch.messages) {
      try {
        await processDownloadQueue(message.body, env);
        message.ack(); // حذف موفقیت‌آمیز از صف
      } catch (error) {
        console.error("Queue execution failed:", error);
      }
    }
  }
};

// --- توابع کمکی ربات ---

async function sendToTelegram(method, payload, token) {
  return fetch(`https://api.telegram.org/bot${token}/${method}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  }).then(res => res.json());
}

async function handleTelegramUpdate(update, env) {
  if (!update.message || !update.message.text) return;

  const chatId = update.message.chat.id;
  const text = update.message.text.trim();

  if (text === '/start') {
    await sendToTelegram('sendMessage', {
      chat_id: chatId,
      text: "سلام آریان عزیز! 🚀\nلینک پست یا ریلز اینستاگرام رو برام بفرست تا با موتور اختصاصی خودم برات دانلودش کنم."
    }, env.BOT_TOKEN);
    return;
  }

  // تشخیص لینک‌های اینستاگرام
  const instaRegex = /https:\/\/www\.instagram\.com\/(p|reel|stories|tv)\/[A-Za-z0-9_-]+/i;
  const match = text.match(instaRegex);

  if (match) {
    const cleanUrl = match[0];
    const contentType = match[1]; // p, reel, etc.

    // چک کردن دیتابیس KV برای ارسال فوری (کش)
    const cached = await env.INDEX_KV.get(`idx:${cleanUrl}`);
    if (cached) {
      await sendToTelegram('sendMessage', { chat_id: chatId, text: "این ویدیو قبلاً دانلود شده، در حال فوروارد سریع... ⚡" }, env.BOT_TOKEN);
      const cacheData = JSON.parse(cached);
      
      for (const msgId of cacheData.message_ids) {
        await sendToTelegram('forwardMessage', {
          chat_id: chatId,
          from_chat_id: cacheData.channel_id,
          message_id: msgId
        }, env.BOT_TOKEN);
      }
      return;
    }

    // اگر جدید بود: ارسال لودینگ و سپردن کار به صف
    await sendToTelegram('sendMessage', { chat_id: chatId, text: "لینک دریافت شد. در حال آماده‌سازی فایل در صف دانلود... ⏳" }, env.BOT_TOKEN);
    
    await env.DOWNLOAD_QUEUE.send({
      chat_id: chatId,
      url: cleanUrl,
      type: contentType
    });
  } else {
    await sendToTelegram('sendMessage', { chat_id: chatId, text: "لطفاً یک لینک معتبر از اینستاگرام بفرست! ❌" }, env.BOT_TOKEN);
  }
}

// موتور ارتباط با API رندر و ارسال فایل به کانال دیتابیس شما
async function processDownloadQueue(task, env) {
  const { chat_id, url, type } = task;
  
  // پیدا کردن آیدی کانال هدف بر اساس نوع محتوا
  let targetChannel = env.POST_CHANNEL_ID;
  if (type === 'reel') targetChannel = env.REEL_CHANNEL_ID;
  if (type === 'stories') targetChannel = env.STORY_CHANNEL_ID;

  try {
    // ۱. فراخوانی سرور پایتون شما روی رندر
    const scraperUrl = `https://insta-scraper-1bus.onrender.com/extract?url=${encodeURIComponent(url)}`;
    const res = await fetch(scraperUrl);
    if (!res.ok) throw new Error("Scraper server error");
    
    const result = await res.json();
    if (!result.success || !result.data || result.data.length === 0) {
      throw new Error("No media found from scraper");
    }

    const savedMessageIds = [];

    // ۲. چرخش روی تمام رسانه‌های استخراج شده (پشتیبانی از آلبوم‌ها)
    for (const item of result.data) {
      const isVideo = item.is_video;
      const uploadMethod = isVideo ? 'sendVideo' : 'sendPhoto';
      const payloadKey = isVideo ? 'video' : 'photo';

      const channelResponse = await sendToTelegram(uploadMethod, {
        chat_id: targetChannel,
        [payloadKey]: item.url,
        caption: `📥 Saved from: ${url}`
      }, env.BOT_TOKEN);

      if (channelResponse && channelResponse.ok) {
        savedMessageIds.push(channelResponse.result.message_id);
      }
    }

    if (savedMessageIds.length > 0) {
      // ۳. ذخیره آرایه آیدی پیام‌ها در دیتابیس KV برای کش دفعه بعد
      await env.INDEX_KV.put(`idx:${url}`, JSON.stringify({
        message_ids: savedMessageIds,
        channel_id: targetChannel
      }));

      // ۴. فوروارد نهایی فایل‌ها برای کاربر
      for (const msgId of savedMessageIds) {
        await sendToTelegram('forwardMessage', {
          chat_id: chat_id,
          from_chat_id: targetChannel,
          message_id: msgId
        }, env.BOT_TOKEN);
      }
    } else {
      throw new Error("Failed to send any media to Telegram channel DB");
    }

  } catch (error) {
    console.error("Downloader engine error:", error);
    await sendToTelegram('sendMessage', { chat_id: chat_id, text: "متاسفانه در استخراج یا ارسال فایل خطایی رخ داد. ⚠️" }, env.BOT_TOKEN);
  }
}