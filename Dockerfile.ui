# ──────────────────────────────────────────────────────────────
#  Dockerfile.ui  —  AyuGuard FastAPI UI Service
#  Runs: uvicorn ui.server:app
#  Port: $PORT (Cloud Run injects 8080)
# ──────────────────────────────────────────────────────────────
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy full project (UI server imports from ayuguard.tools directly)
COPY ayuguard/ ./ayuguard/
COPY datasets/ ./datasets/
COPY ui/ ./ui/

# Seed data directory
COPY ayuguard/data/ ./ayuguard/data/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV GOOGLE_GENAI_USE_VERTEXAI=FALSE

# Cloud Run: PORT=8080 is injected automatically
CMD ["sh", "-c", "python ui/server.py"]
