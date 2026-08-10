from langchain_text_splitters import RecursiveCharacterTextSplitter


def chunk_documents(documents):

    splitter = RecursiveCharacterTextSplitter(

        chunk_size=1500,

        chunk_overlap=300,

        separators=[
            "\n\n",
            "\n",
            ".",
            " "
        ]
    )


    return splitter.split_documents(
        documents
    )