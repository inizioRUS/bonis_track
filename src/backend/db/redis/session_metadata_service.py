import json
from datetime import datetime, timezone

import redis.asyncio as redis

from core.config import settings


class SessionMetadataService:
    def __init__(self, redis_client: redis.Redis) -> None:
        self.redis = redis_client

    @staticmethod
    def build_key(session_id: str, user_id: str) -> str:
        return f"chat_session:{session_id}:user:{user_id}"

    async def upsert_metadata(
        self,
        *,
        session_id: str,
        user_id: str,
        payload
    ) -> None:
        key = self.build_key(session_id, user_id)

        payload.append({"session_id": session_id})
        payload.append({"user_id": user_id})

        await self.redis.set(
            key,
            json.dumps(payload, ensure_ascii=False),
            ex=settings.redis_session_ttl_sec,
        )

    async def get_metadata(self, *, session_id: str, user_id: str) -> dict | None:
        key = self.build_key(session_id, user_id)
        raw = await self.redis.get(key)
        if not raw:
            return None
        return json.loads(raw)

    async def clear_session(self, *, session_id: str, user_id: str) -> bool:
        """
        Удаляет данные сессии из Redis
        """
        key = self.build_key(session_id, user_id)
        result = await self.redis.delete(key)
        return result > 0