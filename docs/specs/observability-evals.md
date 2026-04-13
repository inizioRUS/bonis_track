# Observability / Evals Spec

## 1. Назначение

Observability и evaluation нужны для контроля качества retrieval, качества ответа, надежности workflow и поведения LLM внутри системы.

Сигналы должны собираться на каждом критическом этапе пайплайна.

---

## 2. Метрики качества retrieval

### Retrieval quality
- Recall@k
- MAP@k
- nDCG@k
- доля полезных evidence после reranking
- CTR

### Дополнительно
- average retrieved candidates
- reranker success rate
- empty retrieval rate

---

## 3. Метрики качества ответа

### Answer quality
- groundedness
- factual consistency
- contradiction rate
- hallucination rate
- answer completeness
- доля ответов с явной uncertainty markup

---

## 4. Метрики процесса

### Agent / process quality
- число agent steps
- среднее число итераций
- доля deep research запросов
- число clarification loops
- доля fallback execution
- stop reason distribution
- failed tool call rate

---

## 5. Технические метрики

- total workflow latency
- latency by stage
- tool latency
- LLM latency
- token usage
- cost per query
- timeout rate
- retry rate

---

## 6. Logs

Логируются:
- входящий запрос
- выбранный execution mode
- planner output summary
- retrieval strategy
- tool calls
- verification result
- fallback events
- final response status

Не логируются в сыром виде:
- чувствительные токены
- секреты
- приватные системные ключи

---

## 7. Traces

Должны быть доступны end-to-end traces:

- Telegram Bot span
- Gateway span
- Orchestrator span
- Planner span
- Retrieval span
- Jira span
- Analyst span
- Verifier span
- Writer span

Цель:
- видеть узкие места по latency
- понимать, на каком шаге произошел сбой
- анализировать полное поведение agent cycle

---

## 8. Audit events

Audit нужен для архитектурно значимых действий:

- какой tool вызван
- почему выбран deep research
- почему выбран fallback
- почему ответ помечен uncertain
- какие источники использованы
- сколько было циклов поиска
- какой stop reason сработал

---

## 9. Проверки и evals

### Автоматические проверки
- ответ не должен формироваться без evidence
- ответ должен проходить verification
- tool response должен быть нормализован
- planner/verifier outputs должны проходить schema validation

### Offline evals
- benchmark retrieval quality
- benchmark answer quality
- сравнение baseline RAG vs agent-enhanced mode
- сравнение standard vs deep research

### Manual review
- анализ edge cases
- анализ hallucination scenarios
- анализ failure/fallback behavior

---

## 10. Основная цель observability

Observability в PoC нужна не только для мониторинга ошибок, но и для ответа на вопросы:

- почему система дала именно такой ответ
- какие данные были использованы
- почему был запущен deep research
- на каком шаге качество ухудшилось
- был ли ответ действительно grounded

Использовать langfuse