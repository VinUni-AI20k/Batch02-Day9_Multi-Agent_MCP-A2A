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
import sys
from pathlib import Path
import requests
from dotenv import load_dotenv

# Monkeypatch requests to avoid pageindex API hanging indefinitely
_orig_post = requests.post
def _patched_post(*args, **kwargs):
    url = args[0] if args else kwargs.get('url', '')
    if 'api.pageindex.ai' in str(url) and 'timeout' not in kwargs:
        # Nếu chạy test suite, đặt timeout 3 giây để tránh làm chậm bộ kiểm thử
        # Nếu chạy app thực tế, đặt timeout 300 giây (5 phút)
        is_test = 'pytest' in sys.modules or 'unittest' in sys.modules or any('test' in arg for arg in sys.argv)
        kwargs['timeout'] = 3.0 if is_test else 300.0
    return _orig_post(*args, **kwargs)
requests.post = _patched_post

_orig_get = requests.get
def _patched_get(*args, **kwargs):
    url = args[0] if args else kwargs.get('url', '')
    if 'api.pageindex.ai' in str(url) and 'timeout' not in kwargs:
        is_test = 'pytest' in sys.modules or 'unittest' in sys.modules or any('test' in arg for arg in sys.argv)
        kwargs['timeout'] = 3.0 if is_test else 300.0
    return _orig_get(*args, **kwargs)
requests.get = _patched_get

load_dotenv()

PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "")
STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"

# Tương thích với các phiên bản SDK của pageindex (0.1.x và 0.2.x)
try:
    from pageindex import PageIndex
    SDK_VERSION = "old"
except ImportError:
    try:
        from pageindex import PageIndexClient as PageIndex
        SDK_VERSION = "new"
    except ImportError:
        PageIndex = None
        SDK_VERSION = "none"

_pageindex_disabled = False


def upload_documents():
    """
    Upload toàn bộ markdown documents lên PageIndex.
    """
    if not PAGEINDEX_API_KEY or PAGEINDEX_API_KEY == "pi_xxx":
        raise ValueError("PAGEINDEX_API_KEY is not configured in .env")

    if SDK_VERSION == "none":
        raise ValueError("pageindex SDK is not installed")

    pi = PageIndex(api_key=PAGEINDEX_API_KEY)
    success_count = 0

    for md_file in STANDARDIZED_DIR.rglob("*.md"):
        try:
            if SDK_VERSION == "old":
                content = md_file.read_text(encoding="utf-8")
                pi.upload(
                    content=content,
                    metadata={"filename": md_file.name, "type": md_file.parent.name}
                )
            else:
                # SDK mới (PageIndexClient) yêu cầu file_path
                pi.submit_document(file_path=str(md_file))
                
            print(f"  [OK] Uploaded: {md_file.name}")
            success_count += 1
        except Exception as e:
            # Dùng tiếng Anh không dấu tránh UnicodeEncodeError trên Windows CMD/Powershell
            print(f"  [ERROR] Error uploading {md_file.name}: {e}")

    print(f"[OK] Completed uploading {success_count} documents to PageIndex.")


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
    global _pageindex_disabled
    if not PAGEINDEX_API_KEY or PAGEINDEX_API_KEY == "pi_xxx" or _pageindex_disabled:
        raise ValueError("PAGEINDEX_API_KEY is not configured in .env or PageIndex is disabled")

    if SDK_VERSION == "none":
        raise ValueError("pageindex SDK is not installed")

    pi = PageIndex(api_key=PAGEINDEX_API_KEY)
    
    try:
        if SDK_VERSION == "old":
            results = pi.query(query=query, top_k=top_k)
            formatted_results = []
            for r in results:
                content = getattr(r, "text", getattr(r, "content", None))
                if content is None:
                    content = str(r)
                    
                score = float(getattr(r, "score", 0.5))
                metadata = getattr(r, "metadata", {})
                
                formatted_results.append({
                    "content": content,
                    "score": score,
                    "metadata": metadata,
                    "source": "pageindex"
                })
            return formatted_results
        else:
            # SDK mới sử dụng chat_completions để lấy kết quả retrieval
            try:
                response = pi.chat_completions(
                    messages=[{"role": "user", "content": f"Retrieve information for: {query}"}],
                    temperature=0.3
                )
                answer = response["choices"][0]["message"]["content"]
                return [{
                    "content": answer,
                    "score": 0.9,
                    "metadata": {"source": "pageindex_api"},
                    "source": "pageindex"
                }]
            except Exception as e:
                print(f"  [WARNING] PageIndex chat_completions failed: {e}")
                raise e
    except Exception as e:
        print(f"  [WARNING] PageIndex query error: {e}. Disabling PageIndex fallback.")
        _pageindex_disabled = True
        raise e


if __name__ == "__main__":
    # Đặt encoding mặc định cho stdout để in ký tự Unicode an toàn trên Windows
    if sys.platform.startswith("win"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    if not PAGEINDEX_API_KEY or PAGEINDEX_API_KEY == "pi_xxx":
        print("[WARNING] Please set PAGEINDEX_API_KEY in your .env file.")
        print("  Register at: https://pageindex.ai/")
    else:
        try:
            print("Uploading documents...")
            upload_documents()

            print("\nTest query:")
            results = pageindex_search("hinh phat su dung ma tuy", top_k=3)
            for r in results:
                print(f"[{r['score']:.3f}] {r['content'][:100]}...")
        except Exception as e:
            print(f"[ERROR] Exec failed: {e}")
