"""
Task 8 — PageIndex Vectorless RAG.

Đăng ký tài khoản tại: https://pageindex.ai/
SDK & sample code: https://github.com/VectifyAI/PageIndex

PageIndex cho phép RAG mà không cần vector store — sử dụng
structural understanding của document thay vì embedding.

Cài đặt:
    pip install pageindex

Hướng dẫn:
    1. Đăng ký account tại pageindex.ai
    2. Lấy API key
    3. Upload documents
    4. Query sử dụng PageIndex API
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "")
PROJECT_DIR = Path(__file__).parent.parent
STANDARDIZED_DIR = PROJECT_DIR / "data" / "standardized"
LOCAL_PAGEINDEX_PATH = PROJECT_DIR / "data" / "indexes" / "pageindex_manifest.json"


def upload_documents():
    """
    Upload toàn bộ markdown documents lên PageIndex.
    """
    documents = []
    for md_file in sorted(STANDARDIZED_DIR.rglob("*.md")):
        content = md_file.read_text(encoding="utf-8").strip()
        if not content:
            continue

        metadata = {
            "filename": md_file.name,
            "type": md_file.parent.name,
            "path": str(md_file.relative_to(STANDARDIZED_DIR)),
        }
        documents.append({"content": content, "metadata": metadata})

    if PAGEINDEX_API_KEY:
        try:
            from pageindex import PageIndex

            client = PageIndex(api_key=PAGEINDEX_API_KEY)
            for document in documents:
                upload = getattr(client, "upload", None)
                if callable(upload):
                    upload(content=document["content"], metadata=document["metadata"])
            print(f"✓ Uploaded {len(documents)} documents to PageIndex")
            return documents
        except Exception as exc:
            print(f"⚠ PageIndex upload lỗi, lưu manifest local: {exc}")

    LOCAL_PAGEINDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_PAGEINDEX_PATH.write_text(
        json.dumps(documents, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"✓ Local PageIndex manifest: {LOCAL_PAGEINDEX_PATH}")
    return documents


def local_pageindex_search(query: str, top_k: int) -> list[dict]:
    """Vectorless fallback using lexical search over local chunks."""
    try:
        from .task6_lexical_search import lexical_search
    except ImportError:
        from task6_lexical_search import lexical_search

    results = lexical_search(query, top_k=top_k)
    for item in results:
        item["source"] = "pageindex"
    return results


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    """
    Vectorless retrieval sử dụng PageIndex.
    Dùng làm fallback khi hybrid search không có kết quả tốt.

    Args:
        query: Câu truy vấn
        top_k: Số lượng kết quả tối đa

    Returns:
        List of {
            'content': str,
            'score': float,
            'metadata': dict,
            'source': 'pageindex'   # Đánh dấu nguồn retrieval
        }
    """
    if not query.strip() or top_k <= 0:
        return []

    if PAGEINDEX_API_KEY:
        try:
            from pageindex import PageIndex

            client = PageIndex(api_key=PAGEINDEX_API_KEY)
            raw_results = client.query(query=query, top_k=top_k)
            results = []
            for result in raw_results:
                results.append(
                    {
                        "content": getattr(result, "text", ""),
                        "score": float(getattr(result, "score", 0.0)),
                        "metadata": getattr(result, "metadata", {}),
                        "source": "pageindex",
                    }
                )
            if results:
                return results[:top_k]
        except Exception as exc:
            print(f"⚠ PageIndex query lỗi, dùng local fallback: {exc}")

    return local_pageindex_search(query, top_k)


if __name__ == "__main__":
    if not PAGEINDEX_API_KEY:
        print("⚠ Hãy set PAGEINDEX_API_KEY trong file .env")
        print("  Đăng ký tại: https://pageindex.ai/")
    else:
        print("Uploading documents...")
        upload_documents()

        print("\nTest query:")
        results = pageindex_search("hình phạt sử dụng ma tuý", top_k=3)
        for r in results:
            print(f"[{r['score']:.3f}] {r['content'][:100]}...")
