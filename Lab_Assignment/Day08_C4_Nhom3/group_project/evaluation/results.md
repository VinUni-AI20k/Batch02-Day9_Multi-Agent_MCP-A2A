# RAG Evaluation Results

Framework sử dụng: `local-compatible-deepeval`

## Overall Scores

| Metric | Score |
|--------|-------|
| faithfulness | 1.000 |
| answer_relevance | 0.074 |
| context_recall | 0.052 |
| context_precision | 1.000 |
| average | 0.532 |

## A/B Comparison

| Config | Average |
|--------|---------|
| hybrid_rerank | 0.532 |
| hybrid_no_external_judge | 0.532 |

## Worst Performers

| # | Question | Faithfulness | Relevance | Recall | Precision |
|---|----------|--------------|-----------|--------|-----------|
| 1 | Luật Phòng chống ma tuý 2021 quy định những hình thức cai nghiện nào? | 1.000 | 0.054 | 0.052 | 1.000 |
| 2 | Danh mục các chất ma tuý thuộc nhóm I theo quy định pháp luật Việt Nam gồm những chất nào? | 1.000 | 0.077 | 0.053 | 1.000 |
| 3 | Hình phạt cho tội tàng trữ trái phép chất ma tuý theo Điều 249 Bộ luật Hình sự? | 1.000 | 0.090 | 0.053 | 1.000 |

## Recommendations

- Tăng số lượng golden dataset lên tối thiểu 15 câu hỏi.
- Chạy lại với Qwen3-Reranker và BAAI/bge-m3 thật khi model đã cache local.
- Bật Elasticsearch service để so sánh lexical BM25 server với fallback local.
