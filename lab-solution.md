# Báo Cáo Kết Quả Giải Quyết Bài Lab & Tích Hợp Day 8 Vào Day 9

Tài liệu này ghi nhận chi tiết quá trình giải quyết các bài tập trong chương trình học Day 9 (Multi-Agent với giao thức A2A phân tán), các lỗi kỹ thuật đã khắc phục trên lớp, kết quả đo lường & tối ưu hóa hiệu năng, và hướng dẫn tích hợp toàn bộ giải pháp từ Day 8 (RAG Pipeline v2) vào hệ thống Multi-Agent của Day 9.

---

## 1. Kết Quả Thực Hiện & Giải Quyết Các Bài Tập Trên Lớp (Day 9)

Hệ thống đã được chạy thực tế thành công qua toàn bộ 5 Stage từ cơ bản đến phân tán phức tạp:

### 🔹 Phần 1: Direct LLM Calling (Stage 1)
* **Bài Tập 1.1 (Thay đổi câu hỏi):**
  * Sửa đổi câu hỏi trong [stages/stage_1_direct_llm/main.py](file:///c:/Users/vando/OneDrive/Desktop/Batch02-Day9_2A202600795_NguyenVanDoan/stages/stage_1_direct_llm/main.py) thành câu hỏi tiếng Việt pháp lý thực tế: *"Hậu quả pháp lý khi một bên đơn phương chấm dứt hợp đồng lao động trái pháp luật là gì?"*.
* **Bài Tập 1.2 (Thêm temperature control):**
  * Đã cập nhật hàm `get_llm()` tại [common/llm.py](file:///c:/Users/vando/OneDrive/Desktop/Batch02-Day9_2A202600795_NguyenVanDoan/common/llm.py) cấu hình tham số `temperature=0.3` giúp kiểm soát tính ổn định và tính chính xác của câu trả lời pháp lý từ LLM.
* **Đáp án câu hỏi lý thuyết:**
  1. *Khởi tạo LLM:* LLM được khởi tạo bằng lớp `ChatOpenAI` từ thư viện `langchain_openai`. Trong hàm `get_llm()`, cấu hình `openai_api_base` hướng về OpenRouter (`https://openrouter.ai/api/v1`), truyền `openai_api_key` lấy từ file `.env` và sử dụng tên mô hình từ biến môi trường `OPENROUTER_MODEL` (mặc định cấu hình `google/gemini-2.5-flash`).
  2. *Cấu trúc tin nhắn:* Message gửi đến LLM có cấu trúc là một mảng (list) chứa các đối tượng tin nhắn của LangChain (`SystemMessage` và `HumanMessage`).
  3. *Vai trò:* `SystemMessage` dùng để định hướng hành vi, vai trò hệ thống (phong cách, luật áp dụng, disclaimer). `HumanMessage` chứa câu hỏi thực tế của người dùng. Việc tách biệt giúp LLM phân định rõ ràng đâu là chỉ dẫn vận hành và đâu là dữ liệu đầu vào.

### 🔹 Phần 2: LLM + RAG & Tools (Stage 2)
* **Bài Tập 2.1 (Thêm kiến thức mới):**
  * Đã thêm entry về luật lao động Việt Nam vào cơ sở dữ liệu tĩnh `LEGAL_KNOWLEDGE` của file bài tập [exercises/exercise_2_tools.py](file:///c:/Users/vando/OneDrive/Desktop/Batch02-Day9_2A202600795_NguyenVanDoan/exercises/exercise_2_tools.py):
    ```python
    {
        "id": "labor_law",
        "keywords": ["lao động", "sa thải", "hợp đồng lao động", "labor", "termination"],
        "text": (
            "Theo Bộ luật Lao động Việt Nam 2019, người sử dụng lao động có thể "
            "đơn phương chấm dứt hợp đồng trong các trường hợp: (1) người lao động "
            "thường xuyên không hoàn thành công việc; (2) bị ốm đau, tai nạn đã điều trị "
            "12 tháng chưa khỏi; (3) thiên tai, hỏa hoạn; (4) người lao động đủ tuổi nghỉ hưu."
        ),
    }
    ```
* **Bài Tập 2.2 (Tạo tool mới):**
  * Định nghĩa và hiện thực hóa thành công tool `@tool check_statute_of_limitations` để tính toán thời hiệu khởi kiện cho các vụ án hợp đồng (`contract`), trách nhiệm dân sự (`tort`), tài sản (`property`).
* **Đáp án câu hỏi lý thuyết:**
  1. *Decorator `@tool`:* Giúp chuyển đổi một hàm Python thông thường thành một đối tượng Tool của LangChain. Docstring của hàm được tự động phân tích để tạo thành mô tả JSON schema gửi cho LLM.
  2. *Cấu trúc `LEGAL_KNOWLEDGE`:* Là danh sách các từ điển (list of dicts) gồm các trường `id`, `keywords` (để so khớp từ khóa) và `text` (nội dung chi tiết của điều luật).
  3. *Ràng buộc Tools:* Sử dụng phương thức `.bind_tools(tools)` của đối tượng `ChatOpenAI`. Phương thức này chuyển đổi các hàm Python đã được đánh dấu `@tool` thành định nghĩa JSON schema (tên hàm, mô tả, các đối số) và đính kèm vào payload gửi đến API của OpenRouter để LLM tự quyết định gọi tool.

### 🔹 Phần 3: Single Agent với ReAct (Stage 3)
* **Bài Tập 3.1 (Thêm tool tra cứu án lệ):**
  * Định nghĩa tool `@tool search_case_law` tìm kiếm án lệ theo từ khóa (như *Hadley v. Baxendale*, *Donoghue v. Stevenson*, *Carlill v. Carbolic Smoke Ball Co*) trong file [stages/stage_3_single_agent/main.py](file:///c:/Users/vando/OneDrive/Desktop/Batch02-Day9_2A202600795_NguyenVanDoan/stages/stage_3_single_agent/main.py) và đưa vào danh sách `TOOLS`.
* **Bài Tập 3.2 (Debug agent reasoning):**
  * Để hiển thị chi tiết các bước suy nghĩ (Think) -> hành động (Act) -> quan sát (Observe) mà không gây lỗi `TypeError` của phiên bản LangGraph mới (vốn không hỗ trợ cờ `verbose=True` trực tiếp), chúng ta đã dùng phương thức `astream()` để lặp qua các cập nhật trạng thái của đồ thị và in trực tiếp ra console.
* **Đáp án câu hỏi lý thuyết (Khác biệt so với Stage 2):**
  * Ở Stage 2 (Manual Loop), chúng ta phải tự viết mã nguồn để kiểm tra xem LLM có gọi tool hay không (`if response.tool_calls`), tự gọi hàm Python tương ứng, tạo đối tượng `ToolMessage` thủ công và gửi lại toàn bộ lịch sử tin nhắn cho LLM một lần nữa.
  * Ở Stage 3, hàm `create_react_agent` của LangGraph tự động xây dựng một đồ thị trạng thái (StateGraph) thực hiện chu trình lặp ReAct tự động. Agent có khả năng tự quyết định gọi nhiều công cụ liên tiếp (multi-step reasoning) cho đến khi thu thập đủ thông tin để đưa ra câu trả lời cuối cùng mà không cần lập trình viên viết vòng lặp thủ công.

### 🔹 Phần 4: Multi-Agent In-Process (Stage 4)
* **Bài Tập 4.1 & 4.2 (Tạo và định tuyến cho Privacy Agent):**
  * Đã mở rộng file bài tập [exercises/exercise_4_multiagent.py](file:///c:/Users/vando/OneDrive/Desktop/Batch02-Day9_2A202600795_NguyenVanDoan/exercises/exercise_4_multiagent.py) và file stage mẫu [stages/stage_4_milti_agent/main.py](file:///c:/Users/vando/OneDrive/Desktop/Batch02-Day9_2A202600795_NguyenVanDoan/stages/stage_4_milti_agent/main.py).
  * Tích hợp thêm `privacy_agent` / `call_privacy_specialist` chuyên về GDPR/CCPA và bảo mật dữ liệu.
  * Sửa đổi hàm `check_routing` để tự động định tuyến đến agent bảo mật khi câu hỏi chứa các từ khóa như `data`, `privacy`, `gdpr`, `dữ liệu`.
* **Đáp án câu hỏi lý thuyết:**
  1. *`State` (Shared State):* Lưu trữ toàn bộ dữ liệu dùng chung giữa các node (như câu hỏi gốc, kết quả phân tích của từng agent, câu trả lời cuối). Các node sẽ đọc dữ liệu từ State này và trả về dữ liệu mới để cập nhật vào State.
  2. *Nodes:* Đại diện cho các bước xử lý hoặc các agent chuyên môn (`law_agent`, `tax_agent`, `compliance_agent`, `privacy_agent`). Mỗi node là một hàm nhận vào trạng thái đồ thị và trả về phần dữ liệu cập nhật.
  3. *Edges:* Định nghĩa luồng di chuyển giữa các node (ví dụ: chạy từ Start vào `law_agent`, từ `aggregate_results` đến End).
  4. *`Send()` API (Parallel Dispatch):* Cho phép đồ thị phân nhánh chạy song song nhiều agent chuyên môn cùng một lúc dựa trên các điều kiện kiểm tra (ví dụ: đồng thời gọi cả `tax_agent` và `compliance_agent` mà không cần đợi nhau kết thúc), giúp tối ưu hóa hiệu năng đáng kể.

### 🔹 Phần 5: Distributed A2A System (Stage 5)
* **Bài Tập 5.1 (Trace request flow):**
  * Khởi chạy hệ thống phân tán với Registry và 4 Agent độc lập. Quá trình trace `trace_id` trong logs cho thấy luồng đi của request được truyền qua: Client -> Customer Agent -> Law Agent -> (Tax Agent & Compliance Agent chạy song song qua HTTP) -> Law Agent tổng hợp -> Customer Agent -> Client. Tổng cộng có **3 bước nhảy (hops)** giao tiếp A2A chính.
* **Bài Tập 5.2 (Kiểm tra khả năng chịu lỗi):**
  * Khi dừng Tax Agent, hệ thống **không bị crash** và vẫn trả về kết quả cho khách hàng (chỉ bị thiếu phần thông tin thuế). Do tại hàm `call_tax` trong file [law_agent/graph.py](file:///c:/Users/vando/OneDrive/Desktop/Batch02-Day9_2A202600795_NguyenVanDoan/law_agent/graph.py), lệnh gọi dịch vụ Tax Agent được bao bọc hoàn toàn bởi khối `try-except`. Khi Tax Agent không hoạt động (lỗi kết nối/503), Law Agent sẽ bắt biệt lệ này, ghi nhận log lỗi và trả về một chuỗi thay thế: `"[Tax analysis unavailable: ...]"` giúp đồ thị vẫn tiếp tục thực thi các nhánh còn lại thay vì dừng đột ngột.
* **Bài Tập 5.3 (Thay đổi hành vi Agent):**
  * Thêm chỉ dẫn `"Keep your response extremely concise (under 100 words)."` vào prompt của `tax_agent/graph.py`. Sau khi khởi động lại dịch vụ Tax Agent và chạy test, câu trả lời của agent thuế đã trở nên ngắn gọn, súc tích và tập trung trực tiếp vào các hình phạt chính yếu.

---

## 2. Các Lỗi Kỹ Thuật Đã Khắc Phục Trên Lớp

Trong quá trình thực hành, chúng ta đã phát hiện và xử lý thành công 4 lỗi kỹ thuật hệ thống quan trọng:

1. **Lỗi xác thực OpenRouter (401 Unauthorized):**
   * *Triệu chứng:* Hệ thống báo lỗi `openai.AuthenticationError: Error code: 401 - User not found`.
   * *Nguyên nhân:* Khóa API cũ trong file `.env` đã bị thu hồi hoặc hết hạn.
   * *Khắc phục:* Cập nhật API key mới, hoạt động ổn định vào file `.env`.
2. **Lỗi mã hóa tiếng Việt trên Windows (UnicodeEncodeError):**
   * *Triệu chứng:* Chạy script hiển thị tiếng Việt bị lỗi `UnicodeEncodeError: 'charmap' codec can't encode...`.
   * *Nguyên nhân:* Terminal mặc định của Windows (PowerShell/CMD) sử dụng bảng mã CP1252 không hỗ trợ các ký tự Unicode tiếng Việt.
   * *Khắc phục:* Thực thi chạy Python bằng cách bật chế độ UTF-8 mặc định của Python thông qua biến môi trường đầu lệnh:
     ```powershell
     $env:PYTHONUTF8=1; uv run python exercises/exercise_2_tools.py
     ```
3. **Lỗi hạn mức tín dụng tài khoản (402 Payment Required):**
   * *Triệu chứng:* Gọi LLM báo lỗi `402 - This request requires more credits, or fewer max_tokens`.
   * *Nguyên nhân:* Các mô hình đắt tiền như Claude 3.5 Sonnet mặc định kiểm tra xem số dư tài khoản của người dùng có đủ chi trả cho hạn mức token tối đa được trả về (lên tới 65,535 tokens) hay không. Số dư tài khoản hiện tại của người dùng không đủ đáp ứng hạn mức kiểm tra này.
   * *Khắc phục:* Cấu hình giới hạn cứng tham số `max_tokens=1000` trong hàm khởi tạo `ChatOpenAI` tại file [common/llm.py](file:///c:/Users/vando/OneDrive/Desktop/Batch02-Day9_2A202600795_NguyenVanDoan/common/llm.py). Đồng thời chuyển đổi sang sử dụng mô hình tối ưu chi phí và tốc độ hơn là `google/gemini-2.5-flash` trong file `.env`.
4. **Lỗi cấu trúc đồ thị trong Exercise 4 (InvalidUpdateError):**
   * *Triệu chứng:* Chạy đồ thị in-process của bài tập 4 báo lỗi `langgraph.errors.InvalidUpdateError: Expected dict, got [Send(node='tax_agent', ...), ...]`.
   * *Nguyên nhân:* Skeleton code của bài tập đăng ký hàm `check_routing` (hàm trả về danh sách các tác vụ `Send`) làm một Node xử lý trạng thái. Trong LangGraph, đầu ra của Node bắt buộc phải là một Dictionary để cập nhật vào State chung, dẫn đến lỗi kiểu dữ liệu.
   * *Khắc phục:* Sửa đổi cấu trúc Graph trong [exercise_4_multiagent.py](file:///c:/Users/vando/OneDrive/Desktop/Batch02-Day9_2A202600795_NguyenVanDoan/exercises/exercise_4_multiagent.py#L131-L152): loại bỏ việc đăng ký `check_routing` làm node xử lý và chuyển nó thành hàm điều hướng điều kiện trực tiếp của node `law_agent` (`graph.add_conditional_edges("law_agent", check_routing)`).

---

## 3. Tối Ưu Hóa Hiệu Năng & Đo Lường Latency (Bài Tập Cộng Điểm)

* **Kết quả đo lường thời gian phản hồi E2E ban đầu:** **40.58 giây**
* **Kết quả sau khi tối ưu hóa:** **32.51 giây**
* **Cải thiện:** Tiết kiệm thành công **~8.07 giây (~20%)** thời gian xử lý của hệ thống.
* **Phương án tối ưu đã triển khai:**
  1. *Thay thế LLM Router bằng mã nguồn Python Heuristics:* Hàm định tuyến phân nhánh `check_routing` ban đầu thực hiện một lượt gọi LLM độc lập để xác định xem câu hỏi có thuộc nhóm Thuế hay Compliance không, mất khoảng 5-8 giây. Ta đã thay thế bằng cách viết trực tiếp một bộ lọc từ khóa bằng mã nguồn Python (Keyword Matching Heuristics) tại file [law_agent/graph.py](file:///c:/Users/vando/OneDrive/Desktop/Batch02-Day9_2A202600795_NguyenVanDoan/law_agent/graph.py) để quyết định chuyển tiếp các nhánh song song lập tức.
  2. *Khống chế token:* Cấu hình `max_tokens=1000` giúp LLM của OpenRouter phản hồi nhanh hơn, tránh sinh các phần văn bản quá dài không cần thiết.

---

## 4. Tích Hợp Kế Thừa Tài Nguyên & Kiến Thức Từ Day 8 Vào Day 9

Day 8 tập trung vào **xây dựng RAG Pipeline v2 hoàn chỉnh (Hybrid Search, Reranking, Fallback PageIndex)** và **RAG Evaluation (DeepEval)**. Day 9 tập trung vào **Multi-Agent System (Phân tán A2A)**. Dưới đây là cách thức kết hợp và nâng cấp toàn bộ hệ thống bằng cách tích hợp Day 8 vào Day 9:

```mermaid
graph TD
    User([Người dùng]) -->|1. Hỏi về ma tuý/pháp lý| CustomerAgent[Customer Agent (A2A)]
    CustomerAgent -->|2. Gọi dịch vụ phân tích| LawAgent[Law Agent (A2A)]
    
    subgraph Day 9: Distributed Multi-Agent
        LawAgent -->|Gửi câu hỏi| LawGraph[Law Agent Graph]
        LawGraph -->|Gọi parallel| TaxAgent[Tax Agent]
        LawGraph -->|Gọi parallel| ComplianceAgent[Compliance Agent]
        LawGraph -->|Gọi parallel| PrivacyAgent[Privacy Agent]
    end
    
    subgraph Day 8: Hybrid RAG Pipeline Tool
        LawGraph -.->|3. Gọi Tra Cứu Luật| RAGTool["@tool: Hybrid RAG Engine"]
        RAGTool --> Dense[Weaviate/Chroma Semantic Search]
        RAGTool --> Lexical[BM25 Lexical Search]
        Dense --> RRF[RRF Fusion]
        Lexical --> RRF
        RRF --> Rerank[Jina Reranker v2]
        Rerank --> ScoreGate{Score > Threshold?}
        ScoreGate -->|No| PageIndexFallback[PageIndex Vectorless Search]
    end
    
    subgraph Day 8: Evaluation
        DeepEvalEngine[DeepEval Engine] -.->|4. Đánh giá chất lượng| CustomerAgent
    end
```

### A. Tích hợp RAG Pipeline của Day 8 thành Công Cụ (Tools) cho các Agent Day 9
* **Hạn chế của Day 9:** Hiện tại, các agent chuyên môn trong Day 9 (như `law_agent`, `compliance_agent`, `privacy_agent`) đều phân tích dựa trên kiến thức tĩnh đã học của LLM hoặc một mock knowledge base rất nhỏ (`LEGAL_KNOWLEDGE`). Điều này dễ dẫn đến hiện tượng ảo tưởng (hallucination) khi gặp các câu hỏi luật pháp chi tiết và phức tạp của Việt Nam (ví dụ: các hành vi tàng trữ ma túy cụ thể).
* **Giải pháp tích hợp:** Tích hợp RAG Pipeline hoàn chỉnh của Day 8 làm một Tool được định nghĩa bởi `@tool` để các agent trong Day 9 gọi khi cần tra cứu tài liệu thực tế.
  * **Tool Tra Cứu Luật Ma Túy & Chất Cấm:** Agent `law_agent` hoặc `compliance_agent` sẽ gọi RAG engine của Day 8 (gồm **Hybrid Search Weaviate dense + BM25 lexical**, sau đó chạy **Jina Reranker v2**, và cuối cùng là **PageIndex Fallback** nếu score < threshold) để lấy dữ liệu từ các văn bản pháp luật gốc như *Luật Phòng, chống ma tuý 2021*, *Bộ luật Hình sự 2015*, v.v.
  * **Tool Tra Cứu Tin Tức Nghệ Sĩ:** Khi người dùng hỏi về vụ việc cụ thể của một nghệ sĩ (như Chi Dân, Andrea Aybar, Trúc Phương), agent sẽ gọi RAG engine để tìm kiếm các bài báo đã được crawl và xử lý ở Day 8 trong thư mục `news`.

```python
# Minh họa tích hợp Day 8 RAG Pipeline thành Tool trong Day 9 Agent
@tool
def retrieve_legal_rag_context(query: str) -> str:
    """Tra cứu cơ sở dữ liệu pháp luật ma túy Việt Nam bằng hệ thống Hybrid RAG từ Day 8.
    
    Args:
        query: Từ khóa hoặc câu hỏi cần tra cứu.
    """
    # Gọi trực tiếp retrieval pipeline của Day 8
    context_chunks = day_8_retrieval_pipeline.retrieve(query)
    return "\n\n".join([c["content"] for c in context_chunks])
```

### B. Sử dụng DeepEval từ Day 8 để Đánh Giá Hệ Thống Multi-Agent của Day 9
* **Hạn chế của Day 9:** Hệ thống gồm nhiều agent tương tác với nhau qua mạng (A2A) và tổng hợp kết quả cuối cùng qua Customer Agent. Rất khó để kiểm soát chất lượng câu trả lời cuối cùng có đầy đủ, chính xác và bám sát ý kiến của các agent chuyên môn hay không.
* **Giải pháp tích hợp:** Áp dụng framework **DeepEval** của Day 8 để xây dựng một bộ đánh giá tự động (Evaluation Pipeline) cho Multi-Agent:
  * **Golden Dataset:** Xây dựng một danh sách câu hỏi kiểm thử phức tạp tích hợp (ví dụ: *"Doanh nghiệp công nghệ bị rò rỉ dữ liệu người dùng và bị phạt thuế thì xử lý thế nào?"*), kèm theo `expected_output` chuẩn.
  * **Faithfulness Metric:** Đánh giá xem câu trả lời tổng hợp cuối cùng của Customer Agent có trung thực và bám sát các báo cáo chuyên môn của `law_agent`, `tax_agent`, `compliance_agent` hay không.
  * **Context Recall & Context Precision:** Đánh giá khả năng tìm kiếm thông tin của các tool RAG tích hợp bên trong các agent.

```python
# Minh họa chạy DeepEval cho Multi-Agent
test_case = LLMTestCase(
    input="Hậu quả thuế và bảo mật khi rò rỉ dữ liệu khách hàng?",
    actual_output=agent_final_response,
    expected_output=golden_expected_answer,
    retrieval_context=[
        law_agent_output, 
        tax_agent_output, 
        compliance_agent_output, 
        privacy_agent_output
    ]
)
# Đánh giá độ Faithfulness (trung thực) của báo cáo tổng hợp so với thông tin của các sub-agents
```

### C. Áp dụng kỹ thuật Sắp xếp lại Context (Document Reordering) chống "Lost in the Middle" trong Node Tổng Hợp (Aggregation Node)
* **Hạn chế của Day 9:** Khi kết hợp các kết quả phân tích từ Law, Tax, Compliance, và Privacy Agent, tổng lượng văn bản nạp vào prompt tổng hợp (`aggregate` hoặc `aggregate_results`) có thể rất lớn. LLM có xu hướng bỏ qua thông tin quan trọng nằm ở giữa ngữ cảnh (Lost in the Middle).
* **Giải pháp tích hợp:** Sử dụng hàm `reorder_for_llm` từ Task 10 của Day 8 để sắp xếp lại các kết quả phân tích của các agent trước khi đưa vào prompt tổng hợp của Customer Agent hoặc Law Agent:
  * Đưa báo cáo quan trọng nhất (ví dụ: phân tích pháp luật chính `law_analysis`) lên đầu tiên.
  * Đưa báo cáo quan trọng thứ hai (ví dụ: `privacy_analysis` hoặc `compliance_analysis`) xuống cuối cùng.
  * Đưa các phân tích phụ trợ khác ra giữa ngữ cảnh.

### D. Generation có Trích dẫn (Citation) trong Câu Trả Lời Cuối Cùng
* Khi Customer Agent trả về kết quả cho khách hàng, thay vì chỉ trả về một văn bản chung chung, nó áp dụng prompt định dạng có trích dẫn từ Task 10 của Day 8 để chỉ rõ phần lập luận nào được đưa ra bởi agent nào và dựa trên điều luật cụ thể nào (ví dụ: `[Phân tích Thuế, Điều 143 Bộ luật Hình sự]`). Điều này làm tăng độ tin cậy và tính minh bạch của hệ thống Multi-Agent đối với người dùng cuối.
