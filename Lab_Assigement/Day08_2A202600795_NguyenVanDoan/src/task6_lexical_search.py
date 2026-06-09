"""
Task 6 — Lexical Search Module (BM25).

Mặc định sử dụng BM25. Nếu dùng phương pháp khác (TF-IDF, Elasticsearch,
Weaviate BM25 built-in), hãy giải thích cơ chế trong buổi demo → +5 bonus.

Cài đặt:
    pip install rank-bm25

BM25 hoạt động thế nào:
    - Term Frequency (TF): từ xuất hiện nhiều trong document → điểm cao
    - Inverse Document Frequency (IDF): từ hiếm → quan trọng hơn
    - Document length normalization: document dài không bị ưu tiên quá mức
    - Formula: score(q,d) = Σ IDF(qi) * (tf(qi,d) * (k1+1)) / (tf(qi,d) + k1*(1-b+b*|d|/avgdl))
    - k1=1.5 (term saturation), b=0.75 (length normalization)
"""

from pathlib import Path
from rank_bm25 import BM25Okapi

# Lazy loading corpus & index
_bm25_index = None
_corpus: list[dict] = []  # List of {'content': str, 'metadata': dict}


def build_bm25_index(corpus: list[dict]):
    """
    Xây dựng BM25 index từ corpus.

    Args:
        corpus: List of {'content': str, 'metadata': dict}
    """
    tokenized_corpus = [doc["content"].lower().split() for doc in corpus]
    return BM25Okapi(tokenized_corpus)


def get_index_and_corpus():
    """Lấy BM25 index và corpus, tự động tải nếu chưa được tạo."""
    global _bm25_index, _corpus
    if _bm25_index is None:
        from .task4_chunking_indexing import load_documents, chunk_documents
        try:
            docs = load_documents()
            _corpus = chunk_documents(docs)
            print(f"BM25 Corpus built with {len(_corpus)} chunks.")
        except Exception as e:
            print(f"⚠ Không thể tải corpus cho BM25: {e}")
            _corpus = []

        if _corpus:
            _bm25_index = build_bm25_index(_corpus)
            
    return _bm25_index, _corpus


def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    """
    Tìm kiếm từ khóa sử dụng BM25.

    Args:
        query: Câu truy vấn
        top_k: Số lượng kết quả tối đa

    Returns:
        List of {
            'content': str,
            'score': float,      # BM25 score
            'metadata': dict
        }
        Sorted by score descending.
    """
    bm25, corpus = get_index_and_corpus()
    if not bm25 or not corpus:
        return []

    # Tokenize câu truy vấn
    tokenized_query = query.lower().split()
    scores = bm25.get_scores(tokenized_query)

    # Lấy index và score, sắp xếp giảm dần theo score
    indexed_scores = list(enumerate(scores))
    indexed_scores.sort(key=lambda x: x[1], reverse=True)

    results = []
    for idx, score in indexed_scores:
        # Chỉ lấy các kết quả có điểm lớn hơn 0 (có khớp ít nhất 1 từ khóa)
        if score > 0:
            results.append({
                "content": corpus[idx]["content"],
                "score": float(score),
                "metadata": corpus[idx]["metadata"]
            })
            if len(results) == top_k:
                break
                
    return results


if __name__ == "__main__":
    # Test
    results = lexical_search("Điều 248 tàng trữ trái phép chất ma tuý", top_k=5)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:100]}...")

