"""Task 1 - Setup raw legal documents for later text conversion.

Task nay chi can dam bao cac file PDF/DOC/DOCX da nam trong
data/landing/legal/. Viec convert sang text/markdown duoc thuc hien o Task 3.
"""

from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "legal"
VALID_EXTENSIONS = {".pdf", ".doc", ".docx"}
MIN_REQUIRED_FILES = 3
MIN_FILE_SIZE_BYTES = 1024


def setup_directory() -> Path:
    """Create data/landing/legal/ if it does not exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def collect_document_files() -> list[Path]:
    """Return legal document files that Task 3 can convert."""
    if not DATA_DIR.exists():
        return []

    return sorted(
        path
        for path in DATA_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in VALID_EXTENSIONS
    )


def validate_document_files(files: list[Path]) -> None:
    """Validate the minimum raw documents needed for tests and conversion."""
    if len(files) < MIN_REQUIRED_FILES:
        raise RuntimeError(
            f"Can toi thieu {MIN_REQUIRED_FILES} file PDF/DOC/DOCX trong {DATA_DIR}, "
            f"hien co {len(files)}."
        )

    empty_files = [
        path.name
        for path in files
        if path.stat().st_size <= MIN_FILE_SIZE_BYTES
    ]
    if empty_files:
        raise RuntimeError(
            "Cac file sau qua nho de convert hop le: "
            + ", ".join(empty_files)
        )


def setup_legal_documents() -> list[Path]:
    """Prepare and validate PDF/DOC/DOCX inputs for markdown conversion."""
    setup_directory()
    files = collect_document_files()
    validate_document_files(files)

    print(f"Thu muc san sang: {DATA_DIR}")
    print(f"Tim thay {len(files)} file tai lieu hop le:")
    for path in files:
        size_kb = path.stat().st_size / 1024
        print(f"- {path.name} ({size_kb:.1f} KB)")

    return files


if __name__ == "__main__":
    setup_legal_documents()
