FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data/uploads /data/memory /data/chroma_db

ENV DATA_DIR=/data
ENV RELOAD=false
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl --fail http://localhost:${PORT}/api/health || exit 1

CMD ["sh", "-c", "uvicorn backend.api:api --host 0.0.0.0 --port ${PORT} --timeout-keep-alive 300"]
