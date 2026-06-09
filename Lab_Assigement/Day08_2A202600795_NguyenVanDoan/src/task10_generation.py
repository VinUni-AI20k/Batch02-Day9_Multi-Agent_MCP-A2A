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
from dotenv import load_dotenv

load_dotenv()

import os
from dotenv import load_dotenv

load_dotenv()

from .task9_retrieval_pipeline import retrieve


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

SYSTEM_PROMPT = """You are a helpful and polite DrugLaw RAG Assistant. Answer the following question comprehensively in Vietnamese.

For factual questions about drug laws or artist drug incidents:
- Only use information from the provided context.
- For every statement of fact or claim, immediately insert a citation in brackets linking to the specific source (e.g., [Luật Phòng chống ma tuý 2021, Điều 3] or [VnExpress, 2024]).
- If the information is not explicitly stated in the provided context or knowledge base, state 'Tôi không thể xác minh thông tin này từ nguồn hiện có' rather than guessing.

For general greetings, system help, or polite conversation (e.g. "hello", "xin chào", "bạn là ai", "chào", etc.):
- Respond politely and naturally as a helpful drug law assistant. 
- You do NOT need to cite sources or say 'Tôi không thể xác minh thông tin này từ nguồn hiện có' for simple greetings or chit-chat."""


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
    """
    if len(chunks) <= 2:
        return chunks

    reordered = []
    # Thêm các vị trí lẻ (index chẵn: 0, 2, 4...) vào đầu danh sách
    for i in range(0, len(chunks), 2):
        reordered.append(chunks[i])

    # Thêm các vị trí chẵn (index lẻ: 1, 3...) theo thứ tự ngược lại vào cuối danh sách
    start = len(chunks) - 1
    if start % 2 == 0:
        start -= 1
        
    for i in range(start, 0, -2):
        reordered.append(chunks[i])

    return reordered


# =============================================================================
# CONTEXT FORMATTING
# =============================================================================

def format_context(chunks: list[dict]) -> str:
    """
    Format chunks thành context string cho prompt.
    Mỗi chunk có label source để LLM có thể cite.
    """
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        source = chunk.get("metadata", {}).get("source", f"Source {i}")
        doc_type = chunk.get("metadata", {}).get("type", "unknown")
        context_parts.append(
            f"[Document {i} | Source: {source} | Type: {doc_type}]\n"
            f"{chunk['content']}"
        )
    return "\n\n".join(context_parts)


# =============================================================================
# GENERATION
# =============================================================================

def generate_with_citation(query: str, top_k: int = TOP_K) -> dict:
    """
    End-to-end RAG generation có citation sử dụng OpenRouter.
    """
    # Step 1: Retrieve
    chunks = retrieve(query, top_k=top_k)

    # Step 2: Reorder
    reordered = reorder_for_llm(chunks)

    # Step 3: Format context
    context = format_context(reordered)

    # Step 4: Build prompt
    user_message = f"Context:\n{context}\n\n---\n\nQuestion: {query}"

    # Step 5: Call LLM qua OpenRouter
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or api_key == "sk-xxx":
        raise ValueError("OPENAI_API_KEY is not configured in .env")


    from openai import OpenAI
    
    # Cấu hình client kết nối tới OpenRouter
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key
    )

    # Gọi mô hình qua OpenRouter với cơ chế fallback và retry khi gặp lỗi hoặc RateLimitError (429)
    import time
    
    models_to_try = [
        "meta-llama/llama-3.2-3b-instruct:free",
        "google/gemma-4-31b-it:free",
        "nousresearch/hermes-3-llama-3.1-405b:free",
        "qwen/qwen3-coder:free"
    ]
    
    response = None
    last_error = None
    
    for model_name in models_to_try:
        max_retries = 3
        backoff = 2
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_message}
                    ],
                    temperature=TEMPERATURE,
                    top_p=TOP_P,
                    extra_headers={
                        "HTTP-Referer": "https://localhost:3000",
                        "X-Title": "DrugLaw RAG Pipeline"
                    }
                )
                break
            except Exception as e:
                last_error = e
                print(f"  ⚠ Model {model_name} failed (attempt {attempt+1}/{max_retries}): {e}")
                time.sleep(backoff)
                backoff *= 2
        if response is not None:
            break
            
    if response is None:
        raise last_error if last_error else RuntimeError("All free models failed to generate response")

    answer = response.choices[0].message.content

    # Xác định nguồn retrieval
    retrieval_source = "none"
    if chunks:
        retrieval_source = chunks[0].get("source", "hybrid")

    # Step 6: Return
    return {
        "answer": answer,
        "sources": chunks,
        "retrieval_source": retrieval_source
    }


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
        try:
            result = generate_with_citation(q)
            print(f"\nA: {result['answer']}")
            print(f"\n[Sources: {len(result['sources'])} chunks | via {result['retrieval_source']}]")
        except Exception as e:
            print(f"\n✗ Error: {e}")

