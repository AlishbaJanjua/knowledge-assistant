import logging
import os
import time

from loaders.pdf_loader import load_pdf
from loaders.docx_loader import load_docx
from loaders.txt_loader import load_txt
from loaders.csv_loader import load_csv
from loaders.md_loader import load_md
from loaders.html_loader import load_html
from loaders.ppt_loader import load_ppt

logger = logging.getLogger(__name__)


def load_document(file_path):
    extension = os.path.splitext(file_path)[1].lower()
    started = time.perf_counter()

    if extension == ".pdf":
        docs = load_pdf(file_path)

    elif extension == ".docx":
        docs = load_docx(file_path)

    elif extension == ".txt":
        docs = load_txt(file_path)

    elif extension == ".csv":
        docs = load_csv(file_path)

    elif extension == ".md":
        docs = load_md(file_path)

    elif extension in [".html", ".htm"]:
        docs = load_html(file_path)

    elif extension == ".pptx":
        docs = load_ppt(file_path)

    else:
        raise ValueError(f"Unsupported file type: {extension}")

    elapsed = time.perf_counter() - started
    msg = (
        f"[timing] load_document: {elapsed:.3f}s "
        f"(file={os.path.basename(file_path)}, ext={extension}, docs={len(docs)})"
    )
    logger.info(msg)
    print(msg, flush=True)
    return docs

