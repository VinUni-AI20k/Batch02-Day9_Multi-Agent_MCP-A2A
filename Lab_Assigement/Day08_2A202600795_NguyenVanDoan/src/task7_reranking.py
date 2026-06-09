"""
Task 7 — Reranking Module.

Chọn 1 trong các phương pháp:
    - Cross-encoder reranker: Jina Reranker v2 (multilingual) hoặc Qwen3-Reranker
    - MMR (Maximal Marginal Relevance): tự implement
    - RRF (Reciprocal Rank Fusion): tự implement

Nếu dùng MMR hoặc RRF, đảm bảo hiểu và giải thích được cơ chế.
"""

from typing import Optional


import os
from typing import Optional
import requests
import numpy as np

def cosine_sim(a: list[float], b: list[float]) -> float:
    """Tính toán Cosine Similarity giữa hai vector."""
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    return float(dot / (norm_a * norm_b + 1e-9))


def rerank_mmr_fallback(query: str, candidates: list[dict], top_k: int = 5) -> list[dict]:
    """Hàm fallback sử dụng cosine similarity của mô hình cục bộ."""
    if not candidates:
        return []
    
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    query_emb = model.encode(query)
    doc_embs = model.encode([c["content"] for c in candidates])
    
    for idx, doc_emb in enumerate(doc_embs):
        sim = cosine_sim(query_emb.tolist(), doc_emb.tolist())
        candidates[idx]["score"] = sim
        
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:top_k]


_jina_disabled = False


def rerank_cross_encoder(
    query: str, candidates: list[dict], top_k: int = 5
) -> list[dict]:
    """
    Rerank candidates sử dụng Jina Reranker API.
    Tự động fallback sang local semantic ranking nếu thiếu API key hoặc lỗi mạng.
    """
    global _jina_disabled
    if not candidates:
        return []

    jina_key = os.getenv("JINA_API_KEY", "")
    if not jina_key or jina_key == "jina_xxx" or _jina_disabled:
        return rerank_mmr_fallback(query, candidates, top_k)

    try:
        response = requests.post(
            "https://api.jina.ai/v1/rerank",
            headers={"Authorization": f"Bearer {jina_key}"},
            json={
                "model": "jina-reranker-v2-base-multilingual",
                "query": query,
                "documents": [c["content"] for c in candidates],
                "top_n": top_k
            },
            timeout=3
        )
        if response.status_code == 200:
            results = response.json().get("results", [])
            reranked = []
            for r in results:
                idx = r["index"]
                item = candidates[idx].copy()
                item["score"] = float(r["relevance_score"])
                reranked.append(item)
            return reranked
        else:
            print(f"  ⚠ Jina Rerank API trả về lỗi HTTP {response.status_code}. Tạm thời vô hiệu hóa Jina API.")
            _jina_disabled = True
    except Exception as e:
        print(f"  ⚠ Lỗi kết nối tới Jina Rerank API: {e}. Tạm thời vô hiệu hóa Jina API.")
        _jina_disabled = True

    return rerank_mmr_fallback(query, candidates, top_k)



def rerank_mmr(
    query_embedding: list[float],
    candidates: list[dict],
    top_k: int = 5,
    lambda_param: float = 0.7,
) -> list[dict]:
    """
    Maximal Marginal Relevance — chọn candidates vừa relevant vừa diverse.
    MMR = λ * sim(query, doc) - (1-λ) * max(sim(doc, selected_docs))
    """
    if not candidates:
        return []

    # Đảm bảo tất cả các ứng viên đều có vector embedding
    has_missing_embeddings = any("embedding" not in c for c in candidates)
    if has_missing_embeddings:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        embs = model.encode([c["content"] for c in candidates])
        for idx, emb in enumerate(embs):
            candidates[idx]["embedding"] = emb.tolist()

    selected = []
    remaining = list(range(len(candidates)))

    for _ in range(min(top_k, len(candidates))):
        best_idx = None
        best_score = float('-inf')

        for idx in remaining:
            # Relevance to query
            relevance = cosine_sim(query_embedding, candidates[idx]["embedding"])

            # Max similarity to already selected
            max_sim_to_selected = 0.0
            for sel_idx in selected:
                sim = cosine_sim(candidates[idx]["embedding"], candidates[sel_idx]["embedding"])
                max_sim_to_selected = max(max_sim_to_selected, sim)

            # MMR score
            mmr_score = lambda_param * relevance - (1 - lambda_param) * max_sim_to_selected

            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = idx

        if best_idx is not None:
            selected.append(best_idx)
            remaining.remove(best_idx)
        else:
            break

    return [candidates[i] for i in selected]


def rerank_rrf(
    ranked_lists: list[list[dict]], top_k: int = 5, k: int = 60
) -> list[dict]:
    """
    Reciprocal Rank Fusion — gộp kết quả từ nhiều ranker.
    RRF(d) = Σ 1 / (k + rank_r(d))
    """
    rrf_scores = {}  # content -> score
    content_map = {}  # content -> full dict

    for ranked_list in ranked_lists:
        for rank, item in enumerate(ranked_list, 1):
            key = item["content"]
            rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank)
            if key not in content_map:
                content_map[key] = item.copy()
            else:
                content_map[key].update(item)

    # Sắp xếp theo RRF score giảm dần
    sorted_items = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

    results = []
    for content, score in sorted_items[:top_k]:
        item = content_map[content]
        item["score"] = float(score)
        results.append(item)

    return results


def rerank(
    query: str,
    candidates: list[dict],
    top_k: int = 5,
    method: str = "cross_encoder",  # "cross_encoder" | "mmr" | "rrf"
) -> list[dict]:
    """
    Unified reranking interface.
    """
    if method == "cross_encoder":
        return rerank_cross_encoder(query, candidates, top_k)
    elif method == "mmr":
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        query_embedding = model.encode(query).tolist()
        return rerank_mmr(query_embedding, candidates, top_k)
    elif method == "rrf":
        # RRF cần một danh sách các danh sách xếp hạng. 
        # Nếu truyền candidates phẳng, chúng ta coi nó là một danh sách đơn.
        return rerank_rrf([candidates], top_k)
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

