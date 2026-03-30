# C4 Context

```mermaid
flowchart LR
    User[User]
    TG[Telegram Bot]

    System[PoC Corporate Search System]

    SearchAPI[Search API]
    JiraAPI[Jira API]
    LLM[LLM Provider]
    Obs[Observability Stack]

    User --> TG
    TG --> System

    System --> SearchAPI
    System --> JiraAPI
    System --> LLM
    System --> Obs
 ```
# Пояснение
## Пользователь
User — сотрудник, который хочет найти информацию по внутренним артефактам компании, задать уточняющие вопросы и получить итоговый ответ в диалоговом формате.

## Граница системы

PoC Corporate Search System — основная система корпоративного поиска с RAG и multi-agent orchestration.
* Внутри этой границы находятся:
  * gateway
  * orchestrator
  * agents
  * retrieval/tool layer
  * state/memory handling
## Пользовательский интерфейс
* Telegram Bot — внешний интерфейс системы, через который пользователь:
  * отправляет запросы
  *может включать deep research mode
  *получает ответы
  *отвечает на clarification questions
# Внешние сервисы
  * Search API — внешний или логически выделенный поисковый контур для retrieval по индексированным документам.
  * Jira API — внешний источник структурированных данных по задачам, статусам, исполнителям и связям между тикетами.
  * LLM Provider — внешний сервис языковой модели, используемый для planning, analysis, verification и answer generation.
  * Observability Stack — внешний контур логирования, метрик и трассировки.
# Границы ответственности
## Что находится внутри системы
* orchestration логики
* agent cycle
* planning и decomposition
* retrieval orchestration
* verification
* answer synthesis
* state и memory management
## Что находится вне системы
* пользовательский клиент (Telegram)
* поисковый API
* Jira
* LLM provider
* observability platform