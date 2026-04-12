def mrr(retrieved_urls, relevant_urls):
    for i, url in enumerate(retrieved_urls, start=1):
        if url in relevant_urls:
            return 1 / i
    return 0.0


def recall_at_k(retrieved_urls, relevant_urls, k):
    retrieved_k = set(retrieved_urls[:k])
    relevant = set(relevant_urls)
    return len(retrieved_k & relevant) / len(relevant) if relevant else 0.0


def recall_at_k(retrieved_urls, relevant_urls, k):
    retrieved_k = set(retrieved_urls[:k])
    relevant = set(relevant_urls)
    return len(retrieved_k & relevant) / len(relevant) if relevant else 0.0


def precision_at_k(retrieved_urls, relevant_urls, k):
    retrieved_k = retrieved_urls[:k]
    relevant = set(relevant_urls)
    return sum(1 for url in retrieved_k if url in relevant) / k


import math


def ndcg_at_k(retrieved_urls, relevant_urls, k):
    dcg = 0.0
    for i, url in enumerate(retrieved_urls[:k], start=1):
        if url in relevant_urls:
            dcg += 1 / math.log2(i + 1)

    idcg = sum(1 / math.log2(i + 1) for i in range(1, min(len(relevant_urls), k) + 1))
    return min(dcg / idcg if idcg > 0 else 0.0, 1)




def evaluate_sample(
        sample,
        retrieved_docs,
        k=5
):
    retrieved_urls = [d["url"] for d in retrieved_docs]
    relevant_urls = [d["url"] for d in sample["ground_truth_docs"]]

    metrics = {
        "mrr": mrr(retrieved_urls, relevant_urls),
        "recall@k": recall_at_k(retrieved_urls, relevant_urls, k),
        "precision@k": precision_at_k(retrieved_urls, relevant_urls, k),
        "ndcg@k": ndcg_at_k(retrieved_urls, relevant_urls, k),
    }


    return metrics


def average_metrics(results):
    avg = {}
    for key in results[0]:
        avg[key] = sum(r[key] for r in results) / len(results)
    return avg