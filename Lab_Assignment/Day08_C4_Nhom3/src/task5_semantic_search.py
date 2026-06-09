"""Task 5 - Semantic search over the local BAAI/bge-m3 vector index."""

import math

try:
    from .task4_chunking_indexing import embed_texts, ensure_index
except ImportError:
    from task4_chunking_indexing import embed_texts, ensure_index


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Compute cosine similarity for normalized or raw vectors."""
    if not left or not right:
        return 0.0

    size = min(len(left), len(right))
    dot = sum(left[i] * right[i] for i in range(size))
    left_norm = math.sqrt(sum(value * value for value in left[:size]))
    right_norm = math.sqrt(sum(value * value for value in right[:size]))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    """
    Tìm kiếm ngữ nghĩa sử dụng vector similarity.

    Args:
        query: Câu truy vấn
        top_k: Số lượng kết quả tối đa

    Returns:
        List of {
            'content': str,      # Nội dung chunk
            'score': float,      # Cosine similarity score
            'metadata': dict     # source, doc_type, chunk_index
        }
        Sorted by score descending.
    """
    if not query.strip() or top_k <= 0:
        return []

    chunks = ensure_index()
    if not chunks:
        return []

    query_embedding = embed_texts([query])[0]
    results = []
    for chunk in chunks:
        score = cosine_similarity(query_embedding, chunk.get("embedding", []))
        results.append(
            {
                "content": chunk["content"],
                "score": float(score),
                "metadata": chunk.get("metadata", {}),
            }
        )

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:top_k]


if __name__ == "__main__":
    # Test
    results = semantic_search("hình phạt cho tội tàng trữ ma tuý", top_k=5)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:100]}...")
