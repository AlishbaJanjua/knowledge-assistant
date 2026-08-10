from backend.llm import llm

SYSTEM_PROMPT = """
You are a helpful AI Knowledge Base Assistant.

Currently, no documents have been uploaded.

Answer general questions politely.

Once documents are uploaded, you should answer ONLY from the retrieved document context.

If the answer is not present in the knowledge base, clearly say that you could not find the information.
"""

def chat(query: str):

    messages = [
        ("system", SYSTEM_PROMPT),
        ("human", query)
    ]

    response = llm.invoke(messages)

    return response.content