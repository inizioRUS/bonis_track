# System Design

## 1. Цель документа

Зафиксировать архитектуру PoC-системы до начала разработки: состав модулей, их взаимодействие, execution flow, контракты, ограничения и точки контроля качества.

PoC-система решает задачу продвинутого корпоративного поиска по внутренним артефактам с использованием RAG и multi-agent orchestration. Основной акцент делается на взаимодействии с LLM, контроле качества ответа, механизмах защиты, fallback-логике и проверяемости результата.

---

## 2. Scope PoC

### In scope
- Поиск по документным источникам
- RAG pipeline
- Multi-agent orchestration для сложных запросов
- Agent cycle с накоплением контекста и поэтапным уточнением запроса
- Возможность выбора deep research mode пользователем
- Подключение минимум одного external API tool
- Verification step перед финальным ответом
- Базовые механизмы observability, guardrails и fallback

### Out of scope
- Полноценный production-grade ACL
- Полноценная online learning / RL-оптимизация
- Широкий набор внешних API
- Полноценный UI с развитой аналитикой
- Автоматическое выполнение внешних действий от имени пользователя

---

## 3. Ключевые архитектурные решения

1. **Архитектура строится вокруг orchestrator-first подхода**  
   Основной контроль execution flow находится в orchestrator.

2. **LLM используется как компонент внутри  workflow**  
   Модель применяется для planning, decomposition, synthesis, verification и уточнения контекста.

3. **Orchestrator работает как agent cycle**  
   В базовом режиме orchestrator запускает циклический процесс: анализ запроса → вызов tool/retrieval → обновление state → уточнение контекста → проверка для учтонения информации -> формирование ответа.  
   В режиме deep research orchestrator дополнительно строит план исследования, управляет подзадачами и выполняет несколько итераций поиска и доуточнения информации.

4. **Deep research является явным режимом работы системы**  
   Этот режим может быть выбран пользователем явно. Дополнительно planner/orchestrator может рекомендовать его для длинных, составных или неоднозначных запросов.

5. **Retrieval реализуется как tool/API с явным контрактом**  
   Поиск не является “скрытой” внутренней магией. Для получения документов или кандидатов используется retrieval tool с понятным API: запрос, параметры поиска, фильтры, top-k, тип retrieval.

6. **Все найденные данные приводятся к единому evidence schema**  
   Документы, результаты Jira API и промежуточные находки нормализуются в единый формат, пригодный для анализа и верификации.

7. **Ответ проходит verification step перед возвратом пользователю**  
   Финальный ответ должен быть проверен на groundedness, freshness и наличие конфликтов между источниками.

8. **Guardrails и fallback заложены на уровне system design**  
   Неуспех отдельного шага не должен ломать весь pipeline; система должна уметь деградировать до более простого режима.
---

## 4. Высокоуровневая архитектура

Система состоит из следующих контуров:

- `gateway` — входной API-слой
- `orchestrator` — управление workflow и agent cycle
- `agents` — planner / analyst / verifier / writer
- `retrieval tool` — поиск по индексированным данным
- `tool layer` — внешние API tools
- `state & memory layer` — состояние выполнения, профиль пользователя и история сессии
- `storage layer` — Postgres / Redis / Vector Store
- `observability layer` — логи, метрики, traces, audit

---

## 5. Список модулей и их роли

### 5.1 Gateway
Роль:
- прием пользовательских запросов
- аутентификация
- rate limiting
- request/session correlation
- передача запроса и метаданных в orchestrator
- прием пользовательского флага/параметра `deep_research=true|false`

Не отвечает за:
- бизнес-логику поиска
- agent planning
- retrieval
- verification

---

### 5.2 Orchestrator
Роль:
- определение execution mode
- запуск workflow
- управление agent cycle
- контроль порядка шагов
- накопление промежуточных результатов
- обновление state после каждого шага
- retry / fallback / timeout / budget control
- сохранение состояния выполнения
- сбор финального контекста для ответа

Ключевая идея:
orchestrator — это управляющий слой, который решает **что делать дальше**, принимает результаты всех шагов, обновляет state и подготавливает вход для следующего шага или финальной генерации ответа.

В базовом режиме:
- orchestrator работает как цикл, в котором агент может извлекать сущности из запроса, вызывать retrieval/tooling, при необходимости задавать уточняющие вопросы и получать недостающий контекст.

В режиме deep research:
- orchestrator строит исследовательский план,
- разбивает задачу на подзадачи,
- запускает несколько итераций поиска,
- доузнает новую информацию по мере появления пробелов в knowledge state.

---

### 5.3 Planner Agent
Роль:
- анализ сложности запроса
- извлечение сущностей
- query decomposition
- выбор стратегии выполнения
- решение, нужен ли deep research
- решение, нужны ли external tools
- решение, нужен ли clarification/NER

Выход:
- execution plan
- список подзадач
- список предполагаемых источников
- признак режима (`standard` / `deep_research`)
- сущности запроса (например: сервис, команда, период, тип артефакта)

---

### 5.4 Retrieval Tool
Роль:
- выполнение поиска по индексам и источникам
- keyword / semantic / hybrid retrieval
- reranking
- нормализация результатов в evidence objects

Источники:
- индексированные внутренние документы
- keyword / hybrid search
- external API results через tool layer

Для PoC retrieval должен быть оформлен как явный инструмент с API-контрактом.

Пример логического контракта:
- вход:
  - `query`
  - `top_k`
  - `filters`
- выход:
  - список документов / chunk’ов / evidence objects
  - retriever metadata
  - scores

---

### 5.5 Analyst Agent
Роль:
- агрегация найденных evidence
- deduplication
- выделение фактов
- поиск противоречий
- структурирование материала для финального ответа
- выявление пробелов, которые требуют дополнительного поиска

---

### 5.6 Verifier Agent
Роль:
- groundedness check
- contradiction detection
- freshness check
- cross-check данных из документов и Jira API
- проверка достаточности evidence для ответа

Если verification не пройдена, система должна либо:
- пойти в дополнительный retrieval loop,
- либо ответить с явной неопределенностью,
- либо вернуться в fallback mode.

---

### 5.7 Writer Agent
Роль:
- формирование финального ответа
- структурирование ответа
- привязка утверждений к evidence
- маркировка неопределенности
- указание конфликтов и дат источников

---

### 5.8 Tool Layer
Роль:
- унифицированный доступ к внешним API
- таймауты, retries, error normalization
- контроль side effects
- защита от небезопасного выполнения tool calls

Для PoC используется read-only tooling.

В рамках проекта внешний API-контур ограничивается:
- `Jira API` или его аналогом
-  `Поисковым API`

Потенциальные сущности из API:
- задачи
- статусы задач
- исполнители
- пользователи
- связанные тикеты
- поля задач и служебные метаданные

Все это будет описано и главный агент сможет узнавать необходиме данные если нужно
---

### 5.9 State Layer
Роль:
- хранение runtime-состояния workflow
- хранение текущих шагов выполнения
- хранение visited queries, intermediate evidence, retry counters
- хранение информации о пользователе
- хранение контекста переписки
- обновление состояния после каждого шага agent cycle

State является центральным объектом исполнения и должен эволюционировать на каждом шаге работы системы.

---

### 5.10 Memory Layer
Роль:
- история сообщений
- session context
- summaries
- долгоживущая память, если нужна для диалога

---

## 6. Основной workflow выполнения задачи

### 6.1 Standard flow
1. Пользователь отправляет запрос
2. Gateway принимает запрос, флаг deep research и создает request context
3. Planner Agent извлекает сущности и определяет стратегию
4. Orchestrator вызывает Retrieval Tool
5. Retrieval Tool возвращает evidence
6. Analyst Agent агрегирует evidence
7. Verifier Agent выполняет проверки
8. Если данных недостаточно, orchestrator делает дополнительный шаг цикла
9. Writer Agent формирует ответ
10. Ответ возвращается пользователю
11. State обновляется найденным контекстом
---

### 6.2 Deep research flow
1. Пользователь явно выбирает режим deep research или система рекомендует его для сложного запроса
2. Gateway передает признак deep research в orchestrator
3. Planner Agent:
   - извлекает сущности
   - декомпозирует запрос
   - формирует исследовательский план
4. Orchestrator запускает agent cycle:
   - выбрать текущую подзадачу
   - выполнить retrieval/tool call
   - обновить state
   - проанализировать пробелы
   - уточнить следующую подзадачу
5. Analyst Agent агрегирует результаты всех шагов
6. Verifier Agent проверяет качество и конфликтность данных
7. При необходимости orchestrator запускает дополнительный loop
8. Writer Agent формирует финальный ответ
9. Ответ возвращается пользователю с указанием источников и ограничений

В течении всего этого времени могут вызываться тулы

---

## 7. State / Memory / Context Handling

### 7.1 State
State — краткоживущий runtime-контекст текущего выполнения.

Содержит:
- `request_id`
- `session_id`
- `workflow_id`
- execution mode
- профиль пользователя / доступный user context
- список подзадач
- visited queries
- intermediate evidence
- tool call history
- retry counters
- current step
- status
- accumulated context
- clarification history

Хранение:
- Redis или in-memory store для PoC

State обновляется после каждого шага:
- после planner step
- после retrieval/tool step
- после analyst step
- после verification step
- после clarification step
- инфа о переписки после финального ответа

---

### 7.2 Memory
Memory — более долгоживущая память сессии.

Содержит:
- историю сообщений
- краткие summaries
- контекст предыдущих вопросов в рамках сессии
- важные пользовательские уточнения в рамках диалога

Хранение:
- Postgres для chat history
- при необходимости vector memory в Qdrant / pgvector

---

### 7.3 Context budget
Контекст в LLM ограничен, поэтому:
- сырая история чата не передается целиком
- используется summarization
- retrieval context ограничивается top-k и reranking
- при сборке prompt действует budget policy по токенам

Приоритет контекста:
1. system instructions
2. execution plan
3. verified evidence
4. user/session context
5. session summary
6. recent chat turns

---

## 8. Retrieval-контур

### 8.1 Основные этапы
1. Query normalization
2. Entity extraction / alias expansion
3. Candidate retrieval
4. Reranking
5. Evidence normalization
6. Filtering по качеству / свежести / дубликатам

---

### 8.2 Источники retrieval
- индексированные внутренние документы (в рамках PoC — условные данные с Habr)
- keyword/hybrid поиск
- external API tool results

---

### 8.3 Retrieval strategies
- hybrid retrieval
- iterative retrieval
- query decomposition
- query expansion

---

### 8.4 Evidence schema
Каждый найденный элемент должен нормализоваться в единый формат:

- `id`
- `source`
- `source_type`
- `text`
- `timestamp`
- `score`
- `metadata`
- `trace_ref`

---

### 8.5 API поиска
Поисковый контур должен быть доступен как отдельный API/Tool-интерфейс.

Пример логического контракта поиска:
- вход:
  - `query: string`
  - `top_k: int`
  - `filters: object`
- выход:
  - `items: list`
  - `scores: list`
  - `retrieval_trace`
  - `used_strategy`

Это позволяет использовать retrieval как переиспользуемый инструмент внутри agent cycle.

---

## 9. Tool / API-интеграции

### 9.1 Назначение
Tools используются для получения актуальных структурированных данных, которых может не быть в документах.

В рамках PoC используется:
- Jira API или его аналог
- Микросервис с кастомным поиском по веткорной БД
---

### 9.2 Правила использования
- read-only режим для PoC
- таймаут на вызов
- ограничение числа вызовов на запрос
- ответы API тоже преобразуются в evidence objects

---

### 9.3 Основные требования
- четкий контракт входа/выхода
- error normalization
- retry only for transient failures
- no hidden side effects
- audit logging для tool usage

---

### 9.4 Примеры tool-данных
Из Jira API могут извлекаться:
- тикеты
- статусы
- исполнители
- сроки
- история изменений
- связи между задачами
- комментарии, если они доступны и разрешены

---

## 10. Quality control

Качество должно контролироваться на нескольких уровнях.

### 10.1 Retrieval quality
- Recall@k
- nDCG@k
- MAP@k
- доля полезных evidence после reranking
- CTR

---

### 10.2 Answer quality
- groundedness
- factual consistency
- contradiction rate
- hallucination rate
- answer completeness

---

### 10.3 Agent/process quality
- число agent steps
- доля fallback execution
- доля failed tool calls
- stop reason distribution
- доля запросов, для которых потребовался deep research
- число дополнительных циклов уточнения

---

## 11. Failure modes, fallback и guardrails

### 11.1 Failure modes
1. Недостаточный recall
2. Query decomposition error
3. Некорректный tool selection
4. API timeout / API failure
5. Hallucination на этапе synthesis
6. Конфликтующие источники
7. Устаревшие данные
8. Prompt injection из retrieval-контента
9. Превышение latency budget
10. Превышение token/cost budget
11. Потеря релевантного пользовательского контекста в state
12. Некорректное обновление state между шагами

---

### 11.2 Fallback
- deep research → standard retrieval
- tool retrieval failure → documents-only answer
- verification fail → uncertain answer с указанием ограничений
- reranker unavailable → raw top-k retrieval
- planner uncertainty → conservative plan
- недостаток контекста → clarification question пользователю

---

### 11.3 Guardrails
- system prompt isolation
- retrieval content treated as untrusted input
- prompt injection filtering
- source trust ranking
- freshness awareness
- budget limits
- tool allowlist
- explicit uncertainty policy
- no autonomous side-effect actions
- state update validation между шагами

---

## 12. Технические и операционные ограничения

### 12.1 Latency
Целевые ограничения для PoC:
- standard flow: p95 ≤ 5 сек
- deep research flow: p95 ≤ 12 сек
- single tool call timeout: 2–3 сек
- max workflow timeout: 15 сек

---

### 12.2 Cost
- ограничение числа LLM вызовов на запрос
- ограничение числа tool calls
- ограничение max iterations в deep research
- контекстный budget на prompt assembly

---

### 12.3 Reliability
- graceful degradation при ошибках интеграций
- частичные ошибки не должны ломать весь ответ
- все важные шаги должны быть наблюдаемы через trace/logs

---

## 13. Точки контроля перед реализацией

Перед началом реализации должны быть зафиксированы:
- evidence schema
- state schema
- orchestrator state machine
- tool contracts
- retrieval API contract
- prompt roles и boundaries
- retry/fallback policy
- budget policy
- observability contract

---

## 14. Итог

PoC строится как orchestrated multi-agent RAG-система, в которой LLM используется как контролируемый вычислительный компонент, а не как единственный источник логики. Архитектура ориентирована на повышение качества корпоративного поиска за счет decomposition, iterative retrieval, external tools и verification layer при явном контроле guardrails, latency и cost.

Ключевая особенность PoC — agent cycle под управлением orchestrator, который принимает результаты каждого шага, обновляет state, может уточнять запрос, вызывать retrieval и Jira API, а затем собирать финальный ответ на основе накопленного и проверенного контекста.