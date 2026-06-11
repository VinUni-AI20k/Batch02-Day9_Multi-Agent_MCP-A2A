# Report — Improve Day08 Agent With Supervisor-Workers

## 1. Thông tin bài làm

- Bài gốc Day08: `https://github.com/SeaMUSAnubis/2A202600720-Hoangtrungquan-Day08.git`
- Bài cải tiến Day09: folder `Lab_Assignment/`
- Pattern yêu cầu: Supervisor - Workers
- Số worker triển khai: 3 workers

## 2. Vấn đề của Day08 gốc

Day08 gốc là một RAG chatbot cho chủ đề pháp luật phòng chống ma tuý. Flow chính:

```text
User -> Streamlit UI -> generate_with_citation() -> retrieval pipeline -> LLM answer
```

Pipeline này chạy tốt cho RAG đơn tuyến, nhưng có một số hạn chế:

- Một pipeline xử lý nhiều loại câu hỏi, khó tách trách nhiệm.
- Legal evidence và news evidence chưa được biểu diễn như các worker độc lập.
- Khó demo rõ agent nào đang xử lý bước nào.
- Khi mở rộng thêm domain, pipeline đơn tuyến dễ phình to.

## 3. Kiến trúc cải tiến

Phiên bản trong `Lab_Assignment/` chuyển sang Supervisor-Workers:

```text
User Question
  -> Supervisor
      -> Legal Retrieval Worker
      -> News Retrieval Worker
      -> Answer Synthesis Worker
  -> Final Answer
```

Supervisor đọc intent câu hỏi và chọn worker phù hợp:

- Nếu câu hỏi liên quan luật, điều khoản, hình phạt, cai nghiện, ma tuý: gọi `LegalRetrievalWorker`.
- Nếu câu hỏi liên quan tin tức, nghệ sĩ, vụ việc, thực tế, năm, bị bắt: gọi `NewsRetrievalWorker`.
- Luôn gọi `AnswerSynthesisWorker` sau các retrieval worker để tổng hợp câu trả lời.

## 4. Các worker đã triển khai

| Worker | File | Vai trò |
|---|---|---|
| Supervisor | `supervisor_workers.py` | Chọn worker dựa trên intent của câu hỏi |
| Legal Retrieval Worker | `supervisor_workers.py` | Tìm evidence trong văn bản luật/nghị định |
| News Retrieval Worker | `supervisor_workers.py` | Tìm evidence trong tin tức liên quan |
| Answer Synthesis Worker | `supervisor_workers.py` | Tổng hợp câu trả lời có citation |

## 5. Dữ liệu sử dụng

Corpus được copy từ Day08:

```text
Lab_Assignment/data/standardized/legal/
Lab_Assignment/data/standardized/news/
```

Các file chính:

- `bo-luat-hinh-su-2015-ma-tuy.md`
- `luat-phong-chong-ma-tuy-2021.md`
- `nghi-dinh-105-2021.md`
- `nghi-dinh-28-2026-nd-cp-danh-muc-chat-ma-tuy-va-tien-chat.md`
- `article_01.md` đến `article_05.md`

## 6. Cách hoạt động

### 6.1. Index

`CorpusIndex` load Markdown, chia chunk theo đoạn, rồi tạo lexical score nhẹ bằng TF-IDF nội bộ. Cách này giúp assignment chạy được trong môi trường Day09 mà không cần cài thêm ChromaDB, rank-bm25 hoặc Streamlit.

### 6.2. Routing

`Supervisor.decide()` dùng keyword intent để chọn Legal Worker, News Worker hoặc cả hai.

### 6.3. Parallel workers

Các retrieval workers được chạy bằng `ThreadPoolExecutor`, nên khi Supervisor chọn cả Legal và News thì hai worker có thể chạy song song.

### 6.4. Synthesis

`AnswerSynthesisWorker` gom evidence từ worker results:

- Nếu có `GEMINI_API_KEY`, dùng Gemini qua OpenAI-compatible endpoint để tổng hợp.
- Nếu chưa có API key, fallback sang câu trả lời extractive để vẫn demo được.

## 7. Cách chạy

### CLI

```bash
.venv/bin/python -m Lab_Assignment.supervisor_workers
```

### Web demo

```bash
.venv/bin/uvicorn Lab_Assignment.app:app --host 127.0.0.1 --port 8090
```

Mở trình duyệt:

```text
http://127.0.0.1:8090
```

## 8. Kết quả kiểm thử

Đã kiểm tra cú pháp:

```bash
.venv/bin/python -m py_compile Lab_Assignment/supervisor_workers.py Lab_Assignment/app.py
```

Đã chạy CLI thành công:

```bash
.venv/bin/python -m Lab_Assignment.supervisor_workers
```

Kết quả trace mẫu:

```text
supervisor: completed
legal_retrieval_worker: ok
news_retrieval_worker: ok
answer_synthesis_worker: completed
```

Đã test API web demo:

```bash
curl -X POST http://127.0.0.1:8090/api/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"Hình phạt tàng trữ ma túy là gì?"}'
```

API trả về:

- `decision.selected_workers`
- `worker_results`
- `answer`
- `trace`
- `sources`

## 9. Mapping với checklist

| Yêu cầu | Trạng thái |
|---|---|
| Tạo `Lab-Solution.md` giải quyết lab trên lớp | Hoàn thành |
| Tạo folder `Lab_Assignment` | Hoàn thành |
| Đặt toàn bộ code assignment trong `Lab_Assignment` | Hoàn thành |
| Improve Agent Day08 theo Supervisor-Workers | Hoàn thành |
| Ít nhất 2-3 workers | Hoàn thành: 3 workers |
| Có thể demo | Hoàn thành: CLI và web UI |

## 10. Kết luận

Bài làm đã chuyển Day08 RAG chatbot từ pipeline đơn tuyến sang kiến trúc Supervisor-Workers rõ trách nhiệm, có routing, có nhiều worker, có tổng hợp câu trả lời và có trace để demo quá trình các worker được gọi.
