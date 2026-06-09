"""
Task 3 — Convert toàn bộ file trong data/landing/ thành Markdown.

Sử dụng MarkItDown của Microsoft:
    https://github.com/microsoft/markitdown

Cài đặt:
    pip install markitdown

Hướng dẫn:
    1. Scan toàn bộ file trong data/landing/ (PDF, DOCX, JSON)
    2. Convert sang Markdown
    3. Lưu vào data/standardized/ giữ nguyên cấu trúc thư mục
"""

import json
import shutil
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree

try:
    from markitdown import MarkItDown
except ModuleNotFoundError:
    MarkItDown = None

LANDING_DIR = Path(__file__).parent.parent / "data" / "landing"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "standardized"
LEGAL_EXTENSIONS = {".pdf", ".docx", ".doc"}


def extract_docx_text(filepath: Path) -> str:
    """Fallback DOCX text extractor using only the Python standard library."""
    with zipfile.ZipFile(filepath) as docx:
        document_xml = docx.read("word/document.xml")

    root = ElementTree.fromstring(document_xml)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []

    for paragraph in root.findall(".//w:p", namespace):
        texts = [
            node.text
            for node in paragraph.findall(".//w:t", namespace)
            if node.text
        ]
        if texts:
            paragraphs.append("".join(texts))

    return "\n\n".join(paragraphs).strip()


def extract_pdf_text(filepath: Path) -> str:
    """Fallback PDF text extractor using the local pdftotext binary."""
    if shutil.which("pdftotext") is None:
        raise RuntimeError("không tìm thấy pdftotext để convert PDF")

    completed = subprocess.run(
        ["pdftotext", "-layout", str(filepath), "-"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def convert_legal_file(filepath: Path, md_converter) -> str:
    """Convert one legal PDF/DOC/DOCX file to markdown text."""
    markitdown_error = None
    if md_converter is not None:
        try:
            result = md_converter.convert(str(filepath))
            text_content = (getattr(result, "text_content", "") or "").strip()
            if text_content:
                return text_content
        except Exception as exc:
            markitdown_error = exc

    suffix = filepath.suffix.lower()
    if suffix == ".docx":
        return extract_docx_text(filepath)
    if suffix == ".pdf":
        return extract_pdf_text(filepath)

    raise RuntimeError(
        f"Không thể convert {filepath.name}: {markitdown_error or 'unsupported file type'}"
    )


def build_news_markdown(data: dict, fallback_title: str) -> str:
    """Build markdown content from one crawled article JSON."""
    metadata = data.get("metadata", {})
    content = data.get("content", {})

    title = data.get("title") or metadata.get("title") or fallback_title
    url = data.get("url") or metadata.get("source_url") or "N/A"
    crawled_at = data.get("date_crawled") or metadata.get("crawled_at") or "N/A"
    published_time = (
        data.get("published_time") or metadata.get("published_time") or "N/A"
    )

    body = (
        data.get("content_markdown")
        or content.get("full_text")
        or "\n\n".join(content.get("paragraphs", []))
    ).strip()

    if body.startswith("#"):
        body = "\n".join(body.splitlines()[1:]).strip()

    header = (
        f"# {title}\n\n"
        f"**Source:** {url}\n"
        f"**Published:** {published_time}\n"
        f"**Crawled:** {crawled_at}\n\n"
        "---\n\n"
    )
    return header + body + "\n"


def convert_legal_docs():
    """Convert PDF/DOCX files trong data/landing/legal/ sang markdown."""
    legal_dir = LANDING_DIR / "legal"
    output_dir = OUTPUT_DIR / "legal"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not legal_dir.exists():
        print(f"  ⚠ Không tìm thấy: {legal_dir}")
        return []

    md = MarkItDown() if MarkItDown is not None else None
    converted_files = []

    for filepath in sorted(legal_dir.iterdir()):
        if filepath.suffix.lower() in LEGAL_EXTENSIONS:
            print(f"Converting: {filepath.name}")
            try:
                text_content = convert_legal_file(filepath, md)
            except Exception as exc:
                print(f"  ⚠ Skip {filepath.name}: {exc}")
                continue

            if not text_content:
                print(f"  ⚠ Skip {filepath.name}: không có nội dung text")
                continue

            output_path = output_dir / f"{filepath.stem}.md"
            output_path.write_text(text_content + "\n", encoding="utf-8")
            converted_files.append(output_path)
            print(f"  ✓ Saved: {output_path}")

    return converted_files


def convert_news_articles():
    """Convert JSON crawled articles trong data/landing/news/ sang markdown."""
    news_dir = LANDING_DIR / "news"
    output_dir = OUTPUT_DIR / "news"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not news_dir.exists():
        print(f"  ⚠ Không tìm thấy: {news_dir}")
        return []

    converted_files = []

    for filepath in sorted(news_dir.iterdir()):
        if filepath.suffix.lower() == ".json":
            print(f"Converting: {filepath.name}")
            data = json.loads(filepath.read_text(encoding="utf-8"))
            content = build_news_markdown(data, fallback_title=filepath.stem)

            output_path = output_dir / f"{filepath.stem}.md"
            output_path.write_text(content, encoding="utf-8")
            converted_files.append(output_path)
            print(f"  ✓ Saved: {output_path}")

    return converted_files


def convert_all():
    """Convert toàn bộ files."""
    print("=" * 50)
    print("Task 3: Convert to Markdown (MarkItDown)")
    print("=" * 50)

    print("\n--- Legal Documents ---")
    legal_files = convert_legal_docs()

    print("\n--- News Articles ---")
    news_files = convert_news_articles()

    print(
        f"\n✓ Done! Converted {len(legal_files)} legal files "
        f"and {len(news_files)} news files."
    )
    print("Output tại:", OUTPUT_DIR)


if __name__ == "__main__":
    convert_all()
