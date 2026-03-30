md
# Tools / APIs Spec

## 1. Назначение

Tool layer предоставляет orchestrator’у контролируемый доступ к внешним источникам данных и прикладным инструментам.

В рамках PoC tools используются для:
- retrieval по поисковому контуру
- получения актуальных структурированных данных из Jira API

Все tool calls должны выполняться только через orchestrator / tool layer.

---

## 2. Поддерживаемые tools в PoC

### 2.1 Search / Retrieval Tool
Используется для поиска по индексированным документам(описан в retriver).

### 2.2 Jira Tool
Используется для получения структурированных данных:
- тикеты
- статусы
- исполнители
- связи между задачами
- история изменений
- служебные поля

---

## 3. Контракт tool call

Каждый tool должен иметь:

- явный input schema
- явный output schema
- error schema
- timeout policy
- retry policy
- side-effect policy

---

## 4. Search Tool Contract

### Вход
- `query: string`
- `top_k: int`
- `mode: keyword | semantic | hybrid`
- `filters: object`
- `trace_id: string`

### Выход
- `items: list`
- `scores: list`
- `used_strategy: string`
- `retrieval_trace: object`
- `latency_ms: int`

---

## 5. Jira Tool Contract

### Вход
- `query: string`
- `entity_type: issue | user | link | status`
- `filters: object`
- `trace_id: string`

### Выход
- `items: list`
- `source: jira`
- `request_meta: object`
- `latency_ms: int`

Все результаты Jira Tool должны быть преобразованы в `evidence objects`.

---

## 6. Ошибки

### Типовые ошибки
- auth error
- timeout
- 4xx response
- 5xx response
- malformed payload
- partial response
- unsupported arguments

### Нормализация ошибок
Ошибки не должны пробрасываться в сыром виде в LLM.  
Tool layer обязан:
- нормализовать ошибку в стандартный формат
- указать `error_type`
- указать `recoverable: true|false`

---

## 7. Timeout policy

### PoC-ограничения
- Search Tool timeout: до 2 секунд
- Jira Tool timeout: до 3 секунд
- max tool retries: 1–2 для transient failures

### Retry only for
- network timeout
- temporary unavailable
- transient 5xx errors

### No retry for
- invalid request
- auth errors
- schema violations

---

## 8. Side effects policy

Для PoC все tools работают в **read-only режиме**.

### Запрещено
- создавать или изменять Jira-задачи
- менять статусы
- выполнять действия от имени пользователя
- отправлять команды во внешние системы

---

## 9. Защита

### Базовые меры защиты
- allowlist доступных tools
- schema validation входных аргументов
- sanitize аргументов перед отправкой
- ограничение числа вызовов на запрос
- audit logging каждого tool call
- retrieval/tool content считается untrusted input

### Prompt injection защита
- данные из tools не могут менять system instructions
- tool output не интерпретируется как команды
- оркестратор валидирует дальнейшие действия после tool response