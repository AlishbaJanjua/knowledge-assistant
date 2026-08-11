import logging
import sys
import threading
import time

from langchain_huggingface import HuggingFaceEmbeddings

logger = logging.getLogger(__name__)

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

_embeddings = None
_embeddings_lock = threading.Lock()


def _timing_log(msg: str) -> None:
    """Write timing lines where systemd/journalctl and uvicorn both see them."""

    logger.info(msg)
    try:
        logging.getLogger("uvicorn.error").info(msg)
    except Exception:
        pass
    print(msg, file=sys.stderr, flush=True)


def get_embedding():
    """
    Return a process-wide singleton HuggingFaceEmbeddings instance.

    Loading MiniLM on every call was re-downloading/initializing weights
    (~seconds each time) and made Chroma ingestion appear to hang.
    """

    global _embeddings

    if _embeddings is not None:
        _timing_log(
            f"[timing] get_embedding: 0.000s (cache_hit=True, model={MODEL_NAME})"
        )
        return _embeddings

    with _embeddings_lock:
        if _embeddings is not None:
            _timing_log(
                f"[timing] get_embedding: 0.000s (cache_hit=True, model={MODEL_NAME})"
            )
            return _embeddings

        started = time.perf_counter()
        _timing_log(
            f"[timing] get_embedding: loading model {MODEL_NAME} (cache_miss)..."
        )

        _embeddings = HuggingFaceEmbeddings(
            model_name=MODEL_NAME,
            # Batch encode speeds up Chroma.from_documents on CPU.
            encode_kwargs={
                "normalize_embeddings": False,
                "batch_size": 32,
            },
        )

        elapsed = time.perf_counter() - started
        _timing_log(
            f"[timing] get_embedding: {elapsed:.3f}s "
            f"(cache_hit=False, model={MODEL_NAME})"
        )
        return _embeddings
