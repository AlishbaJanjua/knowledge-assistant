"""Run the Knowledge Assistant web app (FastAPI + custom frontend)."""

import os

import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "true").lower() in ("1", "true", "yes")

    uvicorn.run(
        "backend.api:api",
        host="0.0.0.0",
        port=port,
        reload=reload,
        timeout_keep_alive=300,
    )
