# Hugging Face Space (Docker SDK) for the Nia backend. Free CPU hardware; listens on port 7860.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface \
    HRBOT_RUNTIME_DIR=/tmp/hrbot

# Spaces run the container as user 1000.
RUN useradd -m -u 1000 user
WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY --chown=user backend/ /app/backend/
COPY --chown=user documents/ /app/documents/
COPY --chown=user data/employees.csv /app/data/employees.csv
RUN mkdir -p /app/.cache && chown -R user:user /app
USER user

# Bake both search models into the image, so a sleeping Space does not re-download them on wake-up.
RUN python -c "from backend import config; \
from fastembed import TextEmbedding; \
from fastembed.rerank.cross_encoder import TextCrossEncoder; \
TextEmbedding(config.EMBED_MODEL, cache_dir=str(config.EMBED_CACHE_DIR)); \
TextCrossEncoder(config.RERANK_MODEL, cache_dir=str(config.EMBED_CACHE_DIR)); print('models cached')"

EXPOSE 7860
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "7860"]
