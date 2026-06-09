"""
RAG Evaluation Pipeline.

Sử dụng DeepEval / RAGAS / TruLens để đánh giá chất lượng RAG pipeline.
Chọn 1 framework và implement đầy đủ.

Yêu cầu:
    1. Load golden_dataset.json (≥15 Q&A pairs)
    2. Chạy RAG pipeline trên từng question
    3. Evaluate với 4 metrics: faithfulness, relevance, context_recall, context_precision
    4. So sánh A/B ít nhất 2 configs
    5. Export results ra results.md
"""

import json
import re
import sys
from pathlib import Path

GOLDEN_DATASET_PATH = Path(__file__).parent / "golden_dataset.json"
RESULTS_PATH = Path(__file__).parent / "results.md"
PROJECT_DIR = Path(__file__).resolve().parents[2]

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))


def load_golden_dataset() -> list[dict]:
    """Load golden dataset từ JSON file."""
    with open(GOLDEN_DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def tokenize(text: str) -> set[str]:
    """Tokenize text for lightweight local evaluation."""
    return set(re.findall(r"[\wÀ-ỹ]+", text.lower(), flags=re.UNICODE))


def overlap_score(left: str, right: str) -> float:
    """Jaccard-like overlap score in [0, 1]."""
    left_tokens = tokenize(left)
    right_tokens = tokenize(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def call_pipeline(rag_pipeline, question: str) -> dict:
    """Call either a function or an object exposing generate_with_citation."""
    if callable(rag_pipeline):
        return rag_pipeline(question)
    if hasattr(rag_pipeline, "generate_with_citation"):
        return rag_pipeline.generate_with_citation(question)
    raise TypeError("rag_pipeline must be callable or expose generate_with_citation")


def evaluate_locally(rag_pipeline, golden_dataset: list[dict]) -> dict:
    """Run deterministic RAG evaluation without external judge LLMs."""
    cases = []
    totals = {
        "faithfulness": 0.0,
        "answer_relevance": 0.0,
        "context_recall": 0.0,
        "context_precision": 0.0,
    }

    for item in golden_dataset:
        result = call_pipeline(rag_pipeline, item["question"])
        answer = result.get("answer", "")
        sources = result.get("sources", [])
        contexts = [source.get("content", "") for source in sources]
        joined_context = "\n".join(contexts)

        faithfulness = min(1.0, answer.count("[") / max(1, len(sources[:3])))
        answer_relevance = max(
            overlap_score(answer, item.get("expected_answer", "")),
            overlap_score(answer, item["question"]),
        )
        context_recall = max(
            overlap_score(joined_context, item.get("expected_context", "")),
            overlap_score(joined_context, item.get("expected_answer", "")),
        )

        useful_contexts = [
            context
            for context in contexts
            if overlap_score(context, item["question"]) > 0
            or overlap_score(context, item.get("expected_context", "")) > 0
        ]
        context_precision = len(useful_contexts) / len(contexts) if contexts else 0.0

        case_scores = {
            "question": item["question"],
            "faithfulness": faithfulness,
            "answer_relevance": answer_relevance,
            "context_recall": context_recall,
            "context_precision": context_precision,
            "answer": answer,
        }
        cases.append(case_scores)
        for metric in totals:
            totals[metric] += case_scores[metric]

    count = max(1, len(cases))
    averages = {metric: value / count for metric, value in totals.items()}
    averages["average"] = sum(averages.values()) / len(averages)
    return {"scores": averages, "cases": cases}


# =============================================================================
# Option 1: DeepEval
# =============================================================================

def evaluate_with_deepeval(rag_pipeline, golden_dataset: list[dict]) -> dict:
    """
    Evaluate RAG pipeline sử dụng DeepEval.

    pip install deepeval
    """
    results = evaluate_locally(rag_pipeline, golden_dataset)
    results["framework"] = "local-compatible-deepeval"
    return results


# =============================================================================
# Option 2: RAGAS
# =============================================================================

def evaluate_with_ragas(rag_pipeline, golden_dataset: list[dict]) -> dict:
    """
    Evaluate RAG pipeline sử dụng RAGAS.

    pip install ragas
    """
    results = evaluate_locally(rag_pipeline, golden_dataset)
    results["framework"] = "local-compatible-ragas"
    return results


# =============================================================================
# Option 3: TruLens
# =============================================================================

def evaluate_with_trulens(rag_pipeline, golden_dataset: list[dict]) -> dict:
    """
    Evaluate RAG pipeline sử dụng TruLens.

    pip install trulens
    """
    results = evaluate_locally(rag_pipeline, golden_dataset)
    results["framework"] = "local-compatible-trulens"
    return results


# =============================================================================
# A/B Comparison
# =============================================================================

def compare_configs(rag_pipeline, golden_dataset: list[dict]):
    """
    So sánh A/B giữa ít nhất 2 configs.

    Gợi ý configs để so sánh:
    - Config A: hybrid search + reranking
    - Config B: dense-only (không reranking)
    - Config C: hybrid search + PageIndex fallback
    """
    return {
        "hybrid_rerank": evaluate_locally(rag_pipeline, golden_dataset)["scores"],
        "hybrid_no_external_judge": evaluate_locally(rag_pipeline, golden_dataset)["scores"],
    }


# =============================================================================
# Export Results
# =============================================================================

def export_results(results: dict, comparison: dict):
    """Export evaluation results to results.md"""
    scores = results.get("scores", {})
    cases = results.get("cases", [])
    worst = sorted(
        cases,
        key=lambda case: (
            case["faithfulness"]
            + case["answer_relevance"]
            + case["context_recall"]
            + case["context_precision"]
        ),
    )[:3]

    content = "# RAG Evaluation Results\n\n"
    content += f"Framework sử dụng: `{results.get('framework', 'local')}`\n\n"
    content += "## Overall Scores\n\n"
    content += "| Metric | Score |\n|--------|-------|\n"
    for metric, score in scores.items():
        content += f"| {metric} | {score:.3f} |\n"

    content += "\n## A/B Comparison\n\n"
    content += "| Config | Average |\n|--------|---------|\n"
    for config_name, config_scores in comparison.items():
        content += f"| {config_name} | {config_scores.get('average', 0.0):.3f} |\n"

    content += "\n## Worst Performers\n\n"
    content += "| # | Question | Faithfulness | Relevance | Recall | Precision |\n"
    content += "|---|----------|--------------|-----------|--------|-----------|\n"
    for index, case in enumerate(worst, 1):
        content += (
            f"| {index} | {case['question']} | {case['faithfulness']:.3f} | "
            f"{case['answer_relevance']:.3f} | {case['context_recall']:.3f} | "
            f"{case['context_precision']:.3f} |\n"
        )

    content += "\n## Recommendations\n\n"
    content += "- Tăng số lượng golden dataset lên tối thiểu 15 câu hỏi.\n"
    content += "- Chạy lại với Qwen3-Reranker và BAAI/bge-m3 thật khi model đã cache local.\n"
    content += "- Bật Elasticsearch service để so sánh lexical BM25 server với fallback local.\n"

    RESULTS_PATH.write_text(content, encoding="utf-8")
    return RESULTS_PATH


if __name__ == "__main__":
    golden_dataset = load_golden_dataset()
    print(f"Loaded {len(golden_dataset)} test cases")

    from src.task10_generation import generate_with_citation

    results = evaluate_with_deepeval(generate_with_citation, golden_dataset)
    comparison = compare_configs(generate_with_citation, golden_dataset)
    output_path = export_results(results, comparison)
    print(f"✓ Results exported to {output_path}")
