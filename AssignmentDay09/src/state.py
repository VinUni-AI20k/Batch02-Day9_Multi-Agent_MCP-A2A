from typing import Annotated, List, TypedDict
import operator
from langchain_core.messages import BaseMessage

class RAGState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    query: str
    retrieved_docs: List[dict]  # Lưu kết quả từ các retriever workers
    draft_answer: str           # Câu trả lời tạm thời
    evaluation_score: float     # Điểm do Critic đánh giá
    next_node: str              # Biến điều hướng