# States Flow

Документ описывает структуру `WorkflowState` и то, как состояние меняется по мере прохождения multi-agent workflow.

---

## 1. Основная идея

`WorkflowState` — это единый объект состояния, который передается между агентами в graph / cycle execution.

Он хранит:
- входной пользовательский запрос,
- историю сообщений,
- текущий план,
- результаты retrieval и tool calls,
- evidence,
- verification status,
- итоговый ответ,
- данные о памяти,
- параметры цикла.

Таким образом, состояние является центральным носителем контекста между шагами workflow.

---

## 2. State Schema

```python
from typing import Any, Optional
from typing_extensions import TypedDict


class MemoryItem(TypedDict, total=False):
    id: str
    kind: str  # "user_pref" | "project_fact" | "task_context" | "summary" | ...
    content: str
    source: str  # "session" | "asana" | "retriever" | "llm"
    score: float
    metadata: dict[str, Any]


class WorkflowState(TypedDict, total=False):
    session_id: str
    user_id: str
    username: str
    user_query: str
    deep_research: bool

    messages: list[dict[str, str]]

    plan: dict[str, Any]

    tool_history: list[dict[str, Any]]
    retrieval_results: list[dict[str, Any]]
    evidence: list[dict[str, Any]]

    verification: dict[str, Any]
    next_agent: str
    final_answer: Optional[str]
    final_sources: list[dict[str, Any]]

    iteration: int
    max_iterations: int

    # memory
    memory_hits: list[MemoryItem]

    expected_doc_ids: list[str]
    is_eval: bool
```
3. Поля состояния
* Identity / session
* session_id — идентификатор чата / сессии
* user_id — идентификатор пользователя
* username — имя пользователя
* user_query — текущий пользовательский запрос
* deep_research — включён ли deep research mode
Dialogue context
* messages — текущая история переписки, доступная workflow
Planning
* plan — текущий execution plan, созданный planner agent
Retrieval / tools
* tool_history — список уже выполненных tool calls
* retrieval_results — сырые результаты retrieval
* evidence — нормализованные данные, пригодные для анализа и verification
Verification / output
* verification — результат проверки достаточности и качества данных
* next_agent — следующий агент, которого должен вызвать orchestrator
* final_answer — итоговый текст для пользователя
* final_sources — список источников, использованных в ответе
Iteration control
* iteration — номер текущей итерации
* max_iterations — лимит на число итераций
Memory
* memory_hits — что было найдено в долгоживущей памяти
Eval / control flags
* expected_doc_ids — ожидаемые документы для eval mode
* is_eval — флаг evaluation-сценария
* 
4. Как state меняется по шагам
Шаг 1. Вход в workflow

Инициализируются:

* session_id
* user_id
* username
* user_query
* deep_research
* messages
* iteration = 0
* max_iterations
* tool_history = []
* retrieval_results = []
* evidence = []
* memory_hits = []
* next_agent = "planner_agent"

Шаг 2. Memory loading

После чтения long-term memory обновляются:

* memory_hits

Это позволяет planner учитывать:

* прошлые user preferences
* project facts
* summaries
* session-level context

Шаг 3. Planner step

Planner анализирует текущее состояние и записывает:

* plan
* next_agent

Planner не должен менять:

* final_answer
* verification

Planner может учитывать:

* messages
* tool_history
* retrieval_results
* memory_hits

Шаг 4. Retrieval / tool execution

После выполнения retrieval/tool calls обновляются:

* tool_history
* retrieval_results
* evidence

Если retrieval возвращает документы:

сначала они попадают в retrieval_results
затем нормализуются в evidence

Если выполняется Asana execution step:

информация о вызове также пишется в tool_history

Шаг 5. Verification step

Verifier анализирует:

* plan
* retrieval_results
* tool_history
* iteration
* max_iterations

После этого обновляются:

* verification
* next_agent

Возможные варианты:

* next_agent = "planner_agent" — нужно ещё retrieval / replanning
* next_agent = "writer_agent" — можно завершать

Шаг 6. Writer step

Writer использует:

* user_query
* plan
* verification
* tool_history
* retrieval_results
* evidence

После этого обновляются:

* final_answer
* final_sources

5. State transitions

Типичный базовый переход:

start
  -> planner_agent
  -> retrieval/tools
  -> verifier_agent
  -> writer_agent
  -> finish

Типичный deep research переход:

start
  -> planner_agent
  -> retrieval/tools
  -> verifier_agent
  -> planner_agent
  -> retrieval/tools
  -> verifier_agent
  -> writer_agent
  -> finish

6. Что должен обновлять orchestrator

Orchestrator отвечает за безопасное обновление state между шагами:

* инкремент iteration
* обновление next_agent
* добавление новых tool records в tool_history
* добавление новых retrieval outputs в retrieval_results
* обновление verification
* запись final_answer
* остановку по max_iterations

7. Invariants

Во время работы системы должны соблюдаться следующие инварианты:

* user_query не должен теряться между шагами
* tool_history должен быть append-only в рамках workflow
* iteration <= max_iterations
* next_agent должен быть валидным именем агента
* final_answer не должен появляться до writer step
* verification должен существовать перед final response
* final_sources должны быть согласованы с evidence / retrieval_results