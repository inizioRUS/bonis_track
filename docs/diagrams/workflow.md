# Workflow / Graph Diagram

```mermaid
flowchart TD
    A[User sends request in Telegram Bot] --> B[Telegram Bot forwards request to API Gateway]
    B --> C[Gateway validates request and creates request/session context]
    C --> D[Orchestrator initializes workflow state]
    D --> E[Planner Agent analyzes query]

    E --> F{Deep research mode?}
    F -- No --> G[Build standard execution plan]
    F -- Yes --> H[Build deep research plan]

    G --> I[Run agent cycle]
    H --> I

    subgraph AgentCycle["Agent Cycle / Workflow Loop"]
        I --> J[Assemble context from state and memory]
        J --> K[Choose next action]

        K --> L[Call Search / Retrieval Tool]
        K --> M[Call Jira Tool]
        K --> N[Ask clarification question]
        K --> O[Finish evidence collection]

        L --> P{Retrieval success?}
        P -- Yes --> Q[Normalize results to evidence objects]
        P -- No --> R[Log retrieval failure]

        M --> S{Jira call success?}
        S -- Yes --> T[Normalize Jira data to evidence objects]
        S -- No --> U[Log tool failure]

        Q --> V[Update state]
        T --> V
        R --> W{Fallback available?}
        U --> W

        W -- Yes --> X[Fallback to alternative source or reduced mode]
        W -- No --> Y[Mark partial failure in state]

        X --> V
        Y --> V

        N --> Z[Receive clarification from user]
        Z --> V

        V --> AA[Analyst Agent aggregates evidence]
        AA --> AB[Verifier Agent checks groundedness, freshness, contradictions]

        AB --> AC{Verification passed?}
        AC -- Yes --> O
        AC -- No, recoverable --> AD[Refine query / add subtask / continue loop]
        AC -- No, not recoverable --> AE[Prepare uncertain but safe response]

        AD --> I
    end

    O --> AF[Writer Agent prepares final answer]
    AE --> AF

    AF --> AG{Answer generation success?}
    AG -- Yes --> AH[Persist session memory and final workflow state]
    AG -- No --> AI[Fallback to concise evidence-based response]

    AI --> AH
    AH --> AJ[Return response through Gateway]
    AJ --> AK[Telegram Bot sends final answer to user]

    %% Failure / budget / stop conditions
    I --> BA{Latency or cost budget exceeded?}
    BA -- No --> J
    BA -- Yes --> BB[Stop loop and prepare partial response]
    BB --> AF

    I --> BC{Max iterations reached?}
    BC -- No --> J
    BC -- Yes --> BD[Stop loop and prepare best-effort response]
    BD --> AF
```

# Пояснение
## Основной поток
1. Пользователь отправляет запрос через Telegram Bot
2. Gateway валидирует запрос и создает request/session context
3. Orchestrator инициализирует/подгружает state
4. Planner Agent анализирует запрос и выбирает режим:
* standard
* deep research
5. Далее запускается agent cycle, в котором система:
* собирает контекст,
* выбирает следующее действие,
* вызывает поиск или Jira,
* обновляет state,
* агрегирует evidence,
* проверяет качество через verifier
## Ветки внутри цикла

Внутри цикла возможны следующие действия:

* вызов Search / Retrieval Tool
* вызов Jira Tool
* постановка clarification question
* завершение сбора evidence
## Ветки ошибок

Диаграмма покрывает основные ошибки:

* retrieval failure
* Jira API failure
* verification failure
* answer generation failure
* превышение latency/cost budget
* достижение max iterations

## Fallback-логика

При ошибках система не должна падать целиком. Возможные fallback-сценарии:

* переход к альтернативному источнику
* переход к reduced mode
* выдача partial answer
* выдача uncertain but safe response
* best-effort response на основе уже найденного evidence
