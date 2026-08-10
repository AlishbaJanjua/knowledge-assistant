from langgraph.graph import StateGraph, END

from agents.router import route_question
from agents.rag_agent import ask_question
from agents.memory_agent import answer_from_memory, answer_general



from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END


class AgentState(TypedDict):
    question: str
    db: object
    email: str
    document_id: str
    route: Optional[str]
    answer: Optional[str]



def router_node(state: AgentState):

    route = route_question(state["question"])

    return {
        **state,
        "route": route
    }



def rag_node(state: AgentState):

    answer = ask_question(
        state["db"],
        state["question"]
    )

    return {
        **state,
        "answer": answer
    }


def memory_node(state: AgentState):

    answer = answer_from_memory(
        state["email"],
        state["document_id"],
        state["question"],
    )

    return {
        **state,
        "answer": answer
    }



def general_node(state: AgentState):

    answer = answer_general(
        state["email"],
        state["document_id"],
        state["question"],
    )

    return {
        **state,
        "answer": answer
    }




def choose_route(state):

    return state["route"]




workflow = StateGraph(
    AgentState
)


workflow.add_node(
    "router",
    router_node
)

workflow.add_node(
    "rag",
    rag_node
)

workflow.add_node(
    "memory",
    memory_node
)

workflow.add_node(
    "general",
    general_node
)



workflow.set_entry_point(
    "router"
)



workflow.add_conditional_edges(
    "router",
    choose_route,
    {
        "rag":"rag",
        "memory":"memory",
        "general":"general"
    }
)


workflow.add_edge(
    "rag",
    END
)

workflow.add_edge(
    "memory",
    END
)

workflow.add_edge(
    "general",
    END
)



app = workflow.compile()