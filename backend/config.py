from dotenv import load_dotenv
import os

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY")

DATA_DIR = os.getenv("DATA_DIR", ".")


def data_path(*parts: str) -> str:

    return os.path.join(DATA_DIR, *parts)


def ensure_data_dirs():

    for name in ("uploads", "memory", "chroma_db"):
        os.makedirs(data_path(name), exist_ok=True)


ensure_data_dirs()
