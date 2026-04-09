from collections.abc import Sequence

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from db.postgres.models import ChatMessageORM
from gateway.schemas import ChatTurn


class ChatHistoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_message(
        self,
        *,
        session_id: str,
        user_id: str,
        username: str | None,
        role: str,
        content: str,
        is_from_telegram_history: bool = False,
    ) -> ChatMessageORM:
        message = ChatMessageORM(
            session_id=session_id,
            user_id=user_id,
            username=username,
            role=role,
            content=content,
            is_from_telegram_history=is_from_telegram_history,
        )
        self.session.add(message)
        await self.session.commit()
        await self.session.refresh(message)
        return message

    async def save_history_snapshot(
        self,
        *,
        session_id: str,
        user_id: str,
        username: str | None,
        history: list[ChatTurn],
    ) -> None:
        if not history:
            return

        for turn in history:
            self.session.add(
                ChatMessageORM(
                    session_id=session_id,
                    user_id=user_id,
                    username=username,
                    role=turn.role,
                    content=turn.content,
                    is_from_telegram_history=True,
                )
            )
        await self.session.commit()

    async def get_recent_messages(
        self,
        *,
        session_id: str,
        limit: int = 20,
    ) -> Sequence[ChatMessageORM]:
        stmt = (
            select(ChatMessageORM)
            .where(ChatMessageORM.session_id == session_id)
            .order_by(ChatMessageORM.created_at.desc(), ChatMessageORM.id.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        rows.reverse()
        return rows
    async def clear_session_history(self, *, session_id: str) -> int:
        stmt = delete(ChatMessageORM).where(ChatMessageORM.session_id == session_id)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount or 0