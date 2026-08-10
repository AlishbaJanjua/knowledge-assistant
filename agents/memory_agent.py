import json
import os

from backend.config import data_path
from backend.llm import llm


def _tenant_id(email):

    return email.replace("@", "_").replace(".", "_")


def memory_file(email, document_id):

    memory_dir = data_path(
        "memory",
        _tenant_id(email),
    )

    os.makedirs(memory_dir, exist_ok=True)

    return os.path.join(
        memory_dir,
        f"{document_id}.json",
    )


def legacy_memory_file(email):

    return data_path(
        "memory",
        f"{_tenant_id(email)}.json",
    )


def load_memory(email, document_id):

    if not document_id:
        return []

    path = memory_file(email, document_id)

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    legacy_path = legacy_memory_file(email)

    if not os.path.exists(legacy_path):
        return []

    with open(legacy_path, "r", encoding="utf-8") as f:
        history = json.load(f)

    if history:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4)

        with open(legacy_path, "w", encoding="utf-8") as f:
            json.dump([], f)

    return history


def save_memory(email, document_id, user, assistant):

    if not document_id:
        return

    path = memory_file(email, document_id)

    history = load_memory(email, document_id)

    history.append(
        {
            "user": user,
            "assistant": assistant,
        }
    )

    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            history,
            f,
            indent=4,
        )


def delete_memory(email, document_id):

    if not document_id:
        return False

    path = memory_file(email, document_id)

    if os.path.isfile(path):
        try:
            os.remove(path)
            return True
        except OSError:
            return False

    return False


def _format_history(history):

    lines = []

    for index, chat in enumerate(history, start=1):
        lines.append(f"Turn {index}")
        lines.append(f"User: {chat['user']}")
        lines.append(f"Assistant: {chat['assistant']}")
        lines.append("")

    return "\n".join(lines)


def answer_from_memory(email, document_id, question):

    history = load_memory(email, document_id)

    if not history:
        return "We have not talked about this document yet, so there is no earlier question to reference."

    conversation = _format_history(history)

    prompt = f"""You are a helpful assistant. Answer the user's question using ONLY the conversation history below.

Rules:
- If they ask about their first question, use Turn 1.
- If they ask about their last or previous question, use the latest relevant turn.
- Quote or paraphrase their actual words when helpful.
- If the answer is not in the history, say so clearly.

Conversation history:
{conversation}

User question: {question}

Answer:"""

    response = llm.invoke(prompt)

    return response.content.strip()


def answer_general(email, document_id, question):

    history = load_memory(email, document_id)
    conversation = (
        _format_history(history)
        if history
        else "No conversation yet."
    )

    prompt = f"""You are a Knowledge Assistant helping users with uploaded documents.

Conversation so far:
{conversation}

User question: {question}

If the question is about this chat, answer from the conversation history.
If it is a greeting or general question, respond helpfully and briefly.
If they need document content, suggest asking a specific question about the document."""

    response = llm.invoke(prompt)

    return response.content.strip()
