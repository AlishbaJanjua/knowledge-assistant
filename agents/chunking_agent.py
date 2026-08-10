import os

from utils.chunking import chunk_documents

STRATEGIES = [
    "Fixed-size chunking",
    "Recursive chunking",
    "Semantic chunking",
    "Sliding window",
    "Parent-child chunking",
    "Structure-based chunking",
]

STRUCTURED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".pptx",
    ".md",
    ".html",
    ".htm",
}


def _recommend_strategy(documents, file_path):

    total_length = sum(len(doc.page_content) for doc in documents)
    extension = os.path.splitext(file_path or "")[1].lower()
    section_count = len(documents)

    if extension == ".csv":
        return (
            "Fixed-size chunking",
            "Tabular CSV data splits cleanly into uniform fixed-size chunks.",
        )

    if extension in STRUCTURED_EXTENSIONS and section_count >= 4:
        return (
            "Structure-based chunking",
            f"The document has {section_count} structural sections — "
            "splitting by headings, slides, or pages preserves context best.",
        )

    if extension == ".pptx":
        return (
            "Structure-based chunking",
            "Slide-based documents benefit from structure-aware chunking per slide.",
        )

    if total_length < 5_000:
        return (
            "Fixed-size chunking",
            "This is a short document where uniform fixed-size chunks work well.",
        )

    if total_length < 15_000:
        return (
            "Recursive chunking",
            "A small-to-medium document suits recursive splitting on natural breakpoints.",
        )

    if total_length < 50_000:
        return (
            "Semantic chunking",
            "Medium-length content benefits from grouping text by topic and meaning.",
        )

    if total_length < 120_000:
        return (
            "Sliding window",
            "A longer document needs overlapping windows to keep context across chunks.",
        )

    return (
        "Parent-child chunking",
        "A very large document works best with parent-child chunks for broad "
        "and fine-grained retrieval.",
    )


def analyze_and_chunk(documents, file_path=None):

    strategy, reason = _recommend_strategy(documents, file_path)
    chunks = chunk_documents(documents)

    return {
        "strategy": strategy,
        "reason": reason,
        "chunks": chunks,
        "chunk_count": len(chunks),
    }
