# Serving / Config Spec

## 1. Назначение

Документ описывает запуск системы, конфигурацию окружения, секреты, модельные зависимости и ключевые runtime-параметры.

---

## 2. Способ запуска

Для PoC предполагается локальный и dev-запуск через:

- `docker-compose`
- `Makefile`
- переменные окружения
- единый backend entrypoint
- Telegram Bot как frontend-клиент

---

## 3. Основные компоненты запуска

- API Gateway
- Orchestrator
- Telegram Bot
- Redis
- Postgres
- Vector Store
- optional search service

---

## 4. Конфигурация

Конфигурация должна быть environment-based.

### Конфиг включает
- LLM provider settings
- model names
- embedding model settings
- retrieval settings
- reranker settings
- Redis / Postgres / Vector DB connection settings
- timeout settings
- retry policy
- cost limits
- feature flags:
  - `ENABLE_DEEP_RESEARCH`
  - `ENABLE_VERIFICATION`
  - `ENABLE_JIRA_TOOL`

---

## 5. Секреты

Секреты не должны храниться в репозитории.

### Используются через
- `.env`
- `.env.example`
- secret manager (в будущем)

### Примеры секретов
- LLM API key
- Telegram bot token
- Jira API token
- DB credentials

---

## 6. Версии моделей

Для воспроизводимости должны быть явно зафиксированы:

- версия основной LLM
- версия модели для embeddings
- версия reranker
- версия prompt templates
- версия retrieval index

---

## 7. Runtime ограничения

### Latency
- standard flow: p95 ≤ 5 сек
- deep research flow: p95 ≤ 12 сек
- tool timeout: 2–3 сек
- max workflow timeout: 15 сек

### Cost
- ограничение числа LLM вызовов на запрос
- ограничение числа tool calls
- ограничение max iterations
- prompt budget

---

## 8. Feature flags

Для PoC желательно иметь возможность отдельно включать и выключать:

- deep research mode
- Jira tool
- reranker
- verification step
- clarification loop

Это позволит отлаживать систему по частям.