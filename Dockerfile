FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    openjdk-11-jdk \
    wget \
    curl \
    unzip \
    redis-server \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Set JAVA_HOME
ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64

# Create app directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download and setup Solr
ENV SOLR_VERSION=9.4.1
RUN wget https://archive.apache.org/dist/lucene/solr/${SOLR_VERSION}/solr-${SOLR_VERSION}.tgz && \
    tar -xzf solr-${SOLR_VERSION}.tgz && \
    mv solr-${SOLR_VERSION} /opt/solr && \
    rm solr-${SOLR_VERSION}.tgz

# Create Solr user and directories
RUN useradd -m -s /bin/bash solr && \
    mkdir -p /var/solr/data /var/solr/logs && \
    chown -R solr:solr /var/solr /opt/solr

# Copy application files
COPY app/ ./app/
COPY solr-configs/ ./solr-configs/
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Pre-download embedding model
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Setup Solr collection and schema
COPY setup-solr.sh /app/setup-solr.sh
RUN chmod +x /app/setup-solr.sh

# Expose ports
EXPOSE 8000 8983 6379

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start all services with supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
