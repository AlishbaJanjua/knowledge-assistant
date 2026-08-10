from langchain_community.document_loaders.csv_loader import CSVLoader


def load_csv(file_path):
    loader = CSVLoader(file_path)
    return loader.load()