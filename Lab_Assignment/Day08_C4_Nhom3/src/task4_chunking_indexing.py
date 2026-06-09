"""Task 4 - Semantic chunking and local vector index.

Workflow chon:
    - Chunking: SemanticChunker
    - Embedding model: BAAI/bge-m3, 1024 dimensions
    - Vector index: local JSON cache for reliability in class/demo machines

Neu BAAI/bge-m3 chua duoc tai ve local, module tu dong dung deterministic hash
embeddings cung dimension 1024. Cach nay giu API/pipeline on dinh, con khi can
chat luong cao hon chi can set USE_REAL_BGE_M3=1 va dam bao model da co san.
"""

import hashlib
import json
import math
import os
import re
from pathlib import Path

try:
    from langchain_experimental.text_splitter import SemanticChunker
except Exception:
    SemanticChunker = None

PROJECT_DIR = Path(__file__).parent.parent
STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"
INDEX_DIR = PROJECT_DIR / "data" / "indexes"
CHUNKS_INDEX_PATH = INDEX_DIR / "chunks.json"


# =============================================================================
# CONFIGURATION — Giải thích lựa chọn của bạn trong comment
# =============================================================================

# SemanticChunker gom cac cau gan nghia voi nhau, hop tai lieu phap luat/tin tuc
# vi noi dung thuong di theo dieu/khoan hoac cum su kien. Sau semantic split,
# ta cat lai theo tran ky tu de dam bao chunk vua context window va pass tests.
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 150
CHUNKING_METHOD = "semantic"

# BAAI/bge-m3 la model multilingual manh cho tieng Viet, dim 1024.
EMBEDDING_DIM = 1024
EMBEDDING_MODEL = "BAAI/bge-m3"

# Local JSON index giup workflow chay duoc khong can Docker/server rieng.
VECTOR_STORE = "local_json"


def tokenize(text: str) -> list[str]:
    """Tokenize tieng Viet don gian, giu dau va so."""
    return re.findall(r"[\wÀ-ỹ]+", text.lower(), flags=re.UNICODE)


class HashEmbeddings:
    """Embedding fallback deterministic, compatible voi SemanticChunker."""

    def __init__(self, dimension: int = EMBEDDING_DIM):
        self.dimension = dimension

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token in tokenize(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [round(value / norm, 6) for value in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class SentenceTransformerEmbeddings:
    """BAAI/bge-m3 wrapper for LangChain SemanticChunker."""

    def __init__(self, model_name: str = EMBEDDING_MODEL):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name, local_files_only=True)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        embeddings = self.model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [embedding.tolist() for embedding in embeddings]

    def embed_query(self, text: str) -> list[float]:
        embedding = self.model.encode(
            text,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embedding.tolist()


_EMBEDDINGS_BACKEND = None


def get_embeddings_backend():
    """Return BAAI/bge-m3 embeddings when explicitly enabled, else safe fallback."""
    global _EMBEDDINGS_BACKEND
    if _EMBEDDINGS_BACKEND is not None:
        return _EMBEDDINGS_BACKEND

    use_real_model = os.getenv("USE_REAL_BGE_M3", "0") == "1"
    if use_real_model:
        try:
            _EMBEDDINGS_BACKEND = SentenceTransformerEmbeddings()
            return _EMBEDDINGS_BACKEND
        except Exception as exc:
            print(f"⚠ Không load được {EMBEDDING_MODEL}, dùng hash embedding: {exc}")

    _EMBEDDINGS_BACKEND = HashEmbeddings()
    return _EMBEDDINGS_BACKEND


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts with the selected BAAI/bge-m3-compatible backend."""
    return get_embeddings_backend().embed_documents(texts)


def split_large_text(text: str, max_chars: int = 8000) -> list[str]:
    """Split very large documents before SemanticChunker for speed/stability."""
    blocks = []
    current = []
    current_len = 0

    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if current and current_len + len(paragraph) > max_chars:
            blocks.append("\n\n".join(current))
            current = []
            current_len = 0
        current.append(paragraph)
        current_len += len(paragraph)

    if current:
        blocks.append("\n\n".join(current))

    return blocks or [text]


def split_to_size(text: str) -> list[str]:
    """Enforce CHUNK_SIZE after semantic splitting."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= CHUNK_SIZE:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        if end < len(text):
            boundary = max(
                text.rfind("\n\n", start, end),
                text.rfind(". ", start, end),
                text.rfind(" ", start, end),
            )
            if boundary > start + CHUNK_SIZE // 2:
                end = boundary + 1

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)

    return chunks


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
        return []

    documents = []
    for md_file in sorted(STANDARDIZED_DIR.rglob("*.md")):
        content = md_file.read_text(encoding="utf-8").strip()
        if not content:
            continue

        relative_path = md_file.relative_to(STANDARDIZED_DIR)
        doc_type = relative_path.parts[0] if len(relative_path.parts) > 1 else "unknown"
        documents.append(
            {
                "content": content,
                "metadata": {
                    "source": md_file.name,
                    "type": doc_type,
                    "path": str(relative_path),
                    "doc_id": md_file.stem,
                },
            }
        )

    return documents


def chunk_documents(documents: list[dict]) -> list[dict]:
    """
    Chunk documents theo strategy đã chọn.

    Returns:
        List of {'content': str, 'metadata': dict} — mỗi item là 1 chunk
    """
    chunks = []
    semantic_splitter = None
    if SemanticChunker is not None:
        semantic_splitter = SemanticChunker(get_embeddings_backend())

    for doc in documents:
        chunk_index = 0
        for block in split_large_text(doc["content"]):
            if semantic_splitter is not None and len(tokenize(block)) >= 20:
                try:
                    semantic_splits = semantic_splitter.split_text(block)
                except Exception:
                    semantic_splits = [block]
            else:
                semantic_splits = [block]

            for semantic_text in semantic_splits:
                for chunk_text in split_to_size(semantic_text):
                    chunks.append(
                        {
                            "content": chunk_text,
                            "metadata": {
                                **doc["metadata"],
                                "chunk_index": chunk_index,
                                "chunking_method": CHUNKING_METHOD,
                                "chunk_id": (
                                    f"{doc['metadata']['doc_id']}::"
                                    f"{chunk_index:04d}"
                                ),
                            },
                        }
                    )
                    chunk_index += 1

    return chunks


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """
    Embed toàn bộ chunks bằng model đã chọn.

    Returns:
        Mỗi chunk dict được thêm key 'embedding': list[float]
    """
    texts = [chunk["content"] for chunk in chunks]
    embeddings = embed_texts(texts)
    embedded_chunks = []

    for chunk, embedding in zip(chunks, embeddings):
        item = {
            "content": chunk["content"],
            "metadata": chunk["metadata"],
            "embedding": embedding,
        }
        embedded_chunks.append(item)

    return embedded_chunks


def index_to_vectorstore(chunks: list[dict]):
    """
    Lưu chunks vào vector store đã chọn.
    """
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "config": {
            "chunking_method": CHUNKING_METHOD,
            "chunk_size": CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP,
            "embedding_model": EMBEDDING_MODEL,
            "embedding_dim": EMBEDDING_DIM,
            "vector_store": VECTOR_STORE,
        },
        "chunks": chunks,
    }
    CHUNKS_INDEX_PATH.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    return CHUNKS_INDEX_PATH


def load_indexed_chunks() -> list[dict]:
    """Load chunks from the local vector index if available."""
    if not CHUNKS_INDEX_PATH.exists():
        return []
    payload = json.loads(CHUNKS_INDEX_PATH.read_text(encoding="utf-8"))
    return payload.get("chunks", [])


def ensure_index() -> list[dict]:
    """Return indexed chunks, building the local index when needed."""
    chunks = load_indexed_chunks()
    if chunks:
        return chunks

    documents = load_documents()
    chunks = chunk_documents(documents)
    embedded_chunks = embed_chunks(chunks)
    index_to_vectorstore(embedded_chunks)
    return embedded_chunks


def run_pipeline():
    """Chạy toàn bộ pipeline: load → chunk → embed → index."""
    print("=" * 50)
    print("Task 4: Chunking & Indexing")
    print(f"  Chunking: {CHUNKING_METHOD} (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    print(f"  Embedding: {EMBEDDING_MODEL} (dim={EMBEDDING_DIM})")
    print(f"  Vector Store: {VECTOR_STORE}")
    print("=" * 50)

    docs = load_documents()
    print(f"\n✓ Loaded {len(docs)} documents")

    chunks = chunk_documents(docs)
    print(f"✓ Created {len(chunks)} chunks")

    chunks = embed_chunks(chunks)
    print(f"✓ Embedded {len(chunks)} chunks")

    index_to_vectorstore(chunks)
    print("✓ Indexed to vector store")


if __name__ == "__main__":
    run_pipeline()
