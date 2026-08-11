"""
Strategy-specific document chunking.

Each named strategy uses a distinct splitter behavior. Callers should treat the
returned ``applied_strategy`` as authoritative when it differs from the
recommended strategy (fallback).
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from typing import Iterable, List, Sequence, Tuple

import numpy as np
from langchain_core.documents import Document
from langchain_text_splitters import CharacterTextSplitter, RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)


def _get_embedding_model():
    # Lazy import so non-semantic strategies do not require embeddings at import time.
    from embeddings.embedder import get_embedding

    return get_embedding()

# ---------------------------------------------------------------------------
# Named constants (avoid magic numbers)
# ---------------------------------------------------------------------------

# Recursive — natural breakpoints, moderate overlap
RECURSIVE_CHUNK_SIZE = 1500
RECURSIVE_CHUNK_OVERLAP = 300
RECURSIVE_SEPARATORS = ["\n\n", "\n", ".", " "]

# Fixed-size — hard length cuts, no separator hierarchy
FIXED_CHUNK_SIZE = 1000
FIXED_CHUNK_OVERLAP = 0

# Sliding window — smaller windows with high overlap so neighboring chunks
# share substantial context (50% overlap vs ~20% for recursive).
SLIDING_WINDOW_SIZE = 1200
SLIDING_WINDOW_OVERLAP = 600

# Parent-child — parents stay bounded; children are retrieval units
PARENT_CHUNK_SIZE = 3000
PARENT_CHUNK_OVERLAP = 200
CHILD_CHUNK_SIZE = 800
CHILD_CHUNK_OVERLAP = 100
# Bound parent text stored on child metadata so Chroma rows stay small.
PARENT_CONTENT_METADATA_MAX = 3000

# Structure-based — keep loader units intact unless oversized
STRUCTURE_MAX_UNIT_SIZE = 2000
STRUCTURE_OVERSIZED_CHUNK_SIZE = 1500
STRUCTURE_OVERSIZED_OVERLAP = 200

# Semantic — local MiniLM breakpoint detection
SEMANTIC_MAX_CHUNK_SIZE = 1500
SEMANTIC_MIN_CHUNK_SIZE = 200
SEMANTIC_BUFFER_SIZE = 1  # sentences grouped before embedding comparison
SEMANTIC_BREAKPOINT_PERCENTILE = 90.0  # higher = fewer splits
SEMANTIC_SENTENCE_PATTERN = re.compile(
    r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])|(?<=\n)\s*"
)

STRATEGY_FIXED = "Fixed-size chunking"
STRATEGY_RECURSIVE = "Recursive chunking"
STRATEGY_SEMANTIC = "Semantic chunking"
STRATEGY_SLIDING = "Sliding window"
STRATEGY_PARENT_CHILD = "Parent-child chunking"
STRATEGY_STRUCTURE = "Structure-based chunking"

SUPPORTED_STRATEGIES = {
    STRATEGY_FIXED,
    STRATEGY_RECURSIVE,
    STRATEGY_SEMANTIC,
    STRATEGY_SLIDING,
    STRATEGY_PARENT_CHILD,
    STRATEGY_STRUCTURE,
}


def chunk_documents(
    documents: Sequence[Document],
    strategy: str = STRATEGY_RECURSIVE,
) -> Tuple[List[Document], str, str]:
    """
    Chunk documents using the requested strategy.

    Returns:
        chunks: list of Document chunks
        applied_strategy: strategy that was actually used
        fallback_note: non-empty when a fallback occurred
    """

    started = time.perf_counter()

    if not documents:
        elapsed = time.perf_counter() - started
        msg = f"[timing] chunk_documents: {elapsed:.3f}s (strategy={strategy}, chunks=0)"
        logger.info(msg)
        print(msg, flush=True)
        return [], STRATEGY_RECURSIVE, "No documents to chunk; nothing applied."

    requested = strategy if strategy in SUPPORTED_STRATEGIES else STRATEGY_RECURSIVE
    note = ""

    if strategy not in SUPPORTED_STRATEGIES:
        note = f"Unknown strategy '{strategy}'; fell back to {STRATEGY_RECURSIVE}."
        logger.warning(note)

    try:
        if requested == STRATEGY_FIXED:
            chunks = _chunk_fixed_size(documents)
        elif requested == STRATEGY_SLIDING:
            chunks = _chunk_sliding_window(documents)
        elif requested == STRATEGY_SEMANTIC:
            chunks = _chunk_semantic(documents)
        elif requested == STRATEGY_PARENT_CHILD:
            chunks = _chunk_parent_child(documents)
        elif requested == STRATEGY_STRUCTURE:
            chunks = _chunk_structure_based(documents)
        else:
            chunks = _chunk_recursive(documents)

        if not chunks:
            raise ValueError("Strategy produced zero chunks.")

        _tag_strategy(chunks, requested)
        elapsed = time.perf_counter() - started
        msg = (
            f"[timing] chunk_documents: {elapsed:.3f}s "
            f"(requested={strategy}, applied={requested}, chunks={len(chunks)})"
        )
        logger.info(msg)
        print(msg, flush=True)
        return chunks, requested, note

    except Exception as exc:
        fallback_note = (
            f"Strategy '{requested}' failed ({exc}); "
            f"fell back to {STRATEGY_RECURSIVE}."
        )
        logger.exception(fallback_note)
        chunks = _chunk_recursive(documents)
        _tag_strategy(chunks, STRATEGY_RECURSIVE)
        combined = f"{note} {fallback_note}".strip() if note else fallback_note
        elapsed = time.perf_counter() - started
        msg = (
            f"[timing] chunk_documents: {elapsed:.3f}s "
            f"(requested={strategy}, applied={STRATEGY_RECURSIVE}, "
            f"chunks={len(chunks)}, fallback=True)"
        )
        logger.info(msg)
        print(msg, flush=True)
        return chunks, STRATEGY_RECURSIVE, combined


def _copy_metadata(doc: Document, **extra) -> dict:
    metadata = dict(doc.metadata or {})
    metadata.update(extra)
    return metadata


def _tag_strategy(chunks: Iterable[Document], strategy: str) -> None:
    for chunk in chunks:
        chunk.metadata = dict(chunk.metadata or {})
        chunk.metadata["chunking_strategy"] = strategy


def _chunk_recursive(documents: Sequence[Document]) -> List[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=RECURSIVE_CHUNK_SIZE,
        chunk_overlap=RECURSIVE_CHUNK_OVERLAP,
        separators=list(RECURSIVE_SEPARATORS),
    )
    return splitter.split_documents(list(documents))


def _chunk_fixed_size(documents: Sequence[Document]) -> List[Document]:
    """
    Deterministic fixed-length splits with no recursive separator hierarchy.

    CharacterTextSplitter with separator="" cuts purely by character count.
    """

    splitter = CharacterTextSplitter(
        separator="",
        chunk_size=FIXED_CHUNK_SIZE,
        chunk_overlap=FIXED_CHUNK_OVERLAP,
        keep_separator=False,
    )
    return splitter.split_documents(list(documents))


def _chunk_sliding_window(documents: Sequence[Document]) -> List[Document]:
    """
    Overlapping windows: overlap is 50% of window size so consecutive chunks
    share substantial context. Recursive strategy uses only ~20% overlap.
    """

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=SLIDING_WINDOW_SIZE,
        chunk_overlap=SLIDING_WINDOW_OVERLAP,
        separators=list(RECURSIVE_SEPARATORS),
    )
    return splitter.split_documents(list(documents))


def _chunk_structure_based(documents: Sequence[Document]) -> List[Document]:
    """
    Treat each loader-produced Document as one structural unit (page, slide,
    CSV row, etc.). Do not merge unrelated units. Sub-split only when oversized.
    """

    oversized_splitter = RecursiveCharacterTextSplitter(
        chunk_size=STRUCTURE_OVERSIZED_CHUNK_SIZE,
        chunk_overlap=STRUCTURE_OVERSIZED_OVERLAP,
        separators=list(RECURSIVE_SEPARATORS),
    )

    results: List[Document] = []

    for index, doc in enumerate(documents):
        text = doc.page_content or ""
        unit_meta = _copy_metadata(
            doc,
            structure_unit_index=index,
        )

        if len(text) <= STRUCTURE_MAX_UNIT_SIZE:
            results.append(
                Document(page_content=text, metadata=unit_meta)
            )
            continue

        parts = oversized_splitter.create_documents(
            [text],
            metadatas=[unit_meta],
        )
        for part_index, part in enumerate(parts):
            part.metadata = _copy_metadata(
                part,
                structure_part_index=part_index,
            )
            results.append(part)

    return results


def _chunk_parent_child(documents: Sequence[Document]) -> List[Document]:
    """
    Create bounded parent windows, then child chunks for retrieval.

    Children are what get embedded/stored. Metadata links each child to its
    parent. ``parent_content`` is capped at PARENT_CONTENT_METADATA_MAX so
    metadata stays bounded while still giving RAG enough parent context.
    """

    parent_splitter = RecursiveCharacterTextSplitter(
        chunk_size=PARENT_CHUNK_SIZE,
        chunk_overlap=PARENT_CHUNK_OVERLAP,
        separators=list(RECURSIVE_SEPARATORS),
    )
    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHILD_CHUNK_SIZE,
        chunk_overlap=CHILD_CHUNK_OVERLAP,
        separators=list(RECURSIVE_SEPARATORS),
    )

    parents = parent_splitter.split_documents(list(documents))
    children: List[Document] = []

    for parent in parents:
        parent_id = str(uuid.uuid4())
        parent_text = parent.page_content or ""
        parent_content_meta = parent_text[:PARENT_CONTENT_METADATA_MAX]

        child_docs = child_splitter.create_documents(
            [parent_text],
            metadatas=[dict(parent.metadata or {})],
        )

        for child_index, child in enumerate(child_docs):
            child.metadata = _copy_metadata(
                child,
                parent_id=parent_id,
                child_index=child_index,
                # Bounded parent text for RAG expansion without a separate docstore.
                parent_content=parent_content_meta,
            )
            children.append(child)

    return children


def _split_sentences(text: str) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []

    parts = SEMANTIC_SENTENCE_PATTERN.split(text)
    sentences = [part.strip() for part in parts if part and part.strip()]
    return sentences or [text]


def _cosine_distances(embeddings: Sequence[Sequence[float]]) -> List[float]:
    if len(embeddings) < 2:
        return []

    distances: List[float] = []
    vectors = np.asarray(embeddings, dtype=float)

    for i in range(len(vectors) - 1):
        a = vectors[i]
        b = vectors[i + 1]
        denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1e-12
        similarity = float(np.dot(a, b) / denom)
        distances.append(1.0 - similarity)

    return distances


def _semantic_split_text(text: str, embeddings_model) -> List[str]:
    """
    Local semantic chunking (no paid APIs):

    a) Split text into sentence/units.
    b) Embed consecutive units (buffered groups) with MiniLM.
    c) Calculate semantic (cosine) distance between adjacent embeddings.
    d) Detect larger semantic breaks using a percentile threshold.
    e) Group units into semantic chunks, capped by SEMANTIC_MAX_CHUNK_SIZE.
    """

    sentences = _split_sentences(text)
    if not sentences:
        return []

    if len(sentences) == 1:
        return _hard_cap_chunks(sentences[0], SEMANTIC_MAX_CHUNK_SIZE)

    # Build buffered units so single short sentences are not over-split.
    units: List[str] = []
    buffer: List[str] = []
    for sentence in sentences:
        buffer.append(sentence)
        if len(buffer) >= SEMANTIC_BUFFER_SIZE:
            units.append(" ".join(buffer))
            buffer = []
    if buffer:
        units.append(" ".join(buffer))

    if len(units) == 1:
        return _hard_cap_chunks(units[0], SEMANTIC_MAX_CHUNK_SIZE)

    vectors = embeddings_model.embed_documents(units)
    distances = _cosine_distances(vectors)

    if not distances:
        return _hard_cap_chunks(" ".join(units), SEMANTIC_MAX_CHUNK_SIZE)

    threshold = float(np.percentile(distances, SEMANTIC_BREAKPOINT_PERCENTILE))

    chunks: List[str] = []
    current: List[str] = [units[0]]

    for index, distance in enumerate(distances):
        next_unit = units[index + 1]
        candidate = " ".join(current + [next_unit])
        should_break = distance >= threshold or len(candidate) > SEMANTIC_MAX_CHUNK_SIZE

        if should_break:
            chunk_text = " ".join(current).strip()
            if chunk_text:
                chunks.extend(_hard_cap_chunks(chunk_text, SEMANTIC_MAX_CHUNK_SIZE))
            current = [next_unit]
        else:
            current.append(next_unit)

    if current:
        chunk_text = " ".join(current).strip()
        if chunk_text:
            chunks.extend(_hard_cap_chunks(chunk_text, SEMANTIC_MAX_CHUNK_SIZE))

    # Merge tiny trailing fragments into the previous chunk when possible.
    merged: List[str] = []
    for chunk in chunks:
        if (
            merged
            and len(chunk) < SEMANTIC_MIN_CHUNK_SIZE
            and len(merged[-1]) + 1 + len(chunk) <= SEMANTIC_MAX_CHUNK_SIZE
        ):
            merged[-1] = f"{merged[-1]} {chunk}"
        else:
            merged.append(chunk)

    return merged or _hard_cap_chunks(text, SEMANTIC_MAX_CHUNK_SIZE)


def _hard_cap_chunks(text: str, max_size: int) -> List[str]:
    text = text or ""
    if len(text) <= max_size:
        return [text] if text else []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_size,
        chunk_overlap=min(RECURSIVE_CHUNK_OVERLAP, max_size // 5),
        separators=list(RECURSIVE_SEPARATORS),
    )
    return splitter.split_text(text)


def _chunk_semantic(documents: Sequence[Document]) -> List[Document]:
    embeddings_model = _get_embedding_model()
    results: List[Document] = []

    for doc in documents:
        parts = _semantic_split_text(doc.page_content or "", embeddings_model)
        base_meta = dict(doc.metadata or {})

        for part_index, part in enumerate(parts):
            metadata = dict(base_meta)
            metadata["semantic_part_index"] = part_index
            results.append(Document(page_content=part, metadata=metadata))

    return results
