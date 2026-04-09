import os
import traceback

import redis.asyncio as redis
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db.postgres.chat_history_service import ChatHistoryService
from db.postgres.postgres import get_db_session
from db.postgres.user_settings_service import UserSettingsService
from db.redis.redis import get_redis
from db.redis.session_metadata_service import SessionMetadataService
from gateway.schemas import AskRequest, AskResponse
from lib.multi_agent.agents.orchestrator.workflow import RAGWorkflow
from pydantic import BaseModel, Field

router = APIRouter()

FERNET_SECRET = os.getenv("FERNET_SECRET", "")
if not FERNET_SECRET:
    raise RuntimeError("FERNET_SECRET is not set")

fernet = Fernet(FERNET_SECRET.encode())


class TelegramSetAsanaKeyRequest(BaseModel):
    user_id: str
    username: str | None = None
    session_id: str
    encrypted_api_key: str = Field(..., min_length=1)


class TelegramClearChatRequest(BaseModel):
    user_id: str
    session_id: str


class SimpleStatusResponse(BaseModel):
    status: str
    message: str


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/ask", response_model=AskResponse)
async def ask(
    request: AskRequest,
    db_session: AsyncSession = Depends(get_db_session),
    redis_client: redis.Redis = Depends(get_redis),
) -> AskResponse:
    try:
        postgres_client = ChatHistoryService(db_session)
        user_settings_service = UserSettingsService(db_session)
        redis_metadata = SessionMetadataService(redis_client)

        await user_settings_service.get_or_create_user(
            user_id=request.user_id,
            username=request.username,
        )

        await postgres_client.save_message(
            session_id=request.session_id,
            user_id=request.user_id,
            username=request.username,
            content=request.query,
            role="user",
        )

        history = await postgres_client.get_recent_messages(
            session_id=request.session_id,
            limit=20,
        )
        user = await user_settings_service.get_user_by_user_id(user_id=request.user_id)

        asana_api_key = fernet.decrypt(
            user.asana_api_key_encrypted.encode()
        ).decode()

        workflow = RAGWorkflow(redis_metadata, asana_api_key)
        workflow_result = await workflow.run(
            session_id=request.session_id,
            user_id=request.user_id,
            username=request.username,
            query=request.query,
            deep_research=request.deep_research,
            redis_client=redis_metadata,
            history=[
                {
                    "role": msg.role,
                    "content": msg.content,
                }
                for msg in history
            ],
        )

        answer = workflow_result.get("final_answer", "Не удалось подготовить ответ.")
        print(workflow_result)
        sources = workflow_result.get("final_sources", [])

        await postgres_client.save_message(
            session_id=request.session_id,
            user_id=request.user_id,
            username=request.username,
            content=answer,
            role="assistant",
        )

        return AskResponse(
            answer=answer,
            mode="multi_agent",
            sources=sources,
        )

    except Exception as exc:
        tb = traceback.format_exc()
        print(tb)
        print(exc)
        raise HTTPException(
            status_code=500,
            detail=f"workflow_error: {type(exc).__name__}",
        ) from exc


@router.post("/setasana", response_model=SimpleStatusResponse)
async def set_asana_key(
    request: TelegramSetAsanaKeyRequest,
    db_session: AsyncSession = Depends(get_db_session),
) -> SimpleStatusResponse:
    try:
        user_settings_service = UserSettingsService(db_session)

        try:
            decrypted_api_key = fernet.decrypt(
                request.encrypted_api_key.encode()
            ).decode()
        except InvalidToken as exc:
            raise HTTPException(status_code=400, detail="Invalid encrypted_api_key") from exc

        # Сохраняем в БД в зашифрованном виде
        server_encrypted_key = fernet.encrypt(decrypted_api_key.encode()).decode()

        await user_settings_service.set_asana_api_key(
            user_id=request.user_id,
            username=request.username,
            asana_api_key_encrypted=server_encrypted_key,
        )

        return SimpleStatusResponse(
            status="ok",
            message="Asana API key saved",
        )

    except HTTPException:
        raise
    except Exception as exc:
        tb = traceback.format_exc()
        print(tb)
        print(exc)
        raise HTTPException(
            status_code=500,
            detail=f"setasana_error: {type(exc).__name__}",
        ) from exc


@router.post("/clearchat", response_model=SimpleStatusResponse)
async def clear_chat(
    request: TelegramClearChatRequest,
    db_session: AsyncSession = Depends(get_db_session),
    redis_client: redis.Redis = Depends(get_redis),
) -> SimpleStatusResponse:
    try:
        postgres_client = ChatHistoryService(db_session)
        redis_metadata = SessionMetadataService(redis_client)

        deleted_count = await postgres_client.clear_session_history(
            session_id=request.session_id,
        )

        deleted_redis = await redis_metadata.clear_session(
            session_id=request.session_id,
            user_id=request.user_id,
        )

        return SimpleStatusResponse(
            status="ok",
            message=(
                f"Контекст чата очищен. "
                f"Удалено сообщений: {deleted_count}. "
                f"Redis очищен: {deleted_redis}"
            ),
        )

    except Exception as exc:
        tb = traceback.format_exc()
        print(tb)
        print(exc)
        raise HTTPException(
            status_code=500,
            detail=f"clearchat_error: {type(exc).__name__}",
        ) from exc