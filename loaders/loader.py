import os

from loaders.pdf_loader import load_pdf
from loaders.docx_loader import load_docx
from loaders.txt_loader import load_txt
from loaders.csv_loader import load_csv
from loaders.md_loader import load_md
from loaders.html_loader import load_html
from loaders.ppt_loader import load_ppt

def load_document(file_path):
    extension = os.path.splitext(file_path)[1].lower()

    if extension == ".pdf":
        return load_pdf(file_path)

    elif extension == ".docx":
        return load_docx(file_path)

    elif extension == ".txt":
        return load_txt(file_path)

    elif extension == ".csv":
        return load_csv(file_path)

    elif extension == ".md":
        return load_md(file_path)

    elif extension in [".html", ".htm"]:
        return load_html(file_path)

    elif extension == ".pptx":
        return load_ppt(file_path)
    
    else:
        raise ValueError(f"Unsupported file type: {extension}")

