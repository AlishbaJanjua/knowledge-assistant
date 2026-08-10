import os
import shutil

from langchain_chroma import Chroma

from backend.config import data_path
from embeddings.embedder import get_embedding


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

    embeddings = get_embedding()

    db_path = _db_path(tenant_id, document_id)

    os.makedirs(db_path, exist_ok=True)

    db = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=db_path,
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
