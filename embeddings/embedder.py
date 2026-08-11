"""
Local MiniLM embeddings optimized for small CPU VPS hosts.

Bottleneck context: HuggingFaceEmbeddings was fine locally (~0.3s for 4 texts)
but ~126s on a small VPS. Common causes on Oracle-style 1–2 vCPU machines:
  - PyTorch/OpenMP thread oversubscription (many threads fighting for 1–2 cores)
  - Cold first encode / tokenizer warmup paid during Chroma.from_documents
  - Reloading the model (avoided via singleton)

This module:
  - loads sentence-transformers/all-MiniLM-L6-v2 once
  - configures conservative CPU thread counts
  - calls SentenceTransformer.encode() in real batches
  - times the underlying encode() call
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from typing import List

logger = logging.getLogger(__name__)

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Benchmarked locally: for small N, batch_size ~= N is fine; for larger N,
# 8–16 was a good CPU tradeoff. 8 keeps peak memory lower on 1GB VPS hosts.
DEFAULT_BATCH_SIZE = 8

_embeddings = None
_embeddings_lock = threading.Lock()
_threads_configured = False


def _timing_log(msg: str) -> None:
    logger.info(msg)
    try:
        logging.getLogger("uvicorn.error").info(msg)
    except Exception:
        pass
    print(msg, file=sys.stderr, flush=True)


def _detect_thread_count() -> int:
    """
    Prefer env override. Otherwise use a conservative count:
    1 thread on tiny VPS (<=2 CPUs), else min(4, cpu_count).
    Oversubscription on 1 OCPU Ampere boxes can make MiniLM 10–100x slower.
    """

    override = os.getenv("EMBEDDING_THREADS", "").strip()
    if override.isdigit() and int(override) > 0:
        return int(override)

    cpus = os.cpu_count() or 1
    if cpus <= 2:
        return 1
    return min(4, cpus)


def configure_embedding_threads(force: bool = False) -> int:
    """Set PyTorch / BLAS thread env before heavy CPU work."""

    global _threads_configured

    n = _detect_thread_count()

    if _threads_configured and not force:
        return n

    # Env vars must be set before OpenMP/BLAS libs spawn worker pools.
    os.environ.setdefault("OMP_NUM_THREADS", str(n))
    os.environ.setdefault("MKL_NUM_THREADS", str(n))
    os.environ.setdefault("OPENBLAS_NUM_THREADS", str(n))
    os.environ.setdefault("NUMEXPR_NUM_THREADS", str(n))
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

    import torch

    torch.set_num_threads(n)
    try:
        # Inter-op parallelism adds overhead on tiny CPUs.
        torch.set_num_interop_threads(1)
    except RuntimeError:
        # May already be set after first parallel region.
        pass

    _threads_configured = True
    _timing_log(
        f"[timing] embedding_threads: configured={n} "
        f"cpu_count={os.cpu_count()} "
        f"torch_threads={torch.get_num_threads()}"
    )
    return n


def _batch_size() -> int:
    override = os.getenv("EMBEDDING_BATCH_SIZE", "").strip()
    if override.isdigit() and int(override) > 0:
        return int(override)
    return DEFAULT_BATCH_SIZE


class MiniLMEmbeddings:
    """
    LangChain-compatible embeddings using a singleton SentenceTransformer.

    embed_documents() always passes the full list to encode() with an explicit
    batch_size so chunks are genuinely batched (not encoded one-by-one).
    """

    def __init__(self, model_name: str = MODEL_NAME):
        configure_embedding_threads()

        from sentence_transformers import SentenceTransformer
        import torch

        started = time.perf_counter()
        _timing_log(f"[timing] SentenceTransformer: loading {model_name}...")

        self.model_name = model_name
        self.batch_size = _batch_size()
        self._model = SentenceTransformer(model_name, device="cpu")
        self._model.eval()

        # Warmup so first Chroma.from_documents does not pay cold-start cost.
        warm_started = time.perf_counter()
        with torch.inference_mode():
            self._model.encode(
                ["warmup"],
                batch_size=1,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=False,
            )
        warm_elapsed = time.perf_counter() - warm_started

        elapsed = time.perf_counter() - started
        _timing_log(
            f"[timing] SentenceTransformer: ready in {elapsed:.3f}s "
            f"(warmup_encode={warm_elapsed:.3f}s, batch_size={self.batch_size}, "
            f"device=cpu)"
        )

    def _encode(self, texts: List[str]) -> List[List[float]]:
        import torch

        if not texts:
            return []

        # Match prior HuggingFaceEmbeddings behavior.
        cleaned = [text.replace("\n", " ") for text in texts]
        bs = min(self.batch_size, max(1, len(cleaned)))

        started = time.perf_counter()
        with torch.inference_mode():
            vectors = self._model.encode(
                cleaned,
                batch_size=bs,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=False,
            )
        elapsed = time.perf_counter() - started

        _timing_log(
            f"[timing] SentenceTransformer.encode: {elapsed:.3f}s "
            f"(texts={len(cleaned)}, batch_size={bs})"
        )

        return vectors.tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        started = time.perf_counter()
        vectors = self._encode(list(texts))
        elapsed = time.perf_counter() - started
        _timing_log(
            f"[timing] embed_documents: {elapsed:.3f}s (batch={len(texts)})"
        )
        return vectors

    def embed_query(self, text: str) -> List[float]:
        started = time.perf_counter()
        vector = self._encode([text])[0]
        elapsed = time.perf_counter() - started
        _timing_log(f"[timing] embed_query: {elapsed:.3f}s")
        return vector


def get_embedding():
    """Return the process-wide MiniLM embeddings singleton."""

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
        _embeddings = MiniLMEmbeddings(MODEL_NAME)
        elapsed = time.perf_counter() - started
        _timing_log(
            f"[timing] get_embedding: {elapsed:.3f}s "
            f"(cache_hit=False, model={MODEL_NAME})"
        )
        return _embeddings
