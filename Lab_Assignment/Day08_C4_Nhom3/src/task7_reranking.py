"""Task 7 - Reranking with Qwen3-Reranker and reliable fallbacks."""

import math
import os
import re

try:
    from .task4_chunking_indexing import embed_texts
except ImportError:
    from task4_chunking_indexing import embed_texts

RERANKER_MODEL = "Qwen/Qwen3-Reranker-0.6B"
USE_QWEN_RERANKER = os.getenv("USE_QWEN_RERANKER", "0") == "1"
_QWEN_MODEL = None


def tokenize(text: str) -> list[str]:
    """Tokenize query/doc for fallback reranking."""
    return re.findall(r"[\wÀ-ỹ]+", text.lower(), flags=re.UNICODE)


def normalize_scores(values: list[float]) -> list[float]:
    """Scale scores to [0, 1] while preserving order."""
    if not values:
        return []
    min_value = min(values)
    max_value = max(values)
    if max_value == min_value:
        return [1.0 for _ in values]
    return [(value - min_value) / (max_value - min_value) for value in values]


def cosine_sim(left: list[float], right: list[float]) -> float:
    """Cosine similarity helper for MMR."""
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    dot = sum(left[i] * right[i] for i in range(size))
    left_norm = math.sqrt(sum(value * value for value in left[:size]))
    right_norm = math.sqrt(sum(value * value for value in right[:size]))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def fallback_relevance_score(query: str, candidate: dict) -> float:
    """Fast rerank score based on token overlap plus retrieval prior."""
    query_terms = set(tokenize(query))
    doc_terms = set(tokenize(candidate.get("content", "")))
    if not query_terms:
        overlap_score = 0.0
    else:
        overlap_score = len(query_terms & doc_terms) / len(query_terms)

    prior = float(candidate.get("score", 0.0))
    prior = max(0.0, min(prior, 1.0)) if prior <= 1 else 1.0
    return 0.8 * overlap_score + 0.2 * prior


def load_qwen_cross_encoder():
    """Load Qwen3-Reranker only when explicitly enabled and cached locally."""
    global _QWEN_MODEL
    if _QWEN_MODEL is not None:
        return _QWEN_MODEL
    if not USE_QWEN_RERANKER:
        return None

    try:
        from sentence_transformers import CrossEncoder

        _QWEN_MODEL = CrossEncoder(RERANKER_MODEL, local_files_only=True)
        return _QWEN_MODEL
    except Exception as exc:
        print(f"⚠ Không load được {RERANKER_MODEL}, dùng fallback reranker: {exc}")
        _QWEN_MODEL = None
        return None


def rerank_cross_encoder(
    query: str, candidates: list[dict], top_k: int = 5
) -> list[dict]:
    """
    Rerank candidates sử dụng cross-encoder model.

    Args:
        query: Câu truy vấn
        candidates: List of {'content': str, 'score': float, 'metadata': dict}
        top_k: Số lượng kết quả sau rerank

    Returns:
        List of top_k candidates, re-scored và sorted by rerank_score descending.
    """
    if not candidates or top_k <= 0:
        return []

    model = load_qwen_cross_encoder()
    if model is not None:
        try:
            pairs = [(query, candidate["content"]) for candidate in candidates]
            raw_scores = model.predict(pairs)
            scores = normalize_scores([float(score) for score in raw_scores])
        except Exception:
            scores = [fallback_relevance_score(query, item) for item in candidates]
    else:
        scores = [fallback_relevance_score(query, item) for item in candidates]

    reranked = []
    for candidate, score in zip(candidates, scores):
        item = candidate.copy()
        item["score"] = float(score)
        item.setdefault("metadata", {})
        reranked.append(item)

    reranked.sort(key=lambda item: item["score"], reverse=True)
    return reranked[:top_k]


def rerank_mmr(
    query_embedding: list[float],
    candidates: list[dict],
    top_k: int = 5,
    lambda_param: float = 0.7,
) -> list[dict]:
    """
    Maximal Marginal Relevance — chọn candidates vừa relevant vừa diverse.

    MMR = λ * sim(query, doc) - (1-λ) * max(sim(doc, selected_docs))

    Args:
        query_embedding: Vector embedding của query
        candidates: List of {'content': str, 'score': float, 'embedding': list, 'metadata': dict}
        top_k: Số lượng kết quả
        lambda_param: Trade-off giữa relevance (1.0) và diversity (0.0)

    Returns:
        List of top_k candidates selected by MMR.
    """
    if not candidates or top_k <= 0:
        return []

    enriched = []
    for candidate in candidates:
        item = candidate.copy()
        if "embedding" not in item:
            item["embedding"] = embed_texts([item.get("content", "")])[0]
        enriched.append(item)

    selected = []
    remaining = list(range(len(enriched)))

    for _ in range(min(top_k, len(enriched))):
        best_idx = remaining[0]
        best_score = float("-inf")

        for idx in remaining:
            relevance = cosine_sim(query_embedding, enriched[idx]["embedding"])
            diversity_penalty = 0.0
            if selected:
                diversity_penalty = max(
                    cosine_sim(enriched[idx]["embedding"], enriched[sel_idx]["embedding"])
                    for sel_idx in selected
                )

            mmr_score = lambda_param * relevance - (1 - lambda_param) * diversity_penalty
            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = idx

        enriched[best_idx]["score"] = float(best_score)
        selected.append(best_idx)
        remaining.remove(best_idx)

    return [enriched[index] for index in selected]


def rerank_rrf(
    ranked_lists: list[list[dict]], top_k: int = 5, k: int = 60
) -> list[dict]:
    """
    Reciprocal Rank Fusion — gộp kết quả từ nhiều ranker.

    RRF(d) = Σ 1 / (k + rank_r(d))

    Args:
        ranked_lists: List of ranked result lists (mỗi list từ 1 ranker)
        top_k: Số lượng kết quả cuối cùng
        k: Smoothing constant (default=60, từ paper Cormack et al. 2009)

    Returns:
        List of top_k candidates sorted by RRF score descending.
    """
    if not ranked_lists or top_k <= 0:
        return []

    rrf_scores = {}
    content_map = {}

    for ranked_list in ranked_lists:
        for rank, item in enumerate(ranked_list, 1):
            key = item.get("metadata", {}).get("chunk_id") or item.get("content", "")
            if not key:
                continue
            rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank)
            content_map[key] = item

    sorted_items = sorted(rrf_scores.items(), key=lambda pair: pair[1], reverse=True)
    if not sorted_items:
        return []

    max_score = sorted_items[0][1] or 1.0
    results = []
    for key, score in sorted_items[:top_k]:
        item = content_map[key].copy()
        item["score"] = float(score / max_score)
        item.setdefault("metadata", {})
        results.append(item)

    return results


# =============================================================================
# Main rerank interface
# =============================================================================

def rerank(
    query: str,
    candidates: list[dict],
    top_k: int = 5,
    method: str = "cross_encoder",  # "cross_encoder" | "mmr" | "rrf"
) -> list[dict]:
    """
    Unified reranking interface.

    Args:
        query: Câu truy vấn
        candidates: Danh sách candidates từ retrieval
        top_k: Số lượng kết quả sau rerank
        method: Phương pháp reranking

    Returns:
        List of top_k reranked candidates.
    """
    if method == "cross_encoder":
        return rerank_cross_encoder(query, candidates, top_k)
    elif method == "mmr":
        query_embedding = embed_texts([query])[0]
        return rerank_mmr(query_embedding, candidates, top_k)
    elif method == "rrf":
        ranked_lists = candidates if candidates and isinstance(candidates[0], list) else [candidates]
        return rerank_rrf(ranked_lists, top_k)
    else:
        raise ValueError(f"Unknown rerank method: {method}")


if __name__ == "__main__":
    # Test with dummy data
    dummy_candidates = [
        {"content": "Điều 248: Tội tàng trữ trái phép chất ma tuý", "score": 0.8, "metadata": {}},
        {"content": "Nghệ sĩ X bị bắt vì sử dụng ma tuý", "score": 0.7, "metadata": {}},
        {"content": "Hình phạt tù từ 2-7 năm cho tội tàng trữ", "score": 0.6, "metadata": {}},
    ]
    results = rerank("hình phạt tàng trữ ma tuý", dummy_candidates, top_k=2)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content']}")
