#!/bin/bash
set -e

SOLR_URL="http://localhost:8983/solr"
COLLECTION_NAME="hybrid_search"

echo "🔧 Setting up Solr collection for hybrid search..."

# Wait for Solr to be ready
while ! curl -s "$SOLR_URL/admin/ping" >/dev/null 2>&1; do
    echo "⏳ Waiting for Solr to start..."
    sleep 5
done

echo "✅ Solr is ready!"

# Create collection
echo "📋 Creating collection: $COLLECTION_NAME"
curl -X POST "$SOLR_URL/admin/cores" \
    -F "action=CREATE" \
    -F "name=$COLLECTION_NAME" \
    -F "configSet=_default" || echo "Collection may already exist"

sleep 5

# Add vector field type
echo "🧠 Adding vector field type (384 dimensions)..."
curl -X POST "$SOLR_URL/$COLLECTION_NAME/schema" \
    -H "Content-Type: application/json" \
    -d '{
        "add-field-type": {
            "name": "knn_vector",
            "class": "solr.DenseVectorField",
            "vectorDimension": 384,
            "similarityFunction": "cosine",
            "knnAlgorithm": "hnsw"
        }
    }' || echo "Field type may already exist"

sleep 2

# Add fields
echo "📝 Adding schema fields..."
curl -X POST "$SOLR_URL/$COLLECTION_NAME/schema" \
    -H "Content-Type: application/json" \
    -d '{
        "add-field": [
            {"name": "url", "type": "string", "indexed": true, "stored": true},
            {"name": "title", "type": "text_general", "indexed": true, "stored": true},
            {"name": "content", "type": "text_general", "indexed": true, "stored": true},
            {"name": "content_vector", "type": "knn_vector", "indexed": true, "stored": true},
            {"name": "domain", "type": "string", "indexed": true, "stored": true},
            {"name": "crawl_date", "type": "pdate", "indexed": true, "stored": true},
            {"name": "page_rank", "type": "pfloat", "indexed": true, "stored": true},
            {"name": "content_length", "type": "plong", "indexed": true, "stored": true}
        ]
    }' || echo "Fields may already exist"

echo "✅ Solr collection setup complete!"
