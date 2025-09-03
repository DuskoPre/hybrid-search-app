# -------- Stage 2: app runtime ------------
FROM python:3.9-slim AS app

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    curl unzip ca-certificates \
    redis-server supervisor gosu jq procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# python deps (cached when possible)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# app files
COPY app/ ./app/
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# (optional) prefetch HF cache
# RUN python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='sentence-transformers/all-MiniLM-L6-v2')"

EXPOSE 8000 6379

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
  CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["/usr/bin/supervisord","-c","/etc/supervisor/conf.d/supervisord.conf"]
