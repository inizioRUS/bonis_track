# C4 Component

```mermaid
flowchart TB
    %% External
    User[User]
    SearchAPI[Search API]
    JiraAPI[Jira API]
    Redis[(Redis)]
    Postgres[(Postgres)]

    %% System boundary
    subgraph Core["PoC Core System"]
        Gateway[Gateway]

        subgraph OrchestratorCore["Orchestrator Core"]
            Orchestrator[Orchestrator]
            AgentCycle[Agent Cycle / Workflow Loop]
            StateManager[State Manager]
            MemoryManager[Memory Manager]
            PromptBuilder[Prompt Builder]
            ContextAssembler[Context Assembler]
            Guardrails[Guardrails / Validation]
        end

        subgraph Agents["Agents"]
            Planner[Planner Agent]
            Analyst[Analyst Agent]
            Verifier[Verifier Agent]
            Writer[Writer Agent]
        end

        subgraph Tools["Tool Layer"]
            RetrievalTool[Retrieval Tool]
            JiraTool[Jira Tool]
        end
    end

    %% Main entry
    User --> Gateway
    Gateway --> Orchestrator

    %% Orchestrator internals
    Orchestrator --> AgentCycle
    Orchestrator --> StateManager
    Orchestrator --> MemoryManager
    Orchestrator --> PromptBuilder
    Orchestrator --> ContextAssembler
    Orchestrator --> Guardrails

    %% Cycle with agents
    AgentCycle --> Planner
    Planner --> AgentCycle

    AgentCycle --> RetrievalTool
    RetrievalTool --> AgentCycle

    AgentCycle --> Analyst
    Analyst --> AgentCycle

    AgentCycle --> Verifier
    Verifier --> AgentCycle

    AgentCycle --> Writer
    Writer --> AgentCycle

    %% Tools to externals
    RetrievalTool --> SearchAPI
    JiraTool --> JiraAPI

    %% Optional Jira path from cycle
    AgentCycle --> JiraTool
    JiraTool --> AgentCycle

    %% State and memory
    StateManager --> Redis
    Redis --> StateManager

    MemoryManager --> Postgres
    Postgres --> MemoryManager

    %% Context and prompts
    StateManager --> ContextAssembler
    MemoryManager --> ContextAssembler
    ContextAssembler --> PromptBuilder
    PromptBuilder --> Planner
    PromptBuilder --> Analyst
    PromptBuilder --> Verifier
    PromptBuilder --> Writer

    %% Guardrails
    Guardrails --> RetrievalTool
    Guardrails --> JiraTool
    Guardrails --> Writer

    %% Final response
    AgentCycle --> Orchestrator
    Orchestrator --> Gateway
    Gateway --> User
```

# Пояснение
## Основные компоненты
* Gateway — принимает пользовательский запрос и передаёт его в ядро системы.
* Orchestrator — главный управляющий компонент, который координирует выполнение сценария.
* Agent Cycle / Workflow Loop — цикл исполнения, в рамках которого система:
* анализирует запрос,
* вызывает агентов,
* обращается к tool layer,
* обновляет state,
* принимает решение о следующем шаге,
* завершает выполнение финальным ответом.
## Агенты
* Planner Agent — извлекает сущности, определяет сложность, строит план.
* Analyst Agent — агрегирует найденные evidence и выделяет факты.
* Verifier Agent — проверяет groundedness, конфликты и достаточность данных.
* Writer Agent — формирует финальный ответ.
## Хранилища
* Redis — хранение runtime-state:
  - workflow state
  - visited queries 
  - промежуточные evidence 
  - текущий шаг цикла 
  - уточнения пользователя
* Postgres — хранение memory:
  - история переписки 
  - summaries 
  - session context 
  - пользовательский контекст
## Внешние контуры
* Search API — внешний поисковый контур / retrieval tool для поиска по документам.
* Jira API — внешний источник структурированных данных по задачам, статусам, исполнителям и связям между тикетами.
## Ключевая идея

Orchestrator не просто один раз вызывает агента, а управляет циклом исполнения, где после каждого шага:

* обновляется state,
* пересобирается context,
* проверяется необходимость новых retrieval/tool calls,
* принимается решение — продолжать цикл или формировать финальный ответ.