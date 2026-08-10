import json
import os
import re
from datetime import datetime

from backend.config import data_path


def create_tenant_folder(email):

    tenant_id = email.replace("@", "_").replace(".", "_")

    folder = data_path("uploads", tenant_id)

    os.makedirs(folder, exist_ok=True)

    return tenant_id, folder


def save_uploaded_file(uploaded_file, folder):

    file_path = os.path.join(
        folder,
        uploaded_file.name
    )

    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    return file_path


def save_file_bytes(content, filename, folder):

    file_path = os.path.join(folder, filename)

    with open(file_path, "wb") as f:
        f.write(content)

    return file_path


def _registry_path(tenant_id):

    return data_path(
        "uploads",
        tenant_id,
        "registry.json"
    )


def generate_document_id(filename, file_path=None):

    base = os.path.splitext(filename)[0]
    slug = re.sub(r"[^\w\-]", "_", base.lower())[:50]

    if file_path and os.path.exists(file_path):
        mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
        timestamp = mtime.strftime("%Y%m%d_%H%M%S")
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    return f"{slug}_{timestamp}"


def load_upload_registry(tenant_id):

    path = _registry_path(tenant_id)

    if not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_upload_registry(tenant_id, registry):

    path = _registry_path(tenant_id)

    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=4)


def register_upload(tenant_id, filename, file_path, strategy=None, reason=None):

    registry = load_upload_registry(tenant_id)

    document_id = generate_document_id(filename)

    entry = {
        "document_id": document_id,
        "filename": filename,
        "file_path": file_path,
        "uploaded_at": datetime.now().isoformat(),
    }

    if strategy:
        entry["chunking_strategy"] = strategy

    if reason:
        entry["chunking_reason"] = reason

    registry.append(entry)

    save_upload_registry(tenant_id, registry)

    return document_id


def update_document_strategy(tenant_id, document_id, strategy, reason):

    registry = load_upload_registry(tenant_id)

    for item in registry:
        if item["document_id"] == document_id:
            item["chunking_strategy"] = strategy
            item["chunking_reason"] = reason
            break

    save_upload_registry(tenant_id, registry)


def get_document(tenant_id, document_id):

    for item in load_upload_registry(tenant_id):
        if item["document_id"] == document_id:
            return item

    return None


def list_uploads(tenant_id):

    registry = load_upload_registry(tenant_id)

    return sorted(
        registry,
        key=lambda item: item["uploaded_at"],
        reverse=True,
    )


def delete_upload(tenant_id, document_id):

    registry = load_upload_registry(tenant_id)
    remaining = []
    deleted = None

    for item in registry:
        if item["document_id"] == document_id:
            deleted = item
        else:
            remaining.append(item)

    if not deleted:
        return None

    save_upload_registry(tenant_id, remaining)

    file_path = deleted.get("file_path")

    if file_path and os.path.isfile(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass

    return deleted


def sync_registry_from_folder(tenant_id, folder):

    registry = load_upload_registry(tenant_id)
    known_filenames = {item["filename"] for item in registry}

    for name in os.listdir(folder):
        if name == "registry.json":
            continue

        file_path = os.path.join(folder, name)

        if not os.path.isfile(file_path):
            continue

        if name in known_filenames:
            continue

        document_id = generate_document_id(name, file_path)

        registry.append(
            {
                "document_id": document_id,
                "filename": name,
                "file_path": file_path,
                "uploaded_at": datetime.fromtimestamp(
                    os.path.getmtime(file_path)
                ).isoformat(),
            }
        )

    save_upload_registry(tenant_id, registry)

    return registry
