"""
Task 5 — Semantic Search Module.

Viết module tìm kiếm ngữ nghĩa (dense retrieval) trên vector store.

Yêu cầu:
    - Input: query string + top_k
    - Output: danh sách chunks có score, sorted descending
    - Phải tương thích với embedding model và vector store ở Task 4
"""


import chromadb
from pathlib import Path
from sentence_transformers import SentenceTransformer


def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    """
    Tìm kiếm ngữ nghĩa sử dụng vector similarity trên ChromaDB.

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
    # 1. Đường dẫn tới DB và kết nối
    db_path = Path(__file__).parent.parent / "data" / "chromadb"
    if not db_path.exists():
        print(f"⚠ ChromaDB chưa được tạo tại {db_path}!")
        return []

    client = chromadb.PersistentClient(path=str(db_path))
    
    try:
        collection = client.get_collection(name="DrugLawDocs")
    except Exception as e:
        print(f"⚠ Không thể lấy collection 'DrugLawDocs': {e}")
        return []

    # 2. Sinh embedding cho query bằng model giống ở Task 4
    model_name = "sentence-transformers/all-MiniLM-L6-v2"
    model = SentenceTransformer(model_name)
    query_embedding = model.encode(query).tolist()

    # 3. Query collection
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )

    # 4. Chuyển đổi khoảng cách cosine sang điểm số tương đồng và định dạng đầu ra
    formatted_results = []
    if results and "documents" in results and results["documents"]:
        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        for doc, meta, dist in zip(documents, metadatas, distances):
            # similarity = 1 - cosine_distance
            score = 1.0 - float(dist)
            formatted_results.append({
                "content": doc,
                "score": score,
                "metadata": meta
            })

    # 5. Sắp xếp giảm dần theo score
    formatted_results.sort(key=lambda x: x["score"], reverse=True)
    return formatted_results[:top_k]


if __name__ == "__main__":
    # Test
    results = semantic_search("hình phạt cho tội tàng trữ ma tuý", top_k=5)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:100]}...")

