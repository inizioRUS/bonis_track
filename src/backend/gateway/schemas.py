from typing import Any

from pydantic import BaseModel, Field


class ChatTurn(BaseModel):
    role: str = Field(..., description="user | assistant | system")
    content: str = Field(..., min_length=1)


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1)
    session_id: str = Field(..., description="Telegram chat id")
    user_id: str
    username: str | None = None
    deep_research: bool = False
    is_eval: bool = False
    expected_doc_ids: list[str] = Field(default_factory=list)


class SourceItem(BaseModel):
    source: str
    title: str | None = None
    url: str | None = None
    score: float | None = None
    metadata: dict[str, Any] | None = None


class AskResponse(BaseModel):
    answer: str
    mode: str
    sources: list[SourceItem]
    uncertainty: str | None = None


class TelegramSetAsanaKeyRequest(BaseModel):
    user_id: str
    username: str | None = None
    session_id: str
    encrypted_api_key: str = Field(..., min_length=1)


class TelegramSetModeRequest(BaseModel):
    user_id: str
    username: str | None = None
    deep_research_enabled: bool


class TelegramGetModeRequest(BaseModel):
    user_id: str


class TelegramClearChatRequest(BaseModel):
    user_id: str
    session_id: str


class TelegramDeleteAsanaKeyRequest(BaseModel):
    user_id: str


class SimpleStatusResponse(BaseModel):
    status: str
    message: str


class TelegramModeResponse(BaseModel):
    status: str
    user_id: str
    deep_research_enabled: bool