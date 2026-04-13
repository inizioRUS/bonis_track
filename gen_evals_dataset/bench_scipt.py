#!/usr/bin/env python3
import argparse
import asyncio
import csv
import json
import statistics
import time
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from tqdm.asyncio import tqdm_asyncio


@dataclass
class EvalRow:
    sample_id: str
    question: str
    expected_answers: list[str]
    predicted_answer: str
    status_code: int | None
    error: str | None
    latency_sec: float | None
    source_hit: bool
    source_recall: float
    answer_token_f1: float
    returned_sources: list[Any]
    ground_truth_urls: list[str]


@dataclass
class Summary:
    total: int
    ok: int
    failed: int
    avg_latency_sec: float
    p50_latency_sec: float
    p95_latency_sec: float
    source_hit_rate: float
    avg_source_recall: float
    avg_answer_token_f1: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Прогоняет benchmark/evals цикл по endpoint /ask"
    )
    parser.add_argument("--input", required=True, help="Путь к JSON или JSONL файлу с датасетом")
    parser.add_argument("--base-url", required=True, help="Например: http://localhost:8000")
    parser.add_argument("--output", default="eval_report", help="Префикс выходных файлов")
    parser.add_argument("--user-id", default="eval_user")
    parser.add_argument("--username", default="eval_runner")
    parser.add_argument("--session-prefix", default="eval_session")
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--deep-research", action="store_true")
    parser.add_argument("--is-eval", action="store_true", default=True)
    parser.add_argument(
        "--expected-doc-ids-from",
        choices=["none", "sample_id"],
        default="none",
        help=(
            "Если хочешь пробрасывать expected_doc_ids в /ask. "
            "Сейчас поддерживается либо none, либо sample_id -> [sample['id']]."
        ),
    )
    return parser.parse_args()


def load_dataset(path: str) -> list[dict[str, Any]]:
    raw = Path(path).read_text(encoding="utf-8").strip()
    if not raw:
        raise ValueError("Входной файл пуст")

    if raw[0] in "[{":
        data = json.loads(raw)
        if isinstance(data, dict):
            if "items" in data and isinstance(data["items"], list):
                return data["items"]
            return [data]
        if isinstance(data, list):
            return data
        raise ValueError("Неподдерживаемый JSON-формат")

    rows = []
    for line in raw.splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def normalize_text(text: str) -> str:
    chars = []
    for ch in text.lower():
        if ch.isalnum() or ch.isspace():
            chars.append(ch)
        else:
            chars.append(" ")
    return " ".join("".join(chars).split())


def token_f1(pred: str, gold: str) -> float:
    pred_tokens = normalize_text(pred).split()
    gold_tokens = normalize_text(gold).split()
    if not pred_tokens or not gold_tokens:
        return 0.0

    pred_counts: dict[str, int] = {}
    gold_counts: dict[str, int] = {}
    for tok in pred_tokens:
        pred_counts[tok] = pred_counts.get(tok, 0) + 1
    for tok in gold_tokens:
        gold_counts[tok] = gold_counts.get(tok, 0) + 1

    common = 0
    for tok, cnt in pred_counts.items():
        common += min(cnt, gold_counts.get(tok, 0))

    if common == 0:
        return 0.0

    precision = common / len(pred_tokens)
    recall = common / len(gold_tokens)
    return 2 * precision * recall / (precision + recall)


def best_answer_f1(pred: str, gold_answers: list[str]) -> float:
    if not gold_answers:
        return 0.0
    return max(token_f1(pred, gold) for gold in gold_answers)


def canonicalize_url(url: str) -> str:
    try:
        parsed = urlparse(url.strip())
        netloc = parsed.netloc.lower().removeprefix("www.")
        path = parsed.path.rstrip("/")
        return f"{netloc}{path}"
    except Exception:
        return url.strip().lower()


def extract_urls_from_source(source: Any) -> list[str]:
    urls: list[str] = []
    if isinstance(source, str):
        if source.startswith("http://") or source.startswith("https://"):
            urls.append(source)
        return urls

    if isinstance(source, dict):
        for key in (
            "url",
            "link",
            "source_url",
            "document_url",
            "doc_url",
            "href",
        ):
            value = source.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                urls.append(value)

        metadata = source.get("metadata")
        if isinstance(metadata, dict):
            urls.extend(extract_urls_from_source(metadata))
    return urls


def evaluate_sources(returned_sources: list[Any], gt_docs: list[dict[str, Any]]) -> tuple[bool, float]:
    gt_urls = [canonicalize_url(doc["url"]) for doc in gt_docs if isinstance(doc, dict) and doc.get("url")]
    if not gt_urls:
        return False, 0.0

    found_urls: set[str] = set()
    for src in returned_sources or []:
        for url in extract_urls_from_source(src):
            found_urls.add(canonicalize_url(url))

    matched = sum(1 for gt in gt_urls if gt in found_urls)
    hit = matched > 0
    recall = matched / len(gt_urls)
    return hit, recall


async def ask_one(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    base_url: str,
    sample: dict[str, Any],
    user_id: str,
    username: str,
    session_prefix: str,
    deep_research: bool,
    is_eval: bool,
    expected_doc_ids_from: str,
) -> EvalRow:
    sample_id = str(sample["ground_truth_docs"][0]["url"] or uuid.uuid4())
    question = sample["question"]
    answers = sample.get("answers", [])
    gt_docs = sample.get("ground_truth_docs", [])

    expected_doc_ids: list[str] = []
    if expected_doc_ids_from == "sample_id":
        expected_doc_ids = [sample_id]

    payload = {
        "user_id": user_id,
        "username": username,
        "session_id": f"{session_prefix}_{sample_id}",
        "query": question,
        "deep_research": deep_research,
        "is_eval": is_eval,
        "expected_doc_ids": expected_doc_ids,
    }

    async with semaphore:
        start = time.perf_counter()
        try:
            response = await client.post(f"{base_url.rstrip('/')}/ask", json=payload)
            latency = time.perf_counter() - start
            data = response.json()

            predicted_answer = data.get("answer", "") if isinstance(data, dict) else ""
            returned_sources = data.get("sources", []) if isinstance(data, dict) else []
            source_hit, source_recall = evaluate_sources(returned_sources, gt_docs)
            answer_f1 = best_answer_f1(predicted_answer, answers)

            return EvalRow(
                sample_id=sample_id,
                question=question,
                expected_answers=answers,
                predicted_answer=predicted_answer,
                status_code=response.status_code,
                error=None if response.is_success else json.dumps(data, ensure_ascii=False),
                latency_sec=round(latency, 4),
                source_hit=source_hit,
                source_recall=round(source_recall, 4),
                answer_token_f1=round(answer_f1, 4),
                returned_sources=returned_sources,
                ground_truth_urls=[doc.get("url", "") for doc in gt_docs if isinstance(doc, dict)],
            )
        except Exception as exc:
            latency = time.perf_counter() - start
            return EvalRow(
                sample_id=sample_id,
                question=question,
                expected_answers=answers,
                predicted_answer="",
                status_code=None,
                error=f"{type(exc).__name__}: {exc}",
                latency_sec=round(latency, 4),
                source_hit=False,
                source_recall=0.0,
                answer_token_f1=0.0,
                returned_sources=[],
                ground_truth_urls=[doc.get("url", "") for doc in gt_docs if isinstance(doc, dict)],
            )


def build_summary(rows: list[EvalRow]) -> Summary:
    total = len(rows)
    ok_rows = [r for r in rows if r.error is None and (r.status_code or 0) < 400]
    failed = total - len(ok_rows)
    latencies = [r.latency_sec for r in rows if r.latency_sec is not None]
    source_hits = [1.0 if r.source_hit else 0.0 for r in rows]
    source_recalls = [r.source_recall for r in rows]
    answer_f1s = [r.answer_token_f1 for r in rows]

    sorted_lat = sorted(latencies)

    def percentile(values: list[float], p: float) -> float:
        if not values:
            return 0.0
        idx = min(len(values) - 1, max(0, int(round((len(values) - 1) * p))))
        return float(values[idx])

    return Summary(
        total=total,
        ok=len(ok_rows),
        failed=failed,
        avg_latency_sec=round(statistics.mean(latencies), 4) if latencies else 0.0,
        p50_latency_sec=round(percentile(sorted_lat, 0.50), 4),
        p95_latency_sec=round(percentile(sorted_lat, 0.95), 4),
        source_hit_rate=round(statistics.mean(source_hits), 4) if source_hits else 0.0,
        avg_source_recall=round(statistics.mean(source_recalls), 4) if source_recalls else 0.0,
        avg_answer_token_f1=round(statistics.mean(answer_f1s), 4) if answer_f1s else 0.0,
    )


def write_outputs(output_prefix: str, rows: list[EvalRow], summary: Summary) -> None:
    output_json = Path(f"{output_prefix}.json")
    output_csv = Path(f"{output_prefix}.csv")

    output_json.write_text(
        json.dumps(
            {
                "summary": asdict(summary),
                "rows": [asdict(r) for r in rows],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    with output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "sample_id",
                "question",
                "predicted_answer",
                "status_code",
                "error",
                "latency_sec",
                "source_hit",
                "source_recall",
                "answer_token_f1",
                "ground_truth_urls",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "sample_id": row.sample_id,
                    "question": row.question,
                    "predicted_answer": row.predicted_answer,
                    "status_code": row.status_code,
                    "error": row.error,
                    "latency_sec": row.latency_sec,
                    "source_hit": row.source_hit,
                    "source_recall": row.source_recall,
                    "answer_token_f1": row.answer_token_f1,
                    "ground_truth_urls": json.dumps(row.ground_truth_urls, ensure_ascii=False),
                }
            )


async def main() -> None:
    dataset = load_dataset(
        "\\bonis_track\\gen_evals_dataset\\examples\\rag_eval_dataset.json"
    )
    semaphore = asyncio.Semaphore(1)  # или parse_args().concurrency

    async with httpx.AsyncClient(timeout=300) as client:
        tasks = [
            ask_one(
                client=client,
                semaphore=semaphore,
                base_url="http://localhost:8000/",
                sample=sample,
                user_id="1337",
                username="test_user",
                session_prefix="",
                deep_research=False,
                is_eval=True,
                expected_doc_ids_from="sample_id",
            )
            for sample in dataset
        ]

        rows = await tqdm_asyncio.gather(
            *tasks,
            desc="Running evals",
            total=len(tasks),
        )

        print(rows)


if __name__ == "__main__":
    asyncio.run(main())