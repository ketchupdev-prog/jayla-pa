# Railway: requirements-railway.txt includes docling for RAG ingest; no sentence-transformers (torch).
FROM python:3.12-slim

WORKDIR /app

# psycopg2-binary: libpq5. docling/RAG: libgl1 for PDF rendering if needed.
RUN apt-get update -qq && apt-get install -y --no-install-recommends \
    libpq5 libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip; install slim deps. Constrain langchain-arcade to 1.3.1 (ToolManager API).
COPY requirements-railway.txt constraints-railway.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements-railway.txt -c constraints-railway.txt

# App code.
COPY . .

# Railway sets PORT at runtime.
CMD ["sh", "-c", "exec uvicorn telegram_bot.webhook:app --host 0.0.0.0 --port ${PORT:-8000}"]
