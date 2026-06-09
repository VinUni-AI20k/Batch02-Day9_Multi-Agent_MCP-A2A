"""
Task 10 — Generation Có Citation.

Hướng dẫn:
    1. Chọn top_k, top_p phù hợp (giải thích lý do)
    2. Sắp xếp lại chunks sau reranking để tránh "lost in the middle"
    3. Inject context vào prompt
    4. Yêu cầu LLM trả lời có citation
    5. Nếu không đủ evidence → "I cannot verify this information"
"""

import os
import re
from dotenv import load_dotenv

load_dotenv()

try:
    from .task9_retrieval_pipeline import retrieve
except ImportError:
    from task9_retrieval_pipeline import retrieve


# =============================================================================
# CONFIGURATION — Giải thích lựa chọn
# =============================================================================

# top_k: Số chunks đưa vào context
# Chọn 5 vì: đủ evidence mà không quá dài gây lost in the middle
TOP_K = 5

# top_p (nucleus sampling): Xác suất tích luỹ cho token generation
# Chọn 0.9 vì: đủ diverse nhưng không quá random
TOP_P = 0.9

# temperature: Độ ngẫu nhiên của output
# Chọn 0.3 vì: RAG cần factual, ít sáng tạo
TEMPERATURE = 0.3


# =============================================================================
# SYSTEM PROMPT
# =============================================================================

SYSTEM_PROMPT = """Answer the following question comprehensively in Vietnamese.
For every statement of fact or claim, immediately insert a citation in brackets
linking to the specific source (e.g., [Luật Phòng chống ma tuý 2021, Điều 3]
or [VnExpress, 2024]).

If the information is not explicitly stated in the provided context or knowledge
base, state 'Tôi không thể xác minh thông tin này từ nguồn hiện có' rather than
guessing.

Rules:
- Only use information from the provided context
- Every factual claim MUST have a citation
- If context is insufficient, say so clearly
- Structure your answer with clear paragraphs"""


# =============================================================================
# DOCUMENT REORDERING (tránh lost in the middle)
# =============================================================================

def reorder_for_llm(chunks: list[dict]) -> list[dict]:
    """
    Sắp xếp chunks để tránh "lost in the middle" effect.

    LLM nhớ tốt thông tin ở ĐẦU và CUỐI prompt, quên thông tin ở GIỮA.
    Strategy: đặt chunks quan trọng nhất ở đầu và cuối, kém quan trọng ở giữa.

    Input order (by score):  [1, 2, 3, 4, 5]
    Output order:            [1, 3, 5, 4, 2]
    (best first, worst in middle, second-best last)

    Args:
        chunks: List sorted by score descending (from retrieval)

    Returns:
        List reordered để maximize LLM attention.
    """
    if len(chunks) <= 2:
        return chunks

    front = []
    back = []
    for index, chunk in enumerate(chunks):
        if index % 2 == 0:
            front.append(chunk)
        else:
            back.append(chunk)

    return front + list(reversed(back))


# =============================================================================
# CONTEXT FORMATTING
# =============================================================================

def format_context(chunks: list[dict]) -> str:
    """
    Format chunks thành context string cho prompt.
    Mỗi chunk có label source để LLM có thể cite.

    Args:
        chunks: List of {'content': str, 'metadata': dict, 'score': float}

    Returns:
        Formatted context string.
    """
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        metadata = chunk.get("metadata", {})
        source = metadata.get("source", f"Source {i}")
        doc_type = metadata.get("type", metadata.get("doc_type", "unknown"))
        score = chunk.get("score", 0.0)
        context_parts.append(
            f"[Document {i} | Source: {source} | Type: {doc_type} | "
            f"Score: {score:.3f}]\n{chunk.get('content', '')}\n"
        )
    return "\n---\n".join(context_parts)


def source_label(chunk: dict, index: int) -> str:
    """Build a compact citation label from metadata."""
    metadata = chunk.get("metadata", {})
    source = metadata.get("source", f"Source {index}")
    doc_type = metadata.get("type", "source")
    return f"{source}, {doc_type}"


def compact_snippet(text: str, max_chars: int = 360) -> str:
    """Shorten retrieved content into a readable evidence sentence."""
    text = re.sub(r"\s+", " ", text.replace("\f", " ")).strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rsplit(" ", 1)[0]
    return cut.rstrip(".,;:") + "..."


def tokenize(text: str) -> set[str]:
    """Tokenize text for simple evidence selection."""
    return set(re.findall(r"[\wÀ-ỹ]+", text.lower(), flags=re.UNICODE))


def best_evidence_snippet(query: str, text: str, max_chars: int = 360) -> str:
    """Select the most query-relevant readable segment from a retrieved chunk."""
    normalized = re.sub(r"\s+", " ", text.replace("\f", " ")).strip()
    candidates = re.split(r"(?<=[.!?;:])\s+|\n+", normalized)
    query_terms = tokenize(query)

    scored = []
    for candidate in candidates:
        candidate = candidate.strip(" -")
        if len(candidate) < 45:
            continue
        if "CÔNG BÁO" in candidate and "Điều" not in candidate:
            continue
        candidate_terms = tokenize(candidate)
        overlap = len(query_terms & candidate_terms)
        scored.append((overlap, len(candidate_terms), candidate))

    if scored:
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return compact_snippet(scored[0][2], max_chars=max_chars)

    return compact_snippet(normalized, max_chars=max_chars)


def generate_extractively(query: str, chunks: list[dict]) -> str:
    """Deterministic fallback answer with citations when no LLM is configured."""
    if not chunks:
        return "Tôi không thể xác minh thông tin này từ nguồn hiện có."

    lines = [
        "Dựa trên các nguồn đã truy xuất, thông tin liên quan nhất là:",
    ]
    for index, chunk in enumerate(chunks[:3], 1):
        snippet = best_evidence_snippet(query, chunk.get("content", ""))
        citation = source_label(chunk, index)
        lines.append(f"- {snippet} [{citation}]")

    lines.append(
        "Các ý trên chỉ sử dụng nội dung trong context truy xuất; phần ngoài context "
        "thì tôi không thể xác minh thông tin này từ nguồn hiện có."
    )
    return "\n".join(lines)


# =============================================================================
# GENERATION
# =============================================================================

def generate_answer_from_chunks(query: str, chunks: list[dict]) -> dict:
    """
    Generate an answer from already-retrieved chunks.

    This helper is used by the Supervisor - Workers pipeline so retrieval can
    happen in a dedicated worker and generation only consumes the chunk data.
    It keeps Task 10 behavior unchanged while avoiding a second retrieval pass.
    """
    reordered = reorder_for_llm(chunks)
    context = format_context(reordered)

    answer = ""
    api_key = os.getenv("OPENAI_API_KEY", "")
    if api_key and not api_key.endswith("xxx"):
        try:
            from openai import OpenAI

            client = OpenAI(api_key=api_key)
            user_message = f"Context:\n{context}\n\n---\n\nQuestion: {query}"
            response = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=TEMPERATURE,
                top_p=TOP_P,
            )
            answer = response.choices[0].message.content or ""
        except Exception as exc:
            answer = (
                "LLM API chưa sẵn sàng, chuyển sang trả lời extractive. "
                f"Lỗi: {exc}\n\n"
                + generate_extractively(query, reordered)
            )

    if not answer:
        answer = generate_extractively(query, reordered)

    return {
        "answer": answer,
        "sources": chunks,
        "retrieval_source": chunks[0].get("source", "none") if chunks else "none",
    }


def generate_with_citation(query: str, top_k: int = TOP_K) -> dict:
    """
    End-to-end RAG generation có citation.

    Pipeline:
        1. Retrieve relevant chunks
        2. Reorder để tránh lost in the middle
        3. Format context với source labels
        4. Build prompt (system + context + query)
        5. Call LLM
        6. Return answer + sources

    Args:
        query: Câu hỏi của user

    Returns:
        {
            'answer': str,           # Câu trả lời có citation
            'sources': list[dict],   # Các chunks đã dùng
            'retrieval_source': str  # 'hybrid' hoặc 'pageindex'
        }
    """
    chunks = retrieve(query, top_k=top_k)
    return generate_answer_from_chunks(query, chunks)


if __name__ == "__main__":
    test_queries = [
        "Hình phạt cho tội tàng trữ trái phép chất ma tuý theo pháp luật Việt Nam?",
        "Những nghệ sĩ nào đã bị bắt vì liên quan tới ma tuý?",
        "Quy trình cai nghiện bắt buộc theo Luật Phòng chống ma tuý 2021?",
    ]

    for q in test_queries:
        print(f"\n{'='*70}")
        print(f"Q: {q}")
        print("=" * 70)
        result = generate_with_citation(q)
        print(f"\nA: {result['answer']}")
        print(f"\n[Sources: {len(result['sources'])} chunks | via {result['retrieval_source']}]")
