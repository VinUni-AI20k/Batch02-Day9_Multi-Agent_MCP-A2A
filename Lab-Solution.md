# Lab Solution Day09

## 1. Lab trên lớp

### Stage 1 — Direct LLM

Mục tiêu: hiểu cách gọi LLM trực tiếp bằng system message và human message.

Cách chạy:

```bash
uv run python stages/stage_1_direct_llm/main.py
```

Kết luận: Stage 1 phù hợp câu hỏi đơn giản, nhưng không có retrieval, tool, memory hoặc phân công agent.

### Stage 2 — RAG + Tools

Mục tiêu: bổ sung tool để LLM có thể tra cứu knowledge base và tính toán.

Cách chạy:

```bash
uv run python stages/stage_2_rag_tools/main.py
```

Kết luận: Stage 2 giúp câu trả lời có grounding hơn, nhưng orchestration vẫn thủ công và chưa có vòng lặp agent.

### Stage 3 — ReAct Agent

Mục tiêu: dùng `create_react_agent` để LLM tự quyết định tool nào cần gọi.

Cách chạy:

```bash
uv run python stages/stage_3_single_agent/main.py
```

Bài tập debug agent reasoning: dùng `debug=True` trong `create_react_agent()` để quan sát các bước agent chạy.

### Stage 4 — Multi-Agent In-Process

Mục tiêu: dùng LangGraph `StateGraph` và `Send` API để gọi nhiều agent chuyên môn song song trong cùng một process.

Cách chạy:

```bash
uv run python stages/stage_4_milti_agent/main.py
```

Kết luận: Stage 4 đã có supervisor/orchestrator logic và parallel worker branches, nhưng các agent chưa phải service độc lập.

### Stage 5 — Distributed A2A

Mục tiêu: triển khai mỗi agent thành một HTTP service độc lập và giao tiếp qua A2A protocol.

Cách chạy:

```bash
./start_all.sh
uv run python test_client.py
```

Flow:

```text
User -> Customer Agent -> Law Agent -> Tax Agent + Compliance Agent -> Law aggregate -> Customer
```

Đây là distributed multi-agent vì các agent chạy ở các port riêng:

- Registry: `10000`
- Customer Agent: `10100`
- Law Agent: `10101`
- Tax Agent: `10102`
- Compliance Agent: `10103`

## 2. Assignment — Improve Agent Day08 bằng Supervisor-Workers

Repo Day08 được tham chiếu:

`https://github.com/SeaMUSAnubis/2A202600720-Hoangtrungquan-Day08.git`

Yêu cầu checklist:

- Tạo file `Lab-Solution.md`.
- Tạo folder `Lab_Assignment`.
- Cải tiến Agent Day08 theo pattern Supervisor-Workers với ít nhất 2-3 workers.

Đã thực hiện trong:

```text
Lab_Assignment/
├── app.py
├── supervisor_workers.py
├── README.md
└── data/standardized/
```

Pattern mới:

```text
User Question
  -> Supervisor
      -> Legal Retrieval Worker
      -> News Retrieval Worker
      -> Answer Synthesis Worker
  -> Final answer with citations
```

Workers:

1. `LegalRetrievalWorker`: tìm evidence trong văn bản luật/nghị định.
2. `NewsRetrievalWorker`: tìm evidence trong tin tức liên quan.
3. `AnswerSynthesisWorker`: tổng hợp câu trả lời từ evidence; dùng Gemini nếu có API key, fallback extractive nếu chưa có.

Chạy CLI:

```bash
.venv/bin/python -m Lab_Assignment.supervisor_workers
```

Chạy giao diện demo:

```bash
.venv/bin/uvicorn Lab_Assignment.app:app --host 127.0.0.1 --port 8090
```

Mở:

```text
http://127.0.0.1:8090
```

## 3. Bonus UI demo Stage 5

Đã tạo thêm giao diện demo A2A ở:

```text
demo_ui.py
```

Chạy:

```bash
.venv/bin/uvicorn demo_ui:app --host 127.0.0.1 --port 8080
```

UI này hiển thị agent nào đang được gọi trong flow A2A:

```text
UI -> Customer -> Law -> Tax/Compliance
```

## 4. Latency và đề xuất giảm latency

Cách đo latency:

```bash
/usr/bin/time -f elapsed_seconds=%e .venv/bin/python test_client.py
```

Đề xuất giảm latency:

- Giữ parallel call Tax/Compliance bằng LangGraph `Send`.
- Giảm số lần LLM call ở Customer Agent bằng cách delegate trực tiếp sang Law Agent.
- Dùng model nhanh hơn như `gemini-2.5-flash`.
- Cache kết quả registry discovery và agent card.
- Cache retrieval/evidence cho các câu hỏi lặp lại.

Các thay đổi demo hiện tại đã áp dụng hai hướng:

- Customer Agent delegate trực tiếp sang Law Agent.
- Dùng Gemini API qua endpoint OpenAI-compatible.
