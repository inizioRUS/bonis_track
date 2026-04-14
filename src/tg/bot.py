import asyncio
import logging
import os
from typing import Any, Optional

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from cryptography.fernet import Fernet

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000").rstrip("/")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "300"))
DEEP_RESEARCH_DEFAULT = os.getenv("DEEP_RESEARCH_DEFAULT", "false").lower() == "true"
FERNET_SECRET = os.getenv("FERNET_SECRET", "")

if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

if not FERNET_SECRET:
    raise RuntimeError("FERNET_SECRET is not set")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
fernet = Fernet(FERNET_SECRET.encode())

# In-memory состояние
user_modes: dict[int, bool] = {}
awaiting_asana_key: set[int] = set()


def get_user_mode(user_id: int) -> bool:
    return user_modes.get(user_id, DEEP_RESEARCH_DEFAULT)


def set_user_mode(user_id: int, enabled: bool) -> None:
    user_modes[user_id] = enabled


def main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    deep_enabled = get_user_mode(user_id)

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"Deep Research: {'ON' if deep_enabled else 'OFF'}")],
            [KeyboardButton(text="Asana API key")],
            [KeyboardButton(text="Очистить чат")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Введите запрос...",
    )


async def ask_backend(
    *,
    user_id: int,
    username: Optional[str],
    chat_id: int,
    text: str,
    deep_research: bool,
) -> dict[str, Any]:
    payload = {
        "query": text,
        "session_id": str(chat_id),
        "user_id": str(user_id),
        "username": username or "",
        "deep_research": deep_research,
    }

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.post(f"{BACKEND_URL}/ask", json=payload)
        response.raise_for_status()
        return response.json()


async def send_asana_key_to_backend(
    *,
    user_id: int,
    username: Optional[str],
    chat_id: int,
    asana_api_key: str,
) -> dict[str, Any]:
    encrypted_key = fernet.encrypt(asana_api_key.encode()).decode()

    payload = {
        "user_id": str(user_id),
        "username": username or "",
        "session_id": str(chat_id),
        "encrypted_api_key": encrypted_key,
    }

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.post(f"{BACKEND_URL}/setasana", json=payload)
        response.raise_for_status()
        return response.json()


async def clear_chat_on_backend(
    *,
    user_id: int,
    chat_id: int,
) -> dict[str, Any]:
    payload = {
        "user_id": str(user_id),
        "session_id": str(chat_id),
    }

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.post(f"{BACKEND_URL}/clearchat", json=payload)
        response.raise_for_status()
        return response.json()


def format_answer(data: dict[str, Any]) -> str:
    answer = data.get("answer") or data.get("message") or "Пустой ответ от backend."
    sources = data.get("sources") or []
    mode = data.get("mode")
    uncertainty = data.get("uncertainty")

    parts = [answer]

    if mode:
        parts.append(f"\n\nРежим: `{mode}`")

    if uncertainty:
        parts.append(f"\nНеопределенность: {uncertainty}")

    if sources:
        parts.append("\n\nИсточники:")
        for idx, source in enumerate(sources[:10], start=1):
            if isinstance(source, dict):
                title = source.get("title") or source.get("source") or f"source_{idx}"
                url = source.get("url")
                if url:
                    parts.append(f"\n{idx}. {title} — {url}")
                else:
                    parts.append(f"\n{idx}. {title}")
            else:
                parts.append(f"\n{idx}. {source}")

    return "".join(parts)


@dp.message(Command("start"))
async def cmd_start(message: Message) -> None:
    if not message.from_user:
        return

    text = (
        "Привет! Я бот для PoC корпоративного поиска.\n\n"
        "Что умею:\n"
        "- обычный режим\n"
        "- deep research\n"
        "- сохранение Asana API key\n"
        "- очистка сессии чата\n\n"
        "Можешь использовать команды или кнопки."
    )
    await message.answer(text, reply_markup=main_keyboard(message.from_user.id))


@dp.message(Command("help"))
async def cmd_help(message: Message) -> None:
    if not message.from_user:
        return

    text = (
        "Я отправляю твой запрос в backend RAG-системы.\n\n"
        "Команды:\n"
        "/deep_on — включить deep research\n"
        "/deep_off — выключить deep research\n"
        "/mode — показать текущий режим\n"
        "/clear — очистить контекст чата\n"
        "/asana_key — ввести Asana API key\n\n"
        "Либо используй кнопки над строкой ввода."
    )
    await message.answer(text, reply_markup=main_keyboard(message.from_user.id))


@dp.message(Command("deep_on"))
async def cmd_deep_on(message: Message) -> None:
    if not message.from_user:
        return

    set_user_mode(message.from_user.id, True)
    await message.answer(
        "Deep research включён.",
        reply_markup=main_keyboard(message.from_user.id),
    )


@dp.message(Command("deep_off"))
async def cmd_deep_off(message: Message) -> None:
    if not message.from_user:
        return

    set_user_mode(message.from_user.id, False)
    await message.answer(
        "Deep research выключён.",
        reply_markup=main_keyboard(message.from_user.id),
    )


@dp.message(Command("mode"))
async def cmd_mode(message: Message) -> None:
    if not message.from_user:
        return

    enabled = get_user_mode(message.from_user.id)
    await message.answer(
        f"Текущий режим: {'deep research' if enabled else 'standard'}",
        reply_markup=main_keyboard(message.from_user.id),
    )


@dp.message(Command("clear"))
async def cmd_clear(message: Message) -> None:
    if not message.from_user:
        return

    wait_msg = await message.answer("Очищаю контекст чата...")
    try:
        data = await clear_chat_on_backend(
            user_id=message.from_user.id,
            chat_id=message.chat.id,
        )
        result = data.get("message") or "Контекст чата очищен."
        await wait_msg.edit_text(
            result,
        )
        await message.answer("Выбери действие:", reply_markup=main_keyboard(message.from_user.id))
    except httpx.HTTPStatusError as exc:
        logger.exception("Clear chat backend error")
        await wait_msg.edit_text(
            f"Ошибка backend: {exc.response.status_code}\n{exc.response.text[:1000]}",
        )
        await message.answer("Выбери действие:", reply_markup=main_keyboard(message.from_user.id))
    except httpx.TimeoutException:
        logger.exception("Clear chat timeout")
        await wait_msg.edit_text(
            "Backend не ответил вовремя при очистке чата.",
        )
        await message.answer("Выбери действие:", reply_markup=main_keyboard(message.from_user.id))
    except Exception:
        logger.exception("Unexpected clear chat error")
        await wait_msg.edit_text(
            "Не удалось очистить чат.",
        )
        await message.answer("Выбери действие:", reply_markup=main_keyboard(message.from_user.id))


@dp.message(Command("asana_key"))
async def cmd_asana_key(message: Message) -> None:
    if not message.from_user:
        return

    awaiting_asana_key.add(message.from_user.id)
    await message.answer(
        "Отправь следующим сообщением Asana API key.\n"
        "Он будет зашифрован перед отправкой в backend.",
        reply_markup=main_keyboard(message.from_user.id),
    )


@dp.message(F.text.startswith("Deep Research:"))
async def toggle_deep_research_button(message: Message) -> None:
    if not message.from_user:
        return

    current = get_user_mode(message.from_user.id)
    new_value = not current
    set_user_mode(message.from_user.id, new_value)

    await message.answer(
        f"Deep Research {'включён' if new_value else 'выключен'}",
        reply_markup=main_keyboard(message.from_user.id),
    )


@dp.message(F.text == "Asana API key")
async def asana_key_button(message: Message) -> None:
    if not message.from_user:
        return

    awaiting_asana_key.add(message.from_user.id)
    await message.answer(
        "Отправь следующим сообщением Asana API key.\n"
        "Он будет зашифрован перед отправкой в backend.",
        reply_markup=main_keyboard(message.from_user.id),
    )


@dp.message(F.text == "Очистить чат")
async def clear_chat_button(message: Message) -> None:
    if not message.from_user:
        return

    wait_msg = await message.answer("Очищаю контекст чата...")
    try:
        data = await clear_chat_on_backend(
            user_id=message.from_user.id,
            chat_id=message.chat.id,
        )
        result = data.get("message") or "Контекст чата очищен."
        await wait_msg.edit_text(
            result,
        )
        await message.answer("Выбери действие:", reply_markup=main_keyboard(message.from_user.id))
    except httpx.HTTPStatusError as exc:
        logger.exception("Clear chat backend error")
        await wait_msg.edit_text(
            f"Ошибка backend: {exc.response.status_code}\n{exc.response.text[:1000]}",
        )
        await message.answer("Выбери действие:", reply_markup=main_keyboard(message.from_user.id))
    except httpx.TimeoutException:
        logger.exception("Clear chat timeout")
        await wait_msg.edit_text(
            "Backend не ответил вовремя при очистке чата.",
        )
        await message.answer("Выбери действие:", reply_markup=main_keyboard(message.from_user.id))
    except Exception:
        logger.exception("Unexpected clear chat error")
        await wait_msg.edit_text(
            "Не удалось очистить чат.",
        )
        await message.answer("Выбери действие:", reply_markup=main_keyboard(message.from_user.id))


@dp.message(F.text.startswith("/"))
async def unknown_command(message: Message) -> None:
    await message.answer(
        "Неизвестная команда. Используй /help.",
        reply_markup=main_keyboard(message.from_user.id) if message.from_user else None,
    )


@dp.message(F.text)
async def handle_text(message: Message) -> None:
    if not message.from_user or not message.text:
        return

    if message.from_user.id in awaiting_asana_key:
        wait_msg = await message.answer("Сохраняю Asana API key...")
        try:
            await send_asana_key_to_backend(
                user_id=message.from_user.id,
                username=message.from_user.username,
                chat_id=message.chat.id,
                asana_api_key=message.text.strip(),
            )
            awaiting_asana_key.discard(message.from_user.id)
            await wait_msg.edit_text(
                "Asana API key сохранён.",
            )
            await message.answer("Выбери действие:", reply_markup=main_keyboard(message.from_user.id))
        except httpx.HTTPStatusError as exc:
            logger.exception("Asana key backend error")
            await wait_msg.edit_text(
                f"Ошибка backend: {exc.response.status_code}\n{exc.response.text[:1000]}",
            )
            await message.answer("Выбери действие:", reply_markup=main_keyboard(message.from_user.id))
        except httpx.TimeoutException:
            logger.exception("Asana key timeout")
            await wait_msg.edit_text(
                "Backend не ответил вовремя при сохранении ключа.",
            )
            await message.answer("Выбери действие:", reply_markup=main_keyboard(message.from_user.id))
        except Exception:
            logger.exception("Unexpected Asana key error")
            await wait_msg.edit_text(
                "Не удалось сохранить Asana API key.",
            )
            await message.answer("Выбери действие:", reply_markup=main_keyboard(message.from_user.id))
        return

    deep_research = get_user_mode(message.from_user.id)
    wait_msg = await message.answer("Думаю...")

    try:
        data = await ask_backend(
            user_id=message.from_user.id,
            username=message.from_user.username,
            chat_id=message.chat.id,
            text=message.text,
            deep_research=deep_research,
        )
        formatted = format_answer(data)
        await wait_msg.edit_text(
            formatted,
        )
        await message.answer("Выбери действие:", reply_markup=main_keyboard(message.from_user.id))
    except httpx.HTTPStatusError as exc:
        logger.exception("Backend returned error status")
        await wait_msg.edit_text(
            f"Ошибка backend: {exc.response.status_code}\n{exc.response.text[:1000]}",
        )
        await message.answer("Выбери действие:", reply_markup=main_keyboard(message.from_user.id))
    except httpx.TimeoutException:
        logger.exception("Backend timeout")
        await wait_msg.edit_text(
            "Backend не ответил вовремя.",
        )
        await message.answer("Выбери действие:", reply_markup=main_keyboard(message.from_user.id))
    except Exception as exc:
        logger.exception("Unexpected error")
        await wait_msg.edit_text(
            f"Непредвиденная ошибка: {type(exc).__name__}",
        )
        await message.answer("Выбери действие:", reply_markup=main_keyboard(message.from_user.id))


async def main() -> None:
    logger.info("Starting Telegram bot")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())