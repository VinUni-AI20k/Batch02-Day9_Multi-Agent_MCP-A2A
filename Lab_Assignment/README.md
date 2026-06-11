# Lab Assignment — Improve Day08 Agent with Supervisor-Workers

Nguồn Day08 được tham chiếu từ:

`https://github.com/SeaMUSAnubis/2A202600720-Hoangtrungquan-Day08.git`

## Mục tiêu

Bản Day08 gốc là RAG chatbot gọi trực tiếp một pipeline:

`User -> Streamlit -> generate_with_citation() -> retrieve() -> LLM`

Bản cải tiến trong folder này chuyển sang pattern Supervisor-Workers:

`User -> Supervisor -> Legal Retrieval Worker + News Retrieval Worker -> Answer Synthesis Worker`

## Các agent/worker

| Agent | Vai trò |
|---|---|
| Supervisor | Phân tích intent câu hỏi và chọn worker cần chạy |
| Legal Retrieval Worker | Tìm evidence trong văn bản luật/nghị định |
| News Retrieval Worker | Tìm evidence trong tin tức/ngữ cảnh thực tế |
| Answer Synthesis Worker | Tổng hợp câu trả lời có citation từ evidence |

## Điểm cải tiến so với Day08

- Tách trách nhiệm rõ ràng thay vì một pipeline đơn tuyến.
- Legal/news retrieval có thể chạy song song.
- Có trace để demo agent nào được gọi.
- Không phụ thuộc ChromaDB hay Streamlit, chạy được với dependency sẵn có của Day09.
- Nếu có `GEMINI_API_KEY`, Answer Worker dùng Gemini; nếu không, fallback sang câu trả lời extractive để demo vẫn chạy.

## Report

Báo cáo chi tiết nằm ở [REPORT.md](REPORT.md).

## Cách chạy CLI

```bash
.venv/bin/python -m Lab_Assignment.supervisor_workers
```

## Cách chạy web demo

```bash
.venv/bin/uvicorn Lab_Assignment.app:app --host 127.0.0.1 --port 8090
```

Mở:

`http://127.0.0.1:8090`

## Dữ liệu

Corpus được copy từ Day08:

- `data/standardized/legal/*.md`
- `data/standardized/news/*.md`

Đây là dữ liệu chuẩn hoá của bài Day08 về pháp luật phòng chống ma tuý và tin tức liên quan.
