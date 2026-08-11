"""
Compare batch sizes and thread counts for MiniLM on this machine.
Run on the VPS:  python scripts/benchmark_embeddings.py
"""

from __future__ import annotations

import os
import time


def make_texts(n: int, chars: int = 800) -> list[str]:
    base = (
        "Demand is the quantity of a good consumers are willing to buy at a price. "
        "Supply describes producer behavior in competitive markets. "
    )
    unit = (base * ((chars // len(base)) + 1))[:chars]
    return [f"Chunk {i}: {unit}" for i in range(n)]


def bench_threads_and_batches():
    import torch
    from sentence_transformers import SentenceTransformer

    print(f"cpu_count={os.cpu_count()} torch={torch.__version__} cuda={torch.cuda.is_available()}")

    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")
    model.eval()
    model.encode(["warmup"], batch_size=1, show_progress_bar=False, convert_to_numpy=True)

    texts4 = make_texts(4)

    print("\n=== thread sweep on encode(4) ===")
    for threads in (1, 2, 4):
        torch.set_num_threads(threads)
        # discard first after thread change
        model.encode(texts4, batch_size=4, show_progress_bar=False, convert_to_numpy=True)
        t0 = time.perf_counter()
        model.encode(texts4, batch_size=4, show_progress_bar=False, convert_to_numpy=True)
        print(f"  threads={threads}: {time.perf_counter() - t0:.3f}s")

    torch.set_num_threads(1)
    print("\n=== batch_size sweep on encode(n) with threads=1 ===")
    for n in (1, 4, 8, 16):
        texts = make_texts(n)
        for bs in (1, 4, 8, 16, 32):
            if bs > n:
                continue
            model.encode(texts, batch_size=bs, show_progress_bar=False, convert_to_numpy=True)
            t0 = time.perf_counter()
            model.encode(texts, batch_size=bs, show_progress_bar=False, convert_to_numpy=True)
            print(f"  n={n:2d} batch_size={bs:2d}: {time.perf_counter() - t0:.3f}s")


def bench_app_embedder():
    # Import after env defaults so app configure_embedding_threads runs cleanly.
    os.environ.setdefault("EMBEDDING_THREADS", "1")
    os.environ.setdefault("EMBEDDING_BATCH_SIZE", "8")

    from embeddings.embedder import get_embedding

    emb = get_embedding()
    texts = make_texts(4)

    # Warm path already done in MiniLMEmbeddings.__init__
    t0 = time.perf_counter()
    emb.embed_documents(texts)
    first = time.perf_counter() - t0

    t0 = time.perf_counter()
    emb.embed_documents(texts)
    second = time.perf_counter() - t0

    print(f"\n=== app get_embedding().embed_documents(4) ===")
    print(f"  first={first:.3f}s second={second:.3f}s singleton_ok={get_embedding() is emb}")


if __name__ == "__main__":
    bench_threads_and_batches()
    bench_app_embedder()
