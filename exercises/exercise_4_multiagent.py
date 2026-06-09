"""Bài Tập 4: Thêm Privacy Agent vào Multi-Agent System

Hoàn thành các TODO để thêm privacy agent và conditional routing.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from typing import Annotated, TypedDict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from common.llm import get_llm

CONVERSATION_MEMORY: list[str] = []


def _last_wins(left: str | None, right: str | None) -> str:
    """Reducer: giá trị mới ghi đè giá trị cũ."""
    return right if right is not None else (left or "")


def _call_llm(prompt: str, fallback: str) -> str:
    """Gọi LLM với fallback ngắn gọn để bài demo không crash khi API lỗi."""
    try:
        llm = get_llm()
        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content
    except Exception as exc:
        return f"{fallback}\n\n(Lưu ý: LLM/API đang lỗi nên dùng fallback cục bộ: {exc})"


async def _acall_llm(prompt: str, fallback: str) -> str:
    """Async version used by LangGraph nodes."""
    try:
        llm = get_llm()
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        return response.content
    except Exception as exc:
        return f"{fallback}\n\n(Lưu ý: LLM/API đang lỗi nên dùng fallback cục bộ: {exc})"


class State(TypedDict):
    question: str
    law_analysis: Annotated[str, _last_wins]
    tax_analysis: Annotated[str, _last_wins]
    compliance_analysis: Annotated[str, _last_wins]
    privacy_analysis: Annotated[str, _last_wins]
    financial_analysis: Annotated[str, _last_wins]
    final_response: Annotated[str, _last_wins]


def law_agent(state: State) -> dict:
    """Agent phân tích pháp lý tổng quát."""
    prompt = f"""Bạn là chuyên gia pháp lý. Phân tích câu hỏi sau:

{state['question']}

Tập trung vào: hợp đồng, trách nhiệm dân sự, quyền và nghĩa vụ pháp lý."""

    fallback = (
        "Phân tích pháp lý: xác định nghĩa vụ hợp đồng, hành vi vi phạm, căn cứ bồi thường, "
        "khả năng áp dụng chế tài dân sự và nghĩa vụ giảm thiểu thiệt hại."
    )
    return {"law_analysis": _call_llm(prompt, fallback)}


def check_routing(state: State) -> list[Send]:
    """Quyết định gọi agents nào dựa trên nội dung câu hỏi."""
    question_lower = state["question"].lower()
    tasks = []

    if any(kw in question_lower for kw in ["tax", "irs", "thuế"]):
        tasks.append(Send("tax_agent", state))
    
    if any(kw in question_lower for kw in ["compliance", "sec", "regulation", "regulatory", "tuân thủ"]):
        tasks.append(Send("compliance_agent", state))

    if any(kw in question_lower for kw in ["data", "privacy", "gdpr", "dữ liệu", "rò rỉ", "breach"]):
        tasks.append(Send("privacy_agent", state))

    if any(
        kw in question_lower
        for kw in ["financial", "finance", "thiệt hại", "bồi thường", "damages", "loss", "revenue"]
    ):
        tasks.append(Send("financial_agent", state))
    
    return tasks if tasks else [Send("aggregate_results", state)]


def tax_agent(state: State) -> dict:
    """Agent chuyên về thuế."""
    prompt = f"""Bạn là chuyên gia thuế. Phân tích khía cạnh thuế trong câu hỏi:

Câu hỏi: {state['question']}
Phân tích pháp lý: {state.get('law_analysis', 'N/A')}

Tập trung: IRS, tax evasion, penalties, FBAR, FATCA."""

    fallback = (
        "Phân tích thuế: xem xét truy thu thuế, tiền lãi, phạt dân sự, khả năng điều tra "
        "trốn thuế nếu có yếu tố cố ý và trách nhiệm của người quản lý liên quan."
    )
    return {"tax_analysis": _call_llm(prompt, fallback)}


def compliance_agent(state: State) -> dict:
    """Agent chuyên về compliance."""
    prompt = f"""Bạn là chuyên gia compliance. Phân tích khía cạnh tuân thủ:

Câu hỏi: {state['question']}
Phân tích pháp lý: {state.get('law_analysis', 'N/A')}

Tập trung: SEC, SOX, FCPA, AML, regulatory violations."""

    fallback = (
        "Phân tích tuân thủ: đánh giá nghĩa vụ báo cáo, kiểm soát nội bộ, điều tra của cơ quan "
        "quản lý, biện pháp khắc phục và trách nhiệm cá nhân của lãnh đạo."
    )
    return {"compliance_analysis": _call_llm(prompt, fallback)}


def privacy_agent(state: State) -> dict:
    """Agent chuyên về bảo vệ dữ liệu cá nhân và GDPR."""
    prompt = f"""Bạn là chuyên gia về GDPR và luật bảo vệ dữ liệu cá nhân.

Câu hỏi gốc: {state['question']}
Phân tích pháp lý: {state.get('law_analysis', 'N/A')}

Hãy phân tích các vấn đề về privacy và GDPR, bao gồm data breach, thông báo vi phạm,
quyền của chủ thể dữ liệu, phạt hành chính và biện pháp khắc phục."""

    fallback = (
        "Phân tích bảo vệ dữ liệu: sự cố rò rỉ dữ liệu có thể kích hoạt nghĩa vụ thông báo, "
        "điều tra của cơ quan bảo vệ dữ liệu, phạt GDPR/CCPA, yêu cầu khắc phục và bồi thường."
    )
    return {"privacy_analysis": _call_llm(prompt, fallback)}


def financial_agent(state: State) -> dict:
    """Agent nâng cao: phân tích thiệt hại và rủi ro tài chính."""
    prompt = f"""Bạn là chuyên gia phân tích thiệt hại tài chính trong tranh chấp doanh nghiệp.

Câu hỏi gốc: {state['question']}
Phân tích pháp lý: {state.get('law_analysis', 'N/A')}

Ước lượng các nhóm thiệt hại: direct damages, consequential damages, tiền phạt,
chi phí luật sư, remediation, business interruption và rủi ro danh tiếng."""

    fallback = (
        "Phân tích tài chính: cần lượng hóa thiệt hại trực tiếp, thiệt hại hệ quả, tiền phạt, "
        "phí luật sư, chi phí khắc phục, gián đoạn kinh doanh và ảnh hưởng uy tín."
    )
    return {"financial_analysis": _call_llm(prompt, fallback)}


def aggregate_results(state: State) -> dict:
    """Tổng hợp kết quả từ tất cả agents."""
    sections = []
    if state.get("law_analysis"):
        sections.append(f"📋 PHÂN TÍCH PHÁP LÝ:\n{state['law_analysis']}")
    if state.get("tax_analysis"):
        sections.append(f"💰 PHÂN TÍCH THUẾ:\n{state['tax_analysis']}")
    if state.get("compliance_analysis"):
        sections.append(f"✅ PHÂN TÍCH TUÂN THỦ:\n{state['compliance_analysis']}")
    if state.get("privacy_analysis"):
        sections.append(f"🔒 PHÂN TÍCH BẢO VỆ DỮ LIỆU:\n{state['privacy_analysis']}")
    if state.get("financial_analysis"):
        sections.append(f"📈 PHÂN TÍCH TÀI CHÍNH:\n{state['financial_analysis']}")
    if CONVERSATION_MEMORY:
        sections.append("🧠 NGỮ CẢNH TRƯỚC ĐÓ:\n" + "\n".join(CONVERSATION_MEMORY[-3:]))
    
    combined = "\n\n".join(sections)
    
    prompt = f"""Tổng hợp các phân tích sau thành một báo cáo pháp lý hoàn chỉnh:

{combined}

Câu hỏi gốc: {state['question']}

Hãy tạo một báo cáo ngắn gọn, có cấu trúc rõ ràng."""

    fallback = (
        f"Báo cáo tổng hợp:\n\n{combined}\n\n"
        "Khuyến nghị: lưu giữ chứng cứ, đánh giá nghĩa vụ thông báo, khắc phục sớm, "
        "tính toán thiệt hại và tham vấn luật sư chuyên môn."
    )
    final_response = _call_llm(prompt, fallback)
    CONVERSATION_MEMORY.append(
        f"{datetime.now(timezone.utc).isoformat()} | Q: {state['question']} | A: {final_response[:240]}"
    )
    return {"final_response": final_response}


def run_specialists(state: State) -> dict:
    """Chạy các specialist được chọn bởi check_routing."""
    handlers = {
        "tax_agent": tax_agent,
        "compliance_agent": compliance_agent,
        "privacy_agent": privacy_agent,
        "financial_agent": financial_agent,
    }
    updates: dict[str, str] = {}
    for task in check_routing(state):
        handler = handlers.get(task.node)
        if handler:
            updates.update(handler(state))
    return updates


async def law_agent_node(state: State) -> dict:
    prompt = f"""Bạn là chuyên gia pháp lý. Phân tích câu hỏi sau:

{state['question']}

Tập trung vào: hợp đồng, trách nhiệm dân sự, quyền và nghĩa vụ pháp lý."""
    fallback = (
        "Phân tích pháp lý: xác định nghĩa vụ hợp đồng, hành vi vi phạm, căn cứ bồi thường, "
        "khả năng áp dụng chế tài dân sự và nghĩa vụ giảm thiểu thiệt hại."
    )
    return {"law_analysis": await _acall_llm(prompt, fallback)}


async def run_specialists_node(state: State) -> dict:
    handlers = {
        "tax_agent": tax_agent_node,
        "compliance_agent": compliance_agent_node,
        "privacy_agent": privacy_agent_node,
        "financial_agent": financial_agent_node,
    }
    selected = [handlers[task.node] for task in check_routing(state) if task.node in handlers]
    results = await asyncio.gather(*(handler(state) for handler in selected))
    updates: dict[str, str] = {}
    for result in results:
        updates.update(result)
    return updates


async def tax_agent_node(state: State) -> dict:
    prompt = f"""Bạn là chuyên gia thuế. Phân tích khía cạnh thuế trong câu hỏi:

Câu hỏi: {state['question']}
Phân tích pháp lý: {state.get('law_analysis', 'N/A')}

Tập trung: IRS, tax evasion, penalties, FBAR, FATCA."""
    fallback = (
        "Phân tích thuế: xem xét truy thu thuế, tiền lãi, phạt dân sự, khả năng điều tra "
        "trốn thuế nếu có yếu tố cố ý và trách nhiệm của người quản lý liên quan."
    )
    return {"tax_analysis": await _acall_llm(prompt, fallback)}


async def compliance_agent_node(state: State) -> dict:
    prompt = f"""Bạn là chuyên gia compliance. Phân tích khía cạnh tuân thủ:

Câu hỏi: {state['question']}
Phân tích pháp lý: {state.get('law_analysis', 'N/A')}

Tập trung: SEC, SOX, FCPA, AML, regulatory violations."""
    fallback = (
        "Phân tích tuân thủ: đánh giá nghĩa vụ báo cáo, kiểm soát nội bộ, điều tra của cơ quan "
        "quản lý, biện pháp khắc phục và trách nhiệm cá nhân của lãnh đạo."
    )
    return {"compliance_analysis": await _acall_llm(prompt, fallback)}


async def privacy_agent_node(state: State) -> dict:
    prompt = f"""Bạn là chuyên gia về GDPR và luật bảo vệ dữ liệu cá nhân.

Câu hỏi gốc: {state['question']}
Phân tích pháp lý: {state.get('law_analysis', 'N/A')}

Hãy phân tích các vấn đề về privacy và GDPR, bao gồm data breach, thông báo vi phạm,
quyền của chủ thể dữ liệu, phạt hành chính và biện pháp khắc phục."""
    fallback = (
        "Phân tích bảo vệ dữ liệu: sự cố rò rỉ dữ liệu có thể kích hoạt nghĩa vụ thông báo, "
        "điều tra của cơ quan bảo vệ dữ liệu, phạt GDPR/CCPA, yêu cầu khắc phục và bồi thường."
    )
    return {"privacy_analysis": await _acall_llm(prompt, fallback)}


async def financial_agent_node(state: State) -> dict:
    prompt = f"""Bạn là chuyên gia phân tích thiệt hại tài chính trong tranh chấp doanh nghiệp.

Câu hỏi gốc: {state['question']}
Phân tích pháp lý: {state.get('law_analysis', 'N/A')}

Ước lượng các nhóm thiệt hại: direct damages, consequential damages, tiền phạt,
chi phí luật sư, remediation, business interruption và rủi ro danh tiếng."""
    fallback = (
        "Phân tích tài chính: cần lượng hóa thiệt hại trực tiếp, thiệt hại hệ quả, tiền phạt, "
        "phí luật sư, chi phí khắc phục, gián đoạn kinh doanh và ảnh hưởng uy tín."
    )
    return {"financial_analysis": await _acall_llm(prompt, fallback)}


async def aggregate_results_node(state: State) -> dict:
    sections = []
    if state.get("law_analysis"):
        sections.append(f"📋 PHÂN TÍCH PHÁP LÝ:\n{state['law_analysis']}")
    if state.get("tax_analysis"):
        sections.append(f"💰 PHÂN TÍCH THUẾ:\n{state['tax_analysis']}")
    if state.get("compliance_analysis"):
        sections.append(f"✅ PHÂN TÍCH TUÂN THỦ:\n{state['compliance_analysis']}")
    if state.get("privacy_analysis"):
        sections.append(f"🔒 PHÂN TÍCH BẢO VỆ DỮ LIỆU:\n{state['privacy_analysis']}")
    if state.get("financial_analysis"):
        sections.append(f"📈 PHÂN TÍCH TÀI CHÍNH:\n{state['financial_analysis']}")
    if CONVERSATION_MEMORY:
        sections.append("🧠 NGỮ CẢNH TRƯỚC ĐÓ:\n" + "\n".join(CONVERSATION_MEMORY[-3:]))

    combined = "\n\n".join(sections)
    prompt = f"""Tổng hợp các phân tích sau thành một báo cáo pháp lý hoàn chỉnh:

{combined}

Câu hỏi gốc: {state['question']}

Hãy tạo một báo cáo ngắn gọn, có cấu trúc rõ ràng."""
    fallback = (
        f"Báo cáo tổng hợp:\n\n{combined}\n\n"
        "Khuyến nghị: lưu giữ chứng cứ, đánh giá nghĩa vụ thông báo, khắc phục sớm, "
        "tính toán thiệt hại và tham vấn luật sư chuyên môn."
    )
    final_response = await _acall_llm(prompt, fallback)
    CONVERSATION_MEMORY.append(
        f"{datetime.now(timezone.utc).isoformat()} | Q: {state['question']} | A: {final_response[:240]}"
    )
    return {"final_response": final_response}


def build_graph() -> StateGraph:
    """Xây dựng multi-agent graph."""
    graph = StateGraph(State)
    
    # Add nodes
    graph.add_node("law_agent", law_agent_node)
    graph.add_node("run_specialists", run_specialists_node)
    graph.add_node("aggregate_results", aggregate_results_node)
    
    # Define edges
    graph.add_edge(START, "law_agent")
    graph.add_edge("law_agent", "run_specialists")
    graph.add_edge("run_specialists", "aggregate_results")
    graph.add_edge("aggregate_results", END)
    
    return graph.compile()


async def main():
    load_dotenv(override=True)
    
    # Test với câu hỏi có liên quan đến privacy
    question = "Nếu công ty bị rò rỉ dữ liệu khách hàng, hậu quả pháp lý và thuế là gì?"
    
    print("=" * 70)
    print("MULTI-AGENT SYSTEM với Privacy Agent")
    print("=" * 70)
    print(f"\nCâu hỏi: {question}\n")
    print("Đang xử lý qua các agents...\n")
    
    graph = build_graph()
    
    result = await graph.ainvoke({
        "question": question,
        "law_analysis": "",
        "tax_analysis": "",
        "compliance_analysis": "",
        "privacy_analysis": "",
        "financial_analysis": "",
        "final_response": "",
    })
    
    print("\n" + "=" * 70)
    print("KẾT QUẢ CUỐI CÙNG")
    print("=" * 70)
    print(result["final_response"])
    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
