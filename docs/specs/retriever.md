# Retriever Spec

## 1. Назначение

Retriever отвечает за поиск релевантной информации по пользовательскому запросу и возврат результатов в едином формате `evidence objects`, пригодном для дальнейшего анализа, верификации и генерации ответа.

В рамках PoC retriever используется как **отдельный инструмент поиска** внутри orchestrator-controlled workflow, а не как скрытая часть LLM.

---

## 2. Источники

В PoC retrieval выполняется по следующим источникам:

- индексированные внутренние документы  
  *(в рамках демонстрации — условные данные с Habr / open-source corpus)*
- hybrid поиск
- результаты внешних API после нормализации в evidence format

### Источники вне PoC
Не входят в текущую реализацию:
- Confluence production integration
- GitHub/GitLab API
- CMDB / service catalog
- monitoring/log systems

---

## 3. Индекс

Для retrieval используется индексированный корпус документов, разбитый на chunk’и.

### Индексация включает:
- document id
- chunk id
- source
- title
- text
- timestamp / updated_at
- metadata
- embedding vector

### Хранилища
- **Vector Store** — embeddings и semantic retrieval
- при необходимости keyword/hybrid индекс — отдельный слой поиска или search API

---

## 4. Основной pipeline retrieval

1. Нормализация запроса
2. Entity extraction / alias expansion
3. Выбор retrieval strategy
4. Candidate retrieval
5. Reranking
6. Deduplication
7. Evidence normalization
8. Возврат результатов в orchestrator

---

## 5. Стратегии поиска

Поддерживаемые стратегии:

- `hybrid`
- `iterative retrieval`
- `query decomposition`
- `query expansion`

### Когда используются
- **hybrid** — базовый режим по умолчанию
- **iterative retrieval** — в deep research mode
- **query decomposition** — для составных запросов
- **query expansion** — при недостаточном recall

---

## 6. Reranking

После первичного retrieval кандидаты проходят reranking.

### Цель reranking
- повысить релевантность top-k
- убрать шум
- лучше покрыть аспекты составного запроса

### Ожидаемые эффекты
- рост precision на верхних позициях
- улучшение качества evidence для LLM
- снижение hallucinations на этапе ответа

### Fallback
Если reranker недоступен:
- используется raw top-k retrieval
- событие логируется
- система продолжает работать в degraded mode

---

## 7. Контракт Retriever API

Retriever должен быть доступен как tool/API с явным контрактом.

### Вход
- `query: string`
- `top_k: int`
- `mode: keyword | semantic | hybrid`
- `filters: object`
- `session_id: string` *(optional)*
- `trace_id: string`
- `use_reranker: bool`

### Выход
- `items: list[evidence]`
- `scores: list[float]`
- `used_strategy: string`
- `retrieval_trace: object`
- `latency_ms: int`

---

## 8. Evidence schema

Каждый retrieval result должен быть нормализован в единый формат:

- `id`
- `source`
- `source_type`
- `text`
- `timestamp`
- `score`
- `metadata`
- `trace_ref`

### Пример
```json
{
  "id": "doc_42_chunk_3",
  "source": "habr",
  "source_type": "document",
  "text": "SLA сервиса Y составляет 99.95%",
  "timestamp": "2026-03-01",
  "score": 0.91,
  "metadata": {
    "title": "Service Y Overview",
    "chunk_id": 3
  },
  "trace_ref": "retrieval_step_001"
}