# syntax=docker/dockerfile:1

# ---- 1. Build the frontend ---------------------------------------------------
FROM node:22-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- 2. Python environment and embedding model -------------------------------
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.12.9 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# Dependencies first, so this (large) layer is only rebuilt when the lockfile changes.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --extra prod --no-install-project
COPY semantic_grooves ./semantic_grooves
RUN uv sync --frozen --no-dev --extra prod --no-editable

# Bake the embedding model (about 1.3 GB) into the image so containers start without
# internet access and without downloading it on every new host.
ENV HF_HOME=/opt/huggingface
RUN /app/.venv/bin/python -c "from sentence_transformers import SentenceTransformer; from semantic_grooves.config import MODEL_NAME; SentenceTransformer(MODEL_NAME, device='cpu')"

# ---- 3. Runtime image --------------------------------------------------------
FROM python:3.12-slim
RUN useradd --system --uid 10001 --create-home app && mkdir /data && chown app /data
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /opt/huggingface /opt/huggingface
COPY --from=frontend /build/dist /app/static
COPY docker/entrypoint.sh docker/gunicorn.conf.py /app/
RUN chmod +x /app/entrypoint.sh

ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/opt/huggingface \
    HF_HUB_OFFLINE=1 \
    SG_DEVICE=cpu \
    SG_DB_PATH=/data/database.sqlite \
    SG_STATIC_DIR=/app/static

USER app
VOLUME /data
EXPOSE 8000

# 200 only when the database opens; the model is loaded at start-up, which takes a while.
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "-c", "/app/gunicorn.conf.py", "semantic_grooves.api:app"]
