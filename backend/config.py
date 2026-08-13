from dotenv import load_dotenv
import os

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL")
SESSION_SECRET = os.getenv("SESSION_SECRET")

DATA_DIR = os.getenv("DATA_DIR", ".")


def data_path(*parts: str) -> str:

    return os.path.join(DATA_DIR, *parts)


def ensure_data_dirs():

    for name in ("uploads", "chroma_db", "langgraph_memory", "accounts"):
        os.makedirs(data_path(name), exist_ok=True)


ensure_data_dirs()
