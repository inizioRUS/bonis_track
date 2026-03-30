# Agent / Orchestrator Spec

## 1. Назначение

Orchestrator является центральным управляющим компонентом системы.  
Он контролирует execution flow, вызывает агентов и tools, обновляет state и принимает решение о переходе к следующему шагу.

Архитектура строится по принципу **orchestrator-first**:
- агенты не принимают самостоятельных решений о side effects
- переходы между шагами задаются orchestrator’ом

---

## 2. Роли агентов

### Planner Agent
- анализ запроса
- выделение сущностей
- decomposition
- выбор режима выполнения
- выбор источников

### Analyst Agent
- агрегирует evidence
- выделяет факты
- ищет противоречия
- выявляет пробелы

### Verifier Agent
- проверяет groundedness
- проверяет конфликты
- проверяет freshness
- оценивает достаточность evidence

### Writer Agent
- формирует финальный ответ
- отмечает uncertainty
- прикладывает источники

---

## 3. Основные шаги workflow

1. принять запрос
2. инициализировать state
3. загрузить memory/context
4. вызвать planner
5. выбрать `standard` или `deep_research`
6. выполнить retrieval/tool calls
7. обновить state
8. вызвать analyst
9. вызвать verifier
10. при необходимости повторить цикл
11. вызвать writer
12. сохранить результат в memory/state
13. вернуть ответ пользователю

---

## 4. Правила переходов

### Standard mode
Типовой путь:
- planner
- retrieval
- analyst
- verifier(возможен доп вопрос)
- writer

### Deep research mode
Типовой путь:
- planner
- decomposition
- retrieval/tool loop
- analyst
- verifier
- refinement / next subtask
- повтор цикла до stop condition
- writer

### Clarification path
Если не хватает критически важной сущности:
- orchestrator формирует clarification question
- получает ответ пользователя
- обновляет state
- продолжает workflow

---

## 5. Stop conditions

Workflow должен завершаться, если выполняется хотя бы одно условие:

- answer sufficiently grounded
- все подзадачи закрыты
- достигнут `max_iterations`
- превышен latency budget
- превышен cost budget
- больше нет полезных действий
- пользователь не ответил на clarification и нельзя двигаться дальше

---

## 6. Retry policy

Retry применяется только для технических ошибок.

### Допустим retry
- transient tool failure
- timeout
- temporary unavailable
- кратковременная ошибка интеграции


## 7. Fallback policy

Если шаг не удался, orchestrator обязан деградировать безопасно.

### Примеры fallback
- deep research -> standard retrieval
- tool failure -> documents-only flow
- verification fail -> uncertain answer
- no results -> clarification question
- reranker fail -> raw top-k
- planner uncertainty -> conservative execution plan

---

## 8. Guardrails

- orchestrator контролирует все переходы
- tool outputs считаются untrusted
- state updates валидируются
- writer не должен утверждать факты без evidence
- verifier обязателен перед финальным ответом
- external actions запрещены

---

## 9. Ограничения

### PoC ограничения
- ограниченное число агентных шагов
- ограниченное число итераций в deep research
- ограничение по latency
- ограничение по tool calls
- read-only tooling

### Принцип
Лучше вернуть неполный, но безопасный и проверенный ответ, чем полный, но недостоверный.