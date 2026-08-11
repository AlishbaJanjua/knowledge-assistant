import logging
import time

from langchain_huggingface import HuggingFaceEmbeddings

logger = logging.getLogger(__name__)


def get_embedding():

    started = time.perf_counter()

    embeddings = HuggingFaceEmbeddings(

        model_name="sentence-transformers/all-MiniLM-L6-v2"

    )

    elapsed = time.perf_counter() - started
    msg = f"[timing] get_embedding: {elapsed:.3f}s (model=sentence-transformers/all-MiniLM-L6-v2)"
    logger.info(msg)
    print(msg, flush=True)

    return embeddings
