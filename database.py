# database.py
import logging
import json

logger = logging.getLogger(__name__)

async def get_user_mode(user_id: int, env) -> str:
    """دریافت حالت کاربر از دیتابیس KV کلودفلر (سریع و بدون دردسر)"""
    if env and getattr(env, "INDEX_KV", None):
        try:
            mode = await env.INDEX_KV.get(f"user_mode:{user_id}")
            return mode if mode else "album"
        except Exception as e:
            logger.error(f"Error getting user mode: {e}")
            return "album"
    return "album"

async def set_user_mode(user_id: int, mode: str, env) -> bool:
    """ذخیره حالت جدید کاربر در دیتابیس KV کلودفلر"""
    if env and getattr(env, "INDEX_KV", None):
        try:
            await env.INDEX_KV.put(f"user_mode:{user_id}", mode)
            logger.info(f"User {user_id} mode set to {mode}")
            return True
        except Exception as e:
            logger.error(f"Error setting user mode: {e}")
            return False
    return False
