# Memory / Context Spec

## 1. Назначение

Memory / Context слой отвечает за хранение состояния текущего workflow, контекста сессии и истории взаимодействия пользователя с системой.

Основная цель:
- не терять пользовательский контекст
- не переполнять LLM лишней историей
- управлять тем, что именно передается в model context

---

## 2. Разделение на State и Memory

### State
Краткоживущий runtime-контекст выполнения запроса.

### Memory
Долгоживущая память сессии и диалога.

---

## 3. Session State

State хранится в Redis или in-memory store для PoC.

### Содержит
- `request_id`
- `session_id`
- `workflow_id`
- execution mode
- user context
- current step
- subtasks
- visited queries
- intermediate evidence
- tool call history
- retry counters
- clarification history
- verification status
- accumulated context

### Принцип
После каждого шага orchestrator обязан обновить state.

---

## 4. Memory policy

Memory хранится в Postgres.

### Содержит
- историю сообщений
- session summaries
- важные пользовательские уточнения
- финальные ответы
- краткий пользовательский профиль в рамках системы

### Политика памяти
- не хранить лишние сырые промежуточные данные бессрочно
- важные уточнения сохранять
- длинную историю сворачивать в summary
- разделять runtime-state и long-term memory

---

## 5. Context budget

LLM-контекст ограничен, поэтому должна применяться budget policy.

### Основные правила
- полная история диалога не передается целиком
- используется summary предыдущей сессии
- retrieval context ограничивается `top-k`
- в prompt попадает только наиболее релевантный и проверенный контекст

### Приоритет контекста
1. system instructions
2. execution plan
3. verified evidence
4. user/session context
5. session summary
6. recent chat turns

---

## 6. Summarization policy

Если история переписки растет:
- старые сообщения агрегируются в session summary
- summary обновляется при завершении workflow
- сырые сообщения хранятся отдельно, но не всегда попадают в prompt

---

## 7. Clarification handling

Если система задает уточняющий вопрос:
- вопрос и ответ пользователя сохраняются в memory
- релевантная часть также дублируется в state
- дальнейшие LLM вызовы получают уже обновленный user context

---

## 8. Ограничения

### Технические
- max context size
- max history length
- ограничение на число recent turns в prompt

### Логические
- memory не должна напрямую управлять execution flow
- память не должна подменять retrieval
- непроверенный long-term context не должен иметь больший приоритет, чем verified evidence