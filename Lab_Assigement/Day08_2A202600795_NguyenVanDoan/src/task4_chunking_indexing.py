"""
Task 4 — Chunking & Indexing vào Vector Store.

Hướng dẫn:
    1. Đọc toàn bộ markdown files từ data/standardized/
    2. Chọn 1 chunking strategy (giải thích lý do)
    3. Chọn 1 embedding model (giải thích lý do)
    4. Index vào vector store (Weaviate khuyến cáo)

Chunking options (langchain-text-splitters):
    - RecursiveCharacterTextSplitter: an toàn, phổ biến
    - MarkdownHeaderTextSplitter: tốt cho file có heading
    - SemanticChunker: dùng embedding để tách (nâng cao)

Embedding model options:
    - sentence-transformers/all-MiniLM-L6-v2 (384 dim, nhẹ)
    - BAAI/bge-m3 (1024 dim, multilingual, tốt cho tiếng Việt)
    - OpenAI text-embedding-3-small (1536 dim, API)

Vector store options:
    - Weaviate (khuyến cáo: hỗ trợ hybrid search built-in)
    - ChromaDB (đơn giản, local)
    - FAISS (chỉ dense search)

Cài đặt:
    pip install langchain-text-splitters sentence-transformers weaviate-client
"""

from pathlib import Path

import os
import sys
from pathlib import Path
import chromadb
from chromadb.config import Settings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"

# =============================================================================
# CONFIGURATION — Giải thích lựa chọn của bạn trong comment
# =============================================================================

# Lựa chọn CHUNK_SIZE = 500 ký tự (khoảng 100-120 từ tiếng Việt):
# Kích thước này đủ để chứa trọn vẹn một điều luật hoặc một đoạn tin tức nhỏ mà không bị rời rạc ngữ nghĩa.
# CHUNK_OVERLAP = 50 ký tự: Giúp giữ ngữ cảnh chuyển tiếp giữa các phân đoạn liên tiếp.
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
CHUNKING_METHOD = "recursive"

# Sử dụng model sentence-transformers/all-MiniLM-L6-v2 (384 chiều):
# Model này cực kỳ nhẹ (chỉ khoảng 80MB), tốc độ suy luận nhanh và chạy mượt mà trên CPU của máy cá nhân.
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# Sử dụng ChromaDB làm Vector Store:
# ChromaDB hoạt động hoàn toàn cục bộ (local), gọn nhẹ, lưu trữ dạng file hoặc trong bộ nhớ mà không cần Docker.
VECTOR_STORE = "chromadb"


# =============================================================================
# IMPLEMENTATION
# =============================================================================

def load_documents() -> list[dict]:
    """
    Đọc toàn bộ markdown files từ data/standardized/.

    Returns:
        List of {'content': str, 'metadata': {'source': str, 'type': str}}
    """
    if not STANDARDIZED_DIR.exists():
        print(f"⚠ Thư mục {STANDARDIZED_DIR} không tồn tại!")
        return []

    documents = []
    for md_file in STANDARDIZED_DIR.rglob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")
            doc_type = "legal" if "legal" in md_file.parts else "news"
            documents.append({
                "content": content,
                "metadata": {"source": md_file.name, "type": doc_type}
            })
            print(f"  [OK] Loaded document: {md_file.name} (type: {doc_type})")
        except Exception as e:
            print(f"  [ERROR] Error reading {md_file.name}: {e}")
            
    return documents


def chunk_documents(documents: list[dict]) -> list[dict]:
    """
    Chunk documents theo strategy đã chọn (RecursiveCharacterTextSplitter).

    Returns:
        List of {'content': str, 'metadata': dict} — mỗi item là 1 chunk
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    
    chunks = []
    for doc in documents:
        splits = splitter.split_text(doc["content"])
        for i, chunk_text in enumerate(splits):
            if chunk_text.strip():  # Chỉ lấy các chunk không rỗng
                chunks.append({
                    "content": chunk_text,
                    "metadata": {
                        "source": doc["metadata"]["source"],
                        "type": doc["metadata"]["type"],
                        "chunk_index": i
                    }
                })
    return chunks


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """
    Embed toàn bộ chunks bằng model đã chọn.

    Returns:
        Mỗi chunk dict được thêm key 'embedding': list[float]
    """
    if not chunks:
        return []
        
    print(f"Loading embedding model: {EMBEDDING_MODEL}...")
    model = SentenceTransformer(EMBEDDING_MODEL)
    
    texts = [c["content"] for c in chunks]
    print(f"Generating embeddings for {len(chunks)} chunks...")
    embeddings = model.encode(texts, show_progress_bar=True)
    
    for chunk, emb in zip(chunks, embeddings):
        chunk["embedding"] = emb.tolist()
        
    return chunks


def index_to_vectorstore(chunks: list[dict]):
    """
    Lưu chunks vào vector store đã chọn (ChromaDB).
    """
    if not chunks:
        print("⚠ Không có chunk nào để index!")
        return

    db_path = Path(__file__).parent.parent / "data" / "chromadb"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Connecting to ChromaDB at: {db_path}...")
    # Khởi tạo persistent client lưu trữ dữ liệu tại data/chromadb/
    client = chromadb.PersistentClient(path=str(db_path))
    
    # Xóa collection cũ để tránh lẫn lộn dữ liệu tiếng Anh mẫu cũ
    try:
        client.delete_collection(name="DrugLawDocs")
        print("Dropped existing collection 'DrugLawDocs'")
    except Exception:
        pass
        
    # Tạo collection mới sạch sẽ
    collection = client.create_collection(
        name="DrugLawDocs",
        metadata={"hnsw:space": "cosine"}
    )
    
    # Chuẩn bị dữ liệu để thêm vào collection
    embeddings = [c["embedding"] for c in chunks]
    documents = [c["content"] for c in chunks]
    metadatas = [c["metadata"] for c in chunks]
    ids = [f"{c['metadata']['source']}_chunk_{c['metadata']['chunk_index']}" for c in chunks]
    
    print(f"Inserting {len(chunks)} chunks into collection 'DrugLawDocs'...")
    # Thêm dữ liệu vào ChromaDB
    collection.add(
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )
    print("[OK] Indexing hoan tat!")


def run_pipeline():
    """Chạy toàn bộ pipeline: load → chunk → embed → index."""
    print("=" * 50)
    print("Task 4: Chunking & Indexing")
    print(f"  Chunking: {CHUNKING_METHOD} (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    print(f"  Embedding: {EMBEDDING_MODEL} (dim={EMBEDDING_DIM})")
    print(f"  Vector Store: {VECTOR_STORE}")
    print("=" * 50)

    docs = load_documents()
    print(f"\n[OK] Loaded {len(docs)} documents")

    chunks = chunk_documents(docs)
    print(f"[OK] Created {len(chunks)} chunks")

    chunks = embed_chunks(chunks)
    print(f"[OK] Embedded {len(chunks)} chunks")

    index_to_vectorstore(chunks)
    print("[OK] Indexed to vector store")


if __name__ == "__main__":
    # Đặt stdout về UTF-8 để in tiếng Việt an toàn trên Windows
    if sys.platform.startswith("win"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        
    run_pipeline()

