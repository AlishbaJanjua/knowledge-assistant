from operator import add
from typing import Annotated, Optional, TypedDict

from langgraph.config import get_store
from langgraph.graph import END, StateGraph

from agents.memory_agent import (
    answer_from_memory,
    answer_general,
    checkpointer,
    read_long_term_notes,
    store,
    tenant_id_from_email,
    update_long_term_memory,
)
from agents.rag_agent import ask_question
from agents.router import route_question
from vectorstore.chroma_db import load_vectorstore


class AgentState(TypedDict):
    question: str
    email: str
    document_id: str
    route: Optional[str]
    answer: Optional[str]
    # Short-term conversation turns accumulated via the checkpointer.
    history: Annotated[list, add]


def router_node(state: AgentState):

    route = route_question(state["question"])

    return {"route": route}


def rag_node(state: AgentState):

    # Load Chroma outside checkpointed state (not msgpack-serializable).
    tenant_id = tenant_id_from_email(state["email"])
    db = load_vectorstore(tenant_id, state["document_id"])

    if not db:
        answer = "Document knowledge base not found."
    else:
        history = state.get("history") or []
        answer = ask_question(
            db,
            state["question"],
            history=history,
        )

    runtime_store = get_store()
    update_long_term_memory(
        state["email"],
        state["document_id"],
        state["question"],
        answer,
        runtime_store=runtime_store,
    )

    return {
        "answer": answer,
        "history": [
            {
                "user": state["question"],
                "assistant": answer,
            }
        ],
    }


def memory_node(state: AgentState):

    runtime_store = get_store()
    history = state.get("history") or []
    long_term_notes = read_long_term_notes(
        state["email"],
        state["document_id"],
        runtime_store=runtime_store,
    )

    answer = answer_from_memory(
        state["question"],
        history,
        long_term_notes,
    )

    update_long_term_memory(
        state["email"],
        state["document_id"],
        state["question"],
        answer,
        runtime_store=runtime_store,
    )

    return {
        "answer": answer,
        "history": [
            {
                "user": state["question"],
                "assistant": answer,
            }
        ],
    }


def general_node(state: AgentState):

    runtime_store = get_store()
    history = state.get("history") or []
    long_term_notes = read_long_term_notes(
        state["email"],
        state["document_id"],
        runtime_store=runtime_store,
    )

    answer = answer_general(
        state["question"],
        history,
        long_term_notes,
    )

    update_long_term_memory(
        state["email"],
        state["document_id"],
        state["question"],
        answer,
        runtime_store=runtime_store,
    )

    return {
        "answer": answer,
        "history": [
            {
                "user": state["question"],
                "assistant": answer,
            }
        ],
    }


def choose_route(state):

    return state["route"]


workflow = StateGraph(AgentState)

workflow.add_node("router", router_node)
workflow.add_node("rag", rag_node)
workflow.add_node("memory", memory_node)
workflow.add_node("general", general_node)

workflow.set_entry_point("router")

workflow.add_conditional_edges(
    "router",
    choose_route,
    {
        "rag": "rag",
        "memory": "memory",
        "general": "general",
    },
)

workflow.add_edge("rag", END)
workflow.add_edge("memory", END)
workflow.add_edge("general", END)

# Short-term: SqliteSaver checkpointer. Long-term: SqliteStore.
app = workflow.compile(
    checkpointer=checkpointer,
    store=store,
)
