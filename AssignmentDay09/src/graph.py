from langgraph.graph import StateGraph, END
from src.agents.state import RAGState
from src.agents.workers import legal_worker, news_worker, fallback_worker, generator_worker, critic_worker
from src.agents.supervisor import supervisor_node

def build_graph():
    workflow = StateGraph(RAGState)
    
    # 1. Thêm các nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("legal_worker", legal_worker)
    workflow.add_node("news_worker", news_worker)
    workflow.add_node("fallback_worker", fallback_worker)
    workflow.add_node("generator_worker", generator_worker)
    workflow.add_node("critic_worker", critic_worker)
    
    # 2. Khai báo điểm bắt đầu
    workflow.set_entry_point("supervisor")
    
    # 3. Thêm các cạnh điều kiện từ Supervisor tới các Retriever
    workflow.add_conditional_edges(
        "supervisor",
        lambda x: x["next_node"],
        {
            "legal_worker": "legal_worker",
            "news_worker": "news_worker",
            "fallback_worker": "fallback_worker",
            "generator_worker": "generator_worker"
        }
    )
    
    # 4. Sau khi các retriever lấy xong data, trả về cho Supervisor phân tích tiếp (hoặc đẩy thẳng tới Generator)
    workflow.add_edge("legal_worker", "generator_worker")
    workflow.add_edge("news_worker", "generator_worker")
    workflow.add_edge("fallback_worker", "generator_worker")
    
    # 5. Generator chạy xong thì đưa qua Critic chấm điểm
    workflow.add_edge("generator_worker", "critic_worker")
    
    # 6. Critic kiểm tra (Self-Correction Loop)
    workflow.add_conditional_edges(
        "critic_worker",
        lambda x: x["next_node"],
        {
            "FINISH": END,                  # Đạt chuẩn -> Kết thúc
            "REWRITE": "generator_worker"   # Thiếu sót -> Bắt Generator viết lại
        }
    )
    
    return workflow.compile()