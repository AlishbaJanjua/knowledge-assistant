from dotenv import load_dotenv
import os

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL")
SESSION_SECRET = os.getenv("SESSION_SECRET")

# Project root (…/knowledge-assistant). Relative DATA_DIR must not depend on process cwd,
# otherwise accounts/uploads/chroma/memory can silently resolve to a different path.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_raw_data_dir = os.getenv("DATA_DIR", ".") or "."
if os.path.isabs(_raw_data_dir):
    DATA_DIR = os.path.abspath(_raw_data_dir)
else:
    DATA_DIR = os.path.abspath(os.path.join(_PROJECT_ROOT, _raw_data_dir))


def data_path(*parts: str) -> str:

    return os.path.join(DATA_DIR, *parts)


def ensure_data_dirs():

    for name in ("uploads", "chroma_db", "langgraph_memory", "accounts"):
        os.makedirs(data_path(name), exist_ok=True)


ensure_data_dirs()
