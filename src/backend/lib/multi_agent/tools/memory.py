from __future__ import annotations

import traceback
from typing import Any

from db.redis.session_metadata_service import SessionMetadataService


class MemoryTool:
    def __init__(self, redis_client: SessionMetadataService):
        self.redis_client = redis_client

    async def get(self, session_id, user_id):
        return (await self.redis_client.get_metadata(session_id=session_id, user_id=user_id))

    async def write(
            self,
            *,
            session_id, user_id, payload
    ) -> dict[str, Any]:
        try:
            await self.redis_client.upsert_metadata(session_id=session_id, user_id=user_id, payload=payload)
            print("ok")
            return {"status": "ok"}
        except Exception as e:
            print(e)
            tb = traceback.format_exc()
            print(tb)
            return {"status": "error"}
