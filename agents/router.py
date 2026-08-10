from backend.llm import llm


MEMORY_KEYWORDS = [
    "previous",
    "history",
    "earlier",
    "last time",
    "remember",
    "first question",
    "last question",
    "previous question",
    "what did i ask",
    "what did we",
    "did i ask",
    "have i asked",
    "i asked",
    "my question",
    "you said",
    "you answered",
    "we talked",
    "we discussed",
    "conversation",
    "chat history",
    "before i",
    "recap",
    "summarize our chat",
    "our chat",
    "this chat",
]


RAG_KEYWORDS = [
    "document",
    "file",
    "pdf",
    "ppt",
    "slide",
    "chapter",
    "page",
    "explain",
    "summary",
    "summarize",
    "what is",
    "define",
    "according to",
    "in the document",
    "demand",
    "function",
    "concept",
]


def _matches_memory(question: str) -> bool:

    for phrase in MEMORY_KEYWORDS:
        if phrase in question:
            return True

    return False


def _matches_rag(question: str) -> bool:

    for phrase in RAG_KEYWORDS:
        if phrase in question:
            return True

    return False


def _llm_route(question: str) -> str:

    prompt = f"""Classify this user message into exactly one category.

Categories:
- memory: questions about this chat itself (what was asked before, first/last question, recap)
- rag: questions about document content (explain, summarize, define, concepts from the file)
- general: casual or off-topic questions not about the chat or document

Message: {question}

Reply with only one word: memory, rag, or general"""

    response = llm.invoke(prompt).content.strip().lower()

    if response.startswith("memory"):
        return "memory"

    if response.startswith("rag"):
        return "rag"

    return "general"


def route_question(question: str) -> str:

    question = question.lower().strip()

    if _matches_memory(question):
        return "memory"

    if _matches_rag(question):
        return "rag"

    return _llm_route(question)
