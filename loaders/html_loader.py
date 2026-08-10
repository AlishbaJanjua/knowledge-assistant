from langchain_community.document_loaders import BSHTMLLoader


def load_html(file_path):
    loader = BSHTMLLoader(file_path)
    return loader.load()