import logging
import os
import shutil
import sys
import time

from langchain_chroma import Chroma

from backend.config import data_path
from embeddings.embedder import get_embedding

logger = logging.getLogger(__name__)


def _timing_log(msg: str) -> None:
    """Write timing lines where systemd/journalctl and uvicorn both see them."""

    logger.info(msg)
    try:
        logging.getLogger("uvicorn.error").info(msg)
    except Exception:
        pass
    print(msg, file=sys.stderr, flush=True)


class _TimedEmbeddings:
    """
    Thin wrapper that times embed_documents / embed_query without changing
    the underlying MiniLM model behavior.
    """

    def __init__(self, embeddings):
        self._embeddings = embeddings
        self.embed_documents_calls = 0
        self.embed_documents_seconds = 0.0
        self.embed_documents_texts = 0
        self.embed_query_calls = 0
        self.embed_query_seconds = 0.0

    def embed_documents(self, texts):
        started = time.perf_counter()
        vectors = self._embeddings.embed_documents(texts)
        elapsed = time.perf_counter() - started

        self.embed_documents_calls += 1
        self.embed_documents_seconds += elapsed
        self.embed_documents_texts += len(texts)

        _timing_log(
            f"[timing] embed_documents: {elapsed:.3f}s "
            f"(batch={len(texts)}, call={self.embed_documents_calls})"
        )
        return vectors

    def embed_query(self, text):
        started = time.perf_counter()
        vector = self._embeddings.embed_query(text)
        elapsed = time.perf_counter() - started

        self.embed_query_calls += 1
        self.embed_query_seconds += elapsed

        _timing_log(
            f"[timing] embed_query: {elapsed:.3f}s "
            f"(call={self.embed_query_calls})"
        )
        return vector

    def __getattr__(self, name):
        return getattr(self._embeddings, name)


def _db_path(tenant_id, document_id):

    return data_path(
        "chroma_db",
        tenant_id,
        document_id,
    )


def _legacy_db_path(tenant_id):

    return data_path(
        "chroma_db",
        tenant_id,
    )


def create_vectorstore(chunks, tenant_id, document_id):

    started = time.perf_counter()
    chunk_count = len(chunks) if chunks is not None else 0
    total_chars = sum(len(c.page_content or "") for c in (chunks or []))

    _timing_log(
        f"[timing] create_vectorstore: start "
        f"(document_id={document_id}, chunks={chunk_count}, chars={total_chars})"
    )

    embeddings = get_embedding()
    timed_embeddings = _TimedEmbeddings(embeddings)

    db_path = _db_path(tenant_id, document_id)

    # If this document already has a persisted store, reuse it.
    # Re-running from_documents on the same path would append duplicates.
    if os.path.isdir(db_path) and os.listdir(db_path):
        db = Chroma(
            persist_directory=db_path,
            embedding_function=embeddings,
        )
        elapsed = time.perf_counter() - started
        _timing_log(
            f"[timing] create_vectorstore: {elapsed:.3f}s "
            f"(reused existing store, document_id={document_id}, "
            f"input_chunks={chunk_count})"
        )
        return db

    os.makedirs(db_path, exist_ok=True)

    _timing_log(
        f"[timing] Chroma.from_documents: BEFORE "
        f"(chunks={chunk_count}, chars={total_chars}, path={db_path})"
    )
    from_docs_started = time.perf_counter()

    db = Chroma.from_documents(
        documents=chunks,
        embedding=timed_embeddings,
        persist_directory=db_path,
    )

    from_docs_elapsed = time.perf_counter() - from_docs_started
    _timing_log(
        f"[timing] Chroma.from_documents: AFTER {from_docs_elapsed:.3f}s "
        f"(chunks={chunk_count}, "
        f"embed_documents_calls={timed_embeddings.embed_documents_calls}, "
        f"embed_documents_total={timed_embeddings.embed_documents_seconds:.3f}s, "
        f"texts_embedded={timed_embeddings.embed_documents_texts})"
    )

    elapsed = time.perf_counter() - started
    _timing_log(
        f"[timing] create_vectorstore: {elapsed:.3f}s "
        f"(from_documents={from_docs_elapsed:.3f}s, chunks={chunk_count}, "
        f"document_id={document_id})"
    )

    return db


def load_vectorstore(tenant_id, document_id):

    embeddings = get_embedding()

    db_path = _db_path(tenant_id, document_id)

    if os.path.exists(db_path):
        return Chroma(
            persist_directory=db_path,
            embedding_function=embeddings,
        )

    legacy_path = _legacy_db_path(tenant_id)

    if os.path.exists(legacy_path):
        return Chroma(
            persist_directory=legacy_path,
            embedding_function=embeddings,
        )

    return None


def delete_vectorstore(tenant_id, document_id):

    db_path = _db_path(tenant_id, document_id)

    if os.path.isdir(db_path):
        shutil.rmtree(db_path, ignore_errors=True)
        return True

    return False
