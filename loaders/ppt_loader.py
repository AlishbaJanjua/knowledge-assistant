from langchain_community.document_loaders import UnstructuredPowerPointLoader


def load_ppt(file_path):

    loader = UnstructuredPowerPointLoader(
        file_path
    )

    documents = loader.load()


    for index, doc in enumerate(documents):

        doc.metadata["slide_number"] = index + 1
        doc.metadata["source_type"] = "ppt"


    return documents