# Governance

## Risk Register

| Риск | Вероятность / Влияние | Детект | Защита | Остаточный риск |
|------|----------------------|--------|--------|----------------|
| Hallucination | Medium / High | LLM-as-judge | Verification step | Средний |
| Prompt injection | Medium / High | Pattern detection | Input sanitization + system prompt isolation | Средний |
| Data leakage | Low / High | Audit logs | Access control + source filtering | Низкий |
| Высокая latency | High / Medium | Monitoring p95 | Ограничение шагов агента | Средний |
| Cost overrun | Medium / Medium | Token tracking | Budget cap | Низкий |

---

## Политика логирования

Логируются:
- Входной запрос
- Агентные шаги
- Retrieval IDs
- Latency

Не логируются:
- Персональные данные
- Чувствительные поля

Логи анонимизируются при использовании в evaluation.

---

## Работа с персональными данными

В PoC используются open-source данные. Но будет имитация доступов условного пользователя к определенным данным.
В проде:
- Обязательная фильтрация по доступам.

---

## Защита от Prompt Injection

- System prompt изолирован
- Пользовательский ввод проходит sanitization
- Retrieval-контент не может менять инструкции