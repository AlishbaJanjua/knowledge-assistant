"""LangGraph short-term (checkpointer) and long-term (Store) memory.

Persistent across process restarts via SQLite:
- short-term: SqliteSaver (checkpoints.sqlite)
- long-term: SqliteStore (store.sqlite)

Tenant/document isolation uses stable thread_ids and Store namespaces.
"""

import os
import sqlite3
from typing import Optional

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.store.sqlite import SqliteStore

from backend.config import data_path
from backend.llm import llm

# Long-term Store key within each tenant/document namespace.
LONG_TERM_NOTES_KEY = "notes"

_MEMORY_DIR = data_path("langgraph_memory")
os.makedirs(_MEMORY_DIR, exist_ok=True)

# Long-lived connections for the FastAPI process lifetime.
# check_same_thread=False is required; SqliteSaver/SqliteStore use their own locks.
# SqliteStore requires isolation_level=None (autocommit) so explicit BEGIN works.
_checkpoint_conn = sqlite3.connect(
    os.path.join(_MEMORY_DIR, "checkpoints.sqlite"),
    check_same_thread=False,
)
_store_conn = sqlite3.connect(
    os.path.join(_MEMORY_DIR, "store.sqlite"),
    check_same_thread=False,
    isolation_level=None,
)

checkpointer = SqliteSaver(_checkpoint_conn)
checkpointer.setup()

store = SqliteStore(_store_conn)
store.setup()


def tenant_id_from_email(email: str) -> str:
    """Match utils.helpers.create_tenant_folder tenant id derivation."""

    return email.replace("@", "_").replace(".", "_")


def thread_id(email: str, document_id: str) -> str:
    """Stable short-term memory thread for one user + document conversation."""

    return f"{tenant_id_from_email(email)}:{document_id}"


def invoke_config(email: str, document_id: str) -> dict:
    """RunnableConfig fragment required by LangGraph when a checkpointer is set."""

    return {
        "configurable": {
            "thread_id": thread_id(email, document_id),
        }
    }


def memory_namespace(email: str, document_id: str) -> tuple:
    """Long-term Store namespace: isolated per tenant and document."""

    return (
        "memories",
        tenant_id_from_email(email),
        document_id or "_none",
    )


def _format_history(history) -> str:

    if not history:
        return "No conversation yet."

    lines = []

    for index, chat in enumerate(history, start=1):
        lines.append(f"Turn {index}")
        lines.append(f"User: {chat['user']}")
        lines.append(f"Assistant: {chat['assistant']}")
        lines.append("")

    return "\n".join(lines)


def read_long_term_notes(email: str, document_id: str, runtime_store=None) -> str:
    """Read long-term notes for a tenant/document from the LangGraph Store."""

    active_store = runtime_store if runtime_store is not None else store
    item = active_store.get(memory_namespace(email, document_id), LONG_TERM_NOTES_KEY)

    if not item:
        return ""

    items = item.value.get("items") or []

    if not items:
        return ""

    lines = []

    for index, note in enumerate(items, start=1):
        lines.append(f"Note {index}")
        lines.append(f"User: {note.get('user', '')}")
        lines.append(f"Assistant: {note.get('assistant', '')}")
        lines.append("")

    return "\n".join(lines)


def update_long_term_memory(
    email: str,
    document_id: str,
    user: str,
    assistant: str,
    runtime_store=None,
) -> None:
    """Append a condensed turn into long-term Store notes (capped)."""

    if not document_id:
        return

    active_store = runtime_store if runtime_store is not None else store
    ns = memory_namespace(email, document_id)
    existing = active_store.get(ns, LONG_TERM_NOTES_KEY)
    items = list((existing.value.get("items") if existing else None) or [])

    items.append(
        {
            "user": (user or "")[:300],
            "assistant": (assistant or "")[:500],
        }
    )
    # Keep a bounded long-term window for the testing store.
    items = items[-30:]

    active_store.put(ns, LONG_TERM_NOTES_KEY, {"items": items})


def load_memory(email: str, document_id: str) -> list:
    """Return conversation history from the short-term checkpointer.

    Shape matches the old JSON memory for the frontend:
    [{"user": "...", "assistant": "..."}, ...]
    """

    if not document_id:
        return []

    config = invoke_config(email, document_id)
    checkpoint_tuple = checkpointer.get_tuple(config)

    if not checkpoint_tuple:
        return []

    values = checkpoint_tuple.checkpoint.get("channel_values") or {}
    history = values.get("history") or []

    return list(history)


def delete_memory(email: str, document_id: str) -> bool:
    """Clear short-term checkpoints and long-term Store entries for one document."""

    if not document_id:
        return False

    tid = thread_id(email, document_id)
    checkpointer.delete_thread(tid)

    ns = memory_namespace(email, document_id)

    for item in store.search(ns):
        store.delete(ns, item.key)

    return True


def answer_from_memory(
    question: str,
    history: Optional[list] = None,
    long_term_notes: str = "",
) -> str:
    """Answer questions about this chat using short-term + long-term memory."""

    history = history or []

    if not history and not long_term_notes:
        return (
            "We have not talked about this document yet, "
            "so there is no earlier question to reference."
        )

    conversation = _format_history(history)
    long_term_block = long_term_notes.strip() or "None yet."

    prompt = f"""You are a helpful assistant. Answer the user's question using ONLY the conversation history and long-term notes below.

Rules:
- If they ask about their first question, use Turn 1.
- If they ask about their last or previous question, use the latest relevant turn.
- Quote or paraphrase their actual words when helpful.
- Prefer short-term conversation history for recent turns; use long-term notes for older retained context.
- If the answer is not in the history or notes, say so clearly.

Conversation history (short-term):
{conversation}

Long-term notes:
{long_term_block}

User question: {question}

Answer:"""

    response = llm.invoke(prompt)

    return response.content.strip()


def answer_general(
    question: str,
    history: Optional[list] = None,
    long_term_notes: str = "",
) -> str:
    """Handle greetings / general questions with conversation awareness."""

    history = history or []
    conversation = _format_history(history) if history else "No conversation yet."
    long_term_block = long_term_notes.strip() or "None yet."

    prompt = f"""You are a Knowledge Assistant helping users with uploaded documents.

Conversation so far (short-term):
{conversation}

Long-term notes:
{long_term_block}

User question: {question}

If the question is about this chat, answer from the conversation history or long-term notes.
If it is a greeting or general question, respond helpfully and briefly.
If they need document content, suggest asking a specific question about the document."""

    response = llm.invoke(prompt)

    return response.content.strip()
