from langchain_core.messages import HumanMessage, AIMessage
from src.task5_semantic_search import semantic_search
from src.task8_pageindex_vectorless import pageindex_search
from src.task10_generation import generate_with_citation

def legal_worker(state: RAGState):
    """Worker chuyên tìm kiếm văn bản pháp luật."""
    print("---LEGAL WORKER ĐANG TÌM KIẾM---")
    query = state["query"]
    # Giả sử hàm semantic_search có hỗ trợ filter theo metadata
    docs = semantic_search(query, top_k=3, filter={"category": "legal"})
    
    return {"retrieved_docs": docs}

def news_worker(state: RAGState):
    """Worker chuyên tìm kiếm tin tức báo chí."""
    print("---NEWS WORKER ĐANG TÌM KIẾM---")
    query = state["query"]
    docs = semantic_search(query, top_k=3, filter={"category": "news"})
    
    return {"retrieved_docs": docs}

def fallback_worker(state: RAGState):
    """Worker dùng PageIndex khi Hybrid Search thất bại."""
    print("---FALLBACK WORKER (PAGEINDEX) ĐANG CHẠY---")
    query = state["query"]
    docs = pageindex_search(query, top_k=3)
    
    return {"retrieved_docs": docs}

def generator_worker(state: RAGState):
    """Worker tổng hợp thông tin và viết câu trả lời."""
    print("---GENERATOR WORKER ĐANG VIẾT CÂU TRẢ LỜI---")
    query = state["query"]
    docs = state.get("retrieved_docs", [])
    
    # Gọi task 10 để sinh câu trả lời có citation
    answer = generate_with_citation(query, docs)
    
    return {"draft_answer": answer}

def critic_worker(state: RAGState):
    """Worker đánh giá câu trả lời (Self-Correction)."""
    print("---CRITIC WORKER ĐANG ĐÁNH GIÁ---")
    answer = state.get("draft_answer", "")
    
    # Logic đánh giá đơn giản (Trong thực tế bạn dùng DeepEval/RAGAS ở đây)
    # Ví dụ: Kiểm tra xem câu trả lời có chứa citation [1], [2] không
    if "[" in answer and "]" in answer:
        score = 1.0
        next_step = "FINISH"
    else:
        score = 0.0
        next_step = "REWRITE"
        print("Cảnh báo: Câu trả lời thiếu trích dẫn. Yêu cầu viết lại!")
        
    return {"evaluation_score": score, "next_node": next_step}