# Báo Cáo Kết Quả & Đáp Án Câu Hỏi Codelab

Tài liệu này trả lời chi tiết toàn bộ các câu hỏi lý thuyết, câu hỏi phân tích mã nguồn và câu hỏi ôn tập có trong file [CODELAB.md](CODELAB.md).

---

## PHẦN 1: Direct LLM Calling (Stage 1)

### 1. LLM được khởi tạo như thế nào? (Tìm hàm `get_llm()`)
* **Trả lời:** LLM được khởi tạo bằng lớp `ChatOpenAI` từ thư viện `langchain_openai`. Trong hàm [get_llm()](file:///c:/Users/vando/OneDrive/Desktop/Batch02-Day9_2A202600795_NguyenVanDoan/common/llm.py#L12-L21), ta cấu hình `openai_api_base` hướng về đường dẫn của OpenRouter (`https://openrouter.ai/api/v1`), truyền `openai_api_key` và lấy tên model từ biến môi trường `OPENROUTER_MODEL`. Đồng thời gán `temperature=0.3` để câu trả lời có tính ổn định cao và `max_tokens=1000` để tối ưu chi phí và tránh lỗi hạn mức credit.

### 2. Message được gửi đến LLM có cấu trúc gì?
* **Trả lời:** Message gửi đến LLM có cấu trúc là một mảng (list) chứa các đối tượng tin nhắn của LangChain. Các đối tượng phổ biến bao gồm:
  * `SystemMessage`: Định nghĩa vai trò hệ thống.
  * `HumanMessage`: Câu hỏi từ phía người dùng.
  * `AIMessage`: Câu trả lời do mô hình sinh ra.
  * `ToolMessage`: Kết quả trả về sau khi thực thi một công cụ (tool).

### 3. Tại sao cần có `SystemMessage` và `HumanMessage`?
* **Trả lời:**
  * `SystemMessage` dùng để định hướng hành vi của AI trước khi nhận câu hỏi. Nó quy định vai trò (ví dụ: "Bạn là chuyên gia pháp lý..."), định dạng câu trả lời, giới hạn độ dài và phong thái ứng xử.
  * `HumanMessage` chứa nội dung câu hỏi thực tế của người dùng. Việc tách biệt giúp LLM phân định rõ ràng đâu là chỉ dẫn vận hành (hệ thống) và đâu là dữ liệu đầu vào cần xử lý (người dùng).

---

## PHẦN 2: LLM + RAG & Tools (Stage 2)

### 1. Hàm `@tool` decorator được dùng ở đâu?
* **Trả lời:** Decorator `@tool` (từ thư viện `langchain_core.tools`) được đặt ngay phía trước định nghĩa các hàm Python thông thường (như `search_legal_database`, `calculate_damages` hay `check_statute_of_limitations`). Docstring của các hàm này được LangChain tự động phân tích để tạo thành mô tả schema gửi cho LLM.

### 2. `LEGAL_KNOWLEDGE` được cấu trúc như thế nào?
* **Trả lời:** Được cấu trúc dưới dạng một danh sách các từ điển (list of dicts). Mỗi phần tử biểu diễn một tài liệu kiến thức pháp lý bao gồm các trường:
  * `id`: Mã định danh duy nhất của tài liệu.
  * `keywords`: Mảng chứa các từ khóa liên quan để đối chiếu tìm kiếm.
  * `text`: Nội dung chi tiết của điều luật hoặc án lệ dùng để cung cấp ngữ cảnh cho mô hình.

### 3. LLM được bind với tools ra sao? (Tìm `.bind_tools()`)
* **Trả lời:** Thông qua phương thức `.bind_tools(tools)` của đối tượng `ChatOpenAI`. Ví dụ:
  ```python
  llm_with_tools = llm.bind_tools(tools)
  ```
  Phương thức này chuyển đổi các hàm Python đã được đánh dấu `@tool` thành định nghĩa JSON schema (tên hàm, mô tả, các đối số) và đính kèm vào payload gửi đến OpenRouter API, cho phép LLM quyết định khi nào cần gọi chúng.

---

## PHẦN 3: Single Agent với ReAct (Stage 3)

### 1. Khác biệt cốt lõi của `create_react_agent()` so với Stage 2 là gì?
* **Trả lời:**
  * Ở **Stage 2 (Manual Loop)**: Chúng ta phải tự viết mã nguồn để kiểm tra xem LLM có gọi tool hay không (`if response.tool_calls`), tự gọi hàm Python tương ứng, tạo đối tượng `ToolMessage` thủ công và gửi lại toàn bộ lịch sử tin nhắn cho LLM một lần nữa. Đây là vòng lặp đơn và thủ công.
  * Ở **Stage 3 (create_react_agent)**: Hàm `create_react_agent` của LangGraph tự động xây dựng một đồ thị trạng thái (StateGraph) thực hiện chu trình lặp ReAct (Think -> Act -> Observe) tự động. Agent có khả năng tự quyết định gọi nhiều công cụ liên tiếp (multi-step reasoning) cho đến khi thu thập đủ thông tin để đưa ra câu trả lời cuối cùng mà không cần lập trình viên viết vòng lặp thủ công.

---

## PHẦN 4: Multi-Agent In-Process (Stage 4)

### 1. Ý nghĩa các thành phần trong thiết lập đồ thị (Graph Setup):
* **`class State(TypedDict)` (Shared State):** Lưu trữ toàn bộ dữ liệu dùng chung giữa các node (như câu hỏi gốc, kết quả phân tích của từng agent, câu trả lời cuối). Các node sẽ đọc dữ liệu từ State này và trả về dữ liệu mới để cập nhật vào State.
* **Nodes:** Đại diện cho các bước xử lý hoặc các agent chuyên môn (`law_agent`, `tax_agent`, `compliance_agent`, `privacy_agent`). Mỗi node là một hàm nhận vào trạng thái đồ thị và trả về phần dữ liệu cập nhật.
* **Edges:** Định nghĩa luồng di chuyển giữa các node (ví dụ: chạy từ Start vào `law_agent`, từ `aggregate_results` đến End).
* **`Send()` API (Parallel Dispatch):** Cho phép đồ thị phân nhánh chạy song song nhiều agent chuyên môn cùng một lúc dựa trên các điều kiện kiểm tra (ví dụ: đồng thời gọi cả `tax_agent` và `compliance_agent` mà không cần đợi nhau kết thúc), giúp tối ưu hóa hiệu năng đáng kể.

---

## PHẦN 5: Distributed A2A System (Stage 5)

### 1. Trace request flow (Tìm `trace_id` trong logs)
* **Luồng xử lý qua các Agent:**
  1. Client -> **Customer Agent** (Nhận câu hỏi, phát hiện cần phân tích pháp lý, gọi tool ủy quyền).
  2. Customer Agent -> **Law Agent** (Phân tích tổng quát luật dân sự/hợp đồng, định tuyến định hướng).
  3. Law Agent -> **Tax Agent** & **Compliance Agent** (Gọi song song hai agent chuyên môn qua HTTP A2A).
  4. Hai Agent phản hồi -> **Law Agent** (Tổng hợp toàn bộ phân tích).
  5. Law Agent -> **Customer Agent** -> Trả về Client.
* **Số lượng Hops:** Request đi qua **3 hops** giao tiếp Agent-to-Agent chính.

### 2. Kiểm tra khả năng chịu lỗi (Dừng Tax Agent)
* **Kết quả:** Hệ thống **không bị crash** và vẫn trả về kết quả cho khách hàng (chỉ bị thiếu phần thông tin thuế).
* **Giải thích nguyên nhân:** Tại hàm `call_tax` trong file [law_agent/graph.py](file:///c:/Users/vando/OneDrive/Desktop/Batch02-Day9_2A202600795_NguyenVanDoan/law_agent/graph.py#L135-L154), lệnh gọi dịch vụ Tax Agent được bao bọc hoàn toàn bởi khối `try-except`. Khi Tax Agent không hoạt động (lỗi kết nối/503), Law Agent sẽ bắt biệt lệ này, ghi nhận log lỗi và trả về một chuỗi thay thế: `"[Tax analysis unavailable: ...]"` giúp đồ thị vẫn tiếp tục thực thi các nhánh còn lại thay vì dừng đột ngột.

### 3. Thay đổi System Prompt của Tax Agent
* **Kết quả:** Sau khi thêm chỉ dẫn `"Keep your response extremely concise (under 100 words)."` vào prompt của `tax_agent/graph.py`, câu trả lời từ Tax Agent đã ngắn gọn, súc tích và tập trung trực tiếp vào các hình phạt chính yếu, giúp báo cáo tổng hợp cuối cùng chuyên nghiệp hơn.

---

## PHẦN 6: Câu Hỏi Ôn Tập

### 1. Khi nào nên dùng single agent thay vì multi-agent?
* **Trả lời:** Nên dùng single agent khi tác vụ cần xử lý đơn giản, nằm trong một phạm vi kiến thức hẹp hoặc một domain duy nhất (ví dụ: chỉ tra cứu văn bản, chỉ tính toán số liệu cụ thể). Single agent giúp hệ thống phản hồi nhanh hơn (ít cuộc gọi LLM tuần tự hơn), tiết kiệm chi phí sử dụng API, dễ phát triển và bảo trì hơn.

### 2. Ưu điểm của A2A protocol so với gRPC hoặc REST thông thường?
* **Trả lời:**
  * REST/gRPC thông thường chỉ truyền dữ liệu thô (JSON/Bytes) và không có cấu trúc giao tiếp chuẩn hóa dành riêng cho AI.
  * Giao thức A2A (Agent-to-Agent) chuẩn hóa cách thức đóng gói tin nhắn của AI (các trường dữ liệu Message, Parts, TextPart, BlobPart), tích hợp sẵn các cơ chế của mô hình AI như service discovery qua Agent Card, trace propagation để theo dõi luồng suy nghĩ xuyên suốt các agent độc lập, và cơ chế Depth Guard nhằm ngăn chặn vòng lặp gọi nhau vô hạn giữa các AI Agent.

### 3. Làm thế nào để prevent infinite delegation loops trong A2A?
* **Trả lời:** Sử dụng cơ chế giới hạn độ sâu ủy quyền (Depth Limit). Mỗi khi một tin nhắn được gửi đi thông qua A2A, tham số độ sâu (`delegation_depth` hoặc `depth`) sẽ tự động tăng thêm 1. Agent nhận tin nhắn sẽ kiểm tra thuộc tính này, nếu vượt quá hạn mức tối đa cho phép (ví dụ: `MAX_DELEGATION_DEPTH = 3`), agent sẽ từ chối gọi tiếp và trả về lỗi hoặc phản hồi hiện tại ngay lập tức.

### 4. Tại sao cần Registry service? Có thể hardcode URLs không?
* **Trả lời:** Registry cung cấp cơ chế khám phá dịch vụ động (Dynamic Service Discovery). Khi các Agent khởi động, chúng tự đăng ký thông tin cổng mạng và khả năng xử lý của mình với Registry. Điều này giúp hệ thống linh hoạt hơn: dễ dàng scale (mở rộng thêm agent), tự phục hồi (khi một agent đổi port/IP thì registry tự cập nhật). Nếu hardcode URLs, hệ thống sẽ trở nên cực kỳ cứng nhắc, dễ phát sinh lỗi kết nối khi thay đổi hạ tầng và rất khó để triển khai trên các môi trường cloud động.
