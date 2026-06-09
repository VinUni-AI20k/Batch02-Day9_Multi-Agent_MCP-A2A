"""Task 6 - Lexical search with Elasticsearch and local BM25 fallback.

Elasticsearch duoc chon cho lexical retrieval vi search engine nay dung BM25
mac dinh, ho tro analyzer, field boosting va scale tot khi corpus lon. Neu local
Elasticsearch chua chay, module tu dong fallback sang BM25 Python de workflow
van hoan thanh trong moi truong lop hoc/test.
"""

import math
import os
import re
from collections import Counter
from dataclasses import dataclass

try:
    from .task4_chunking_indexing import ensure_index
except ImportError:
    from task4_chunking_indexing import ensure_index

ELASTICSEARCH_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
ELASTICSEARCH_INDEX = os.getenv("ELASTICSEARCH_INDEX", "drug_law_chunks")
USE_ELASTICSEARCH = os.getenv("USE_ELASTICSEARCH", "1") != "0"

CORPUS: list[dict] = []
_BM25_INDEX = None
_ES_READY = None


def tokenize(text: str) -> list[str]:
    """Tokenize tieng Viet don gian cho BM25 fallback."""
    return re.findall(r"[\wÀ-ỹ]+", text.lower(), flags=re.UNICODE)


def load_corpus() -> list[dict]:
    """Load chunk corpus from Task 4 local vector index."""
    global CORPUS
    if CORPUS:
        return CORPUS

    CORPUS = [
        {
            "content": chunk["content"],
            "metadata": chunk.get("metadata", {}),
        }
        for chunk in ensure_index()
    ]
    return CORPUS


@dataclass
class LocalBM25:
    corpus: list[dict]
    tokenized_corpus: list[list[str]]
    k1: float = 1.5
    b: float = 0.75

    def __post_init__(self):
        self.doc_freq = Counter()
        self.doc_lengths = [len(tokens) for tokens in self.tokenized_corpus]
        self.avgdl = (
            sum(self.doc_lengths) / len(self.doc_lengths)
            if self.doc_lengths
            else 0.0
        )

        for tokens in self.tokenized_corpus:
            for token in set(tokens):
                self.doc_freq[token] += 1

        self.num_docs = len(self.tokenized_corpus)

    def idf(self, token: str) -> float:
        freq = self.doc_freq.get(token, 0)
        return math.log(1 + (self.num_docs - freq + 0.5) / (freq + 0.5))

    def get_scores(self, query_tokens: list[str]) -> list[float]:
        scores = []
        for tokens, doc_len in zip(self.tokenized_corpus, self.doc_lengths):
            term_counts = Counter(tokens)
            score = 0.0
            for token in query_tokens:
                tf = term_counts.get(token, 0)
                if tf == 0:
                    continue
                denominator = tf + self.k1 * (
                    1 - self.b + self.b * doc_len / (self.avgdl or 1.0)
                )
                score += self.idf(token) * (tf * (self.k1 + 1)) / denominator
            scores.append(score)
        return scores


def build_bm25_index(corpus: list[dict]):
    """
    Xây dựng BM25 fallback index từ corpus.

    Args:
        corpus: List of {'content': str, 'metadata': dict}
    """
    tokenized_corpus = [tokenize(doc["content"]) for doc in corpus]
    return LocalBM25(corpus=corpus, tokenized_corpus=tokenized_corpus)


def get_bm25_index():
    """Lazily build BM25 fallback index."""
    global _BM25_INDEX
    if _BM25_INDEX is None:
        _BM25_INDEX = build_bm25_index(load_corpus())
    return _BM25_INDEX


def get_elasticsearch_client():
    """Return Elasticsearch client when server is reachable."""
    global _ES_READY
    if not USE_ELASTICSEARCH:
        return None
    if _ES_READY is False:
        return None

    try:
        from elasticsearch import Elasticsearch

        client = Elasticsearch(
            ELASTICSEARCH_URL,
            request_timeout=0.5,
            retry_on_timeout=False,
            max_retries=0,
        )
        if not client.ping():
            _ES_READY = False
            return None
        _ES_READY = True
        return client
    except Exception:
        _ES_READY = False
        return None


def ensure_elasticsearch_index(client, corpus: list[dict]) -> bool:
    """Create/update the Elasticsearch BM25 index when a server is available."""
    try:
        if client.indices.exists(index=ELASTICSEARCH_INDEX):
            return True

        client.indices.create(
            index=ELASTICSEARCH_INDEX,
            mappings={
                "properties": {
                    "content": {"type": "text"},
                    "source": {"type": "keyword"},
                    "doc_type": {"type": "keyword"},
                    "chunk_id": {"type": "keyword"},
                }
            },
        )

        for i, doc in enumerate(corpus):
            metadata = doc.get("metadata", {})
            client.index(
                index=ELASTICSEARCH_INDEX,
                id=metadata.get("chunk_id", str(i)),
                document={
                    "content": doc["content"],
                    "source": metadata.get("source", ""),
                    "doc_type": metadata.get("type", ""),
                    "chunk_id": metadata.get("chunk_id", str(i)),
                    "metadata": metadata,
                },
            )
        client.indices.refresh(index=ELASTICSEARCH_INDEX)
        return True
    except Exception:
        return False


def elasticsearch_search(query: str, top_k: int) -> list[dict]:
    """Search Elasticsearch BM25 index if available."""
    corpus = load_corpus()
    client = get_elasticsearch_client()
    if client is None or not ensure_elasticsearch_index(client, corpus):
        return []

    try:
        response = client.search(
            index=ELASTICSEARCH_INDEX,
            query={"match": {"content": {"query": query, "operator": "or"}}},
            size=top_k,
        )
        results = []
        for hit in response.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            results.append(
                {
                    "content": source.get("content", ""),
                    "score": float(hit.get("_score", 0.0)),
                    "metadata": source.get("metadata", {}),
                }
            )
        return results
    except Exception:
        return []


def bm25_search(query: str, top_k: int) -> list[dict]:
    """Local BM25 fallback search."""
    corpus = load_corpus()
    if not corpus:
        return []

    bm25 = get_bm25_index()
    query_tokens = tokenize(query)
    scores = bm25.get_scores(query_tokens)
    ranked_indices = sorted(
        range(len(scores)),
        key=lambda index: scores[index],
        reverse=True,
    )

    results = []
    for index in ranked_indices[:top_k]:
        score = float(scores[index])
        if score <= 0:
            continue
        results.append(
            {
                "content": corpus[index]["content"],
                "score": score,
                "metadata": corpus[index].get("metadata", {}),
            }
        )
    return results


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
    if not query.strip() or top_k <= 0:
        return []

    results = elasticsearch_search(query, top_k)
    if not results:
        results = bm25_search(query, top_k)

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:top_k]


if __name__ == "__main__":
    # Test
    results = lexical_search("Điều 248 tàng trữ trái phép chất ma tuý", top_k=5)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:100]}...")
