import logging
import os
import time

from utils.chunking import chunk_documents

logger = logging.getLogger(__name__)

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
    """
    Recommend a strategy, then chunk with that strategy.

    Returns both the recommended and applied strategy so callers/UI can
    distinguish a fallback from the original recommendation.
    """

    started = time.perf_counter()

    recommended, reason = _recommend_strategy(documents, file_path)
    chunks, applied, fallback_note = chunk_documents(documents, recommended)

    if applied != recommended:
        reason = (
            f"{reason} "
            f"Recommended: {recommended}. Applied: {applied}."
            + (f" {fallback_note}" if fallback_note else "")
        ).strip()
    elif fallback_note:
        reason = f"{reason} {fallback_note}".strip()

    elapsed = time.perf_counter() - started
    msg = (
        f"[timing] analyze_and_chunk: {elapsed:.3f}s "
        f"(recommended={recommended}, applied={applied}, chunks={len(chunks)})"
    )
    logger.info(msg)
    print(msg, flush=True)

    # `strategy` remains the applied strategy for honest display/storage.
    # `recommended_strategy` preserves the original recommendation.
    return {
        "strategy": applied,
        "recommended_strategy": recommended,
        "applied_strategy": applied,
        "reason": reason,
        "chunks": chunks,
        "chunk_count": len(chunks),
        "fallback": applied != recommended,
    }
