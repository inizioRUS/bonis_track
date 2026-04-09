import httpx
from core.config import settings
class LLMClient:
    async def generate_answer(self, query: str, context: str) -> str:
        payload = {
            "system_prompt": (
                "Ты помощник для корпоративного поиска. "
                "Отвечай только на основе предоставленного контекста. "
                "Если данных недостаточно, явно скажи об этом. "
                "Не придумывай факты."
            ),
            "user_prompt": (
                f"Запрос пользователя:\n{query}\n\n"
                f"Контекст:\n{context}\n\n"
                "Сформируй краткий, полезный ответ на русском языке. "
                "Если есть неопределенность или конфликт данных, укажи это."
            ),
        }

        async with httpx.AsyncClient(timeout=settings.request_timeout_sec) as client:
            response = await client.post(settings.llm_url, json=payload)
            response.raise_for_status()
            data = response.json()

        return data.get("answer", "Не удалось сгенерировать ответ.")