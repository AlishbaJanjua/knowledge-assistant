from langchain_groq import ChatGroq
from dotenv import load_dotenv
import os
from backend.llm import llm

load_dotenv()


llm = ChatGroq(
    model="llama-3.1-8b-instant",
    api_key=os.getenv("GROQ_API_KEY")
)



def ask_question(db, question):


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
                doc.page_content
                for doc in docs
            ]
        )



    prompt = f"""
You are a document assistant.

Answer using ONLY this document context.

If the question asks for an overview,
identify the major topics from the entire document.

Context:

{context}


Question:

{question}


Answer:
"""


    response = llm.invoke(
        prompt
    )


    return response.content