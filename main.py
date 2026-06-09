from src.agents.graph import build_graph
from langchain_core.messages import HumanMessage

def main():
    # Khởi tạo RAG Pipeline Graph
    app = build_graph()
    
    # Chạy thử nghiệm
    user_query = "Nghệ sĩ Chi Dân bị bắt vì tội gì và theo luật thì mức phạt là bao nhiêu?"
    
    initial_state = {
        "query": user_query,
        "messages": [HumanMessage(content=user_query)],
        "retrieved_docs": [],
        "draft_answer": "",
    }
    
    print(f"Câu hỏi: {user_query}\n")
    
    # Chạy stream để xem từng bước Graph hoạt động
    for output in app.stream(initial_state):
        # In ra node vừa chạy xong
        for key, value in output.items():
            print(f"[{key}] hoàn tất.")
            
    # Lấy State cuối cùng
    final_state = app.get_state(app.config).values
    print("\n=== KẾT QUẢ CUỐI CÙNG ===")
    print(final_state.get("draft_answer"))

if __name__ == "__main__":
    main()s