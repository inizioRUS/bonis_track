from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.postgres.models import UserSettingsORM


class UserSettingsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create_user(
        self,
        *,
        user_id: str,
        username: str | None,
    ) -> UserSettingsORM:
        stmt = select(UserSettingsORM).where(UserSettingsORM.user_id == user_id)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()

        if user is not None:
            if user.username != username:
                user.username = username
                await self.session.commit()
                await self.session.refresh(user)
            return user

        user = UserSettingsORM(
            user_id=user_id,
            username=username,
            deep_research_enabled=False,
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def get_user_by_user_id(self, *, user_id: str) -> UserSettingsORM | None:
        stmt = select(UserSettingsORM).where(UserSettingsORM.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def set_asana_api_key(
        self,
        *,
        user_id: str,
        username: str | None,
        asana_api_key_encrypted: str,
    ) -> UserSettingsORM:
        user = await self.get_or_create_user(user_id=user_id, username=username)
        user.asana_api_key_encrypted = asana_api_key_encrypted
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def clear_asana_api_key(self, *, user_id: str) -> UserSettingsORM | None:
        user = await self.get_user_by_user_id(user_id=user_id)
        if user is None:
            return None

        user.asana_api_key_encrypted = None
        await self.session.commit()
        await self.session.refresh(user)
        return user
