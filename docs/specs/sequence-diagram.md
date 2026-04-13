# Sequence Diagram

Документ описывает один end-to-end сценарий работы системы.

Сценарий:
**Пользователь в Telegram просит найти статью на Habr и создать по ней задачи в Asana.**

---

## Sequence Diagram

```mermaid
sequenceDiagram
    actor User
    participant TG as Telegram Bot
    participant GW as API Gateway
    participant ORCH as Orchestrator
    participant MEM as Memory Layer
    participant PLAN as Planner Agent
    participant RET as Retriever Tool
    participant HABR as Habr Tool
    participant ASANA as Asana API
    participant VER as Verifier Agent
    participant WR as Writer Agent
    participant PG as Postgres
    participant RD as Redis

    User->>TG: "Найди статью на Habr про RAG и создай задачи в Asana"
    TG->>GW: POST /ask (query, user_id, session_id, history)
    GW->>ORCH: start workflow

    ORCH->>RD: load session metadata
    ORCH->>PG: load chat history / memory
    PG-->>ORCH: messages / memory hits
    RD-->>ORCH: session metadata

    ORCH->>MEM: fetch memory context
    MEM-->>ORCH: memory_hits

    ORCH->>PLAN: build next-step plan(state)
    PLAN-->>ORCH: plan(JSON)

    ORCH->>RET: retriever.search(article query)
    RET-->>ORCH: candidate docs

    ORCH->>HABR: habr.get_article_text(url)
    HABR-->>ORCH: full article text

    ORCH->>VER: verify sufficiency(state)
    VER-->>ORCH: enough evidence, execution allowed

    ORCH->>ASANA: create_task(...) x N
    ASANA-->>ORCH: created task ids / urls

    ORCH->>VER: verify final state
    VER-->>ORCH: ready_for_final_response = true

    ORCH->>WR: write final answer(state)
    WR-->>ORCH: final answer + sources

    ORCH->>PG: save user/assistant messages
    ORCH->>RD: update session metadata

    ORCH-->>GW: final response
    GW-->>TG: answer
    TG-->>User: final message with sources
```
Пояснение к сценарию
1. Вход

Пользователь отправляет запрос в Telegram-бот.

2. Gateway

Gateway принимает запрос и передает его в orchestrator вместе с:

user_id
session_id
историей сообщений
параметрами режима
3. Memory / session loading

Orchestrator поднимает:

metadata из Redis
историю чата из Postgres
memory context из memory layer
4. Planning

Planner Agent анализирует текущее состояние и определяет:

какой article query использовать,
какие retrieval steps нужны,
нужны ли execution steps.
5. Retrieval

Orchestrator вызывает retriever и получает кандидатов документов.
Если релевантный Habr URL найден, отдельно загружается полный текст статьи.

6. Verification before execution

Verifier проверяет:

действительно ли статья найдена,
хватает ли контекста,
безопасно ли переходить к Asana execution.
7. Asana execution

Если evidence достаточен, orchestrator выполняет создание задач в Asana.

8. Final verification

После execution verifier повторно оценивает состояние и подтверждает, что можно писать финальный ответ.

9. Writing

Writer Agent формирует финальное сообщение для пользователя.

10. Persistence

История чата сохраняется в Postgres, metadata — в Redis.
