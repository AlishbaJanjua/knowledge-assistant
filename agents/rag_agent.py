from langchain_groq import ChatGroq
from dotenv import load_dotenv
import os
from backend.llm import llm

load_dotenv()


llm = ChatGroq(
    model="llama-3.1-8b-instant",
    api_key=os.getenv("GROQ_API_KEY")
)



def _context_from_document(doc):
    """
    Prefer bounded parent_content for parent-child children when present.
    Falls back to the child/page text so normal RAG is unchanged.
    """

    metadata = getattr(doc, "metadata", None) or {}
    parent_content = metadata.get("parent_content")

    if isinstance(parent_content, str) and parent_content.strip():
        child_text = (doc.page_content or "").strip()
        if child_text and child_text not in parent_content:
            return f"{parent_content}\n\nRelevant section:\n{child_text}"
        return parent_content

    return doc.page_content or ""


def _format_recent_history(history, limit=6):

    if not history:
        return ""

    lines = []

    for chat in history[-limit:]:
        lines.append(f"User: {chat.get('user', '')}")
        lines.append(f"Assistant: {chat.get('assistant', '')}")

    return "\n".join(lines)


def ask_question(db, question, history=None):


    summary_words = [
        "what is this document about",
        "summarize",
        "summary",
        "main topics",
        "overview",
        "explain the document"
    ]


    if any(word in question.lower() for word in summary_words):

        docs = db.get()

        docs = docs["documents"][:15]


        context = "\n\n".join(docs)


    else:

        docs = db.similarity_search(
            question,
            k=5
        )


        context = "\n\n".join(
            [
                _context_from_document(doc)
                for doc in docs
            ]
        )

    recent = _format_recent_history(history)
    history_block = (
        f"\nRecent conversation (for follow-ups only):\n{recent}\n"
        if recent
        else ""
    )

    prompt = f"""
You are a document assistant.

Answer using ONLY this document context.
Use recent conversation only to resolve follow-up references
(e.g. "that", "it", "the previous topic"). Do not invent document facts
from chat history alone.

If the question asks for an overview,
identify the major topics from the entire document.

Context:

{context}
{history_block}

Question:

{question}


Answer:
"""


    response = llm.invoke(
        prompt
    )


    return response.content