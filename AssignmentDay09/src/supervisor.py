from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

class RouteDecision(BaseModel):
    next_worker: str = Field(
        description="Chọn một trong các worker: 'legal_worker', 'news_worker', 'fallback_worker', hoặc 'generator_worker' nếu đã đủ thông tin."
    )

def supervisor_node(state: RAGState):
    print("---SUPERVISOR ĐANG PHÂN TÍCH---")
    query = state["query"]
    docs = state.get("retrieved_docs", [])
    
    # Nếu đã có tài liệu, chuyển thẳng đến generator
    if len(docs) > 0:
        return {"next_node": "generator_worker"}
        
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    structured_llm = llm.with_structured_output(RouteDecision)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """Bạn là người điều phối (Supervisor). Dựa vào câu hỏi của người dùng:
        - Nếu hỏi về luật, điều khoản phạt -> chọn 'legal_worker'
        - Nếu hỏi về nghệ sĩ, showbiz, tin tức -> chọn 'news_worker'
        - Nếu câu hỏi không rõ ràng -> chọn 'fallback_worker'"""),
        ("human", "{query}")
    ])
    
    chain = prompt | structured_llm
    decision = chain.invoke({"query": query})
    
    print(f"Supervisor quyết định gọi: {decision.next_worker}")
    return {"next_node": decision.next_worker}