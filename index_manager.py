# index_manager.py
import json
import logging

logger = logging.getLogger(__name__)

class IndexManager:
    def __init__(self, env=None):
        # INDEX_KV دیتابیس کلید/مقدار کلودفلر هست که جایگزین فایل متنی channel_index.json میشه
        self.kv_storage = getattr(env, "INDEX_KV", None) if env else None

    async def load_index(self):
        if self.kv_storage:
            try:
                data = await self.kv_storage.get("channel_index")
                return json.loads(data) if data else {}
            except Exception as e:
                logger.error(f"Error loading index from KV: {e}")
                return {}
        return {}

    async def save_index(self, index_data):
        if self.kv_storage:
            try:
                await self.kv_storage.put("channel_index", json.dumps(index_data, ensure_ascii=False))
                return True
            except Exception as e:
                logger.error(f"Error saving index to KV: {e}")
                return False
        return False
