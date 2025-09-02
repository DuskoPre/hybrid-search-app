.PHONY: build up down setup logs status clean test-search scrape-sample

# Build and start the single container
build:
	@echo "🔨 Building hybrid search container..."
	docker-compose build

# Start the all-in-one container
up:
	@echo "🚀 Starting hybrid search stack..."
	docker-compose up -d
	@echo "⏳ Waiting for services to initialize (2-3 minutes for model loading)..."
	@echo "📊 Check status with: make status"

# Complete setup with sample data
setup: up
	@echo "⏳ Waiting for services to be ready..."
	@sleep 60
	@echo "🔧 Setting up Solr collection..."
	@docker exec hybrid-search-all-in-one /app/setup-solr.sh
	@echo "📝 Adding sample Wikipedia content..."
	@make scrape-sample
	@echo ""
	@echo "🎉 Hybrid search stack is ready!"
	@echo "📊 FastAPI: http://localhost:8000"
	@echo "📊 Solr UI: http://localhost:8983"
	@echo "🔍 Try: make test-search"

# Stop the container
down:
	@echo "🛑 Stopping hybrid search stack..."
	docker-compose down

# Add sample Wikipedia content
scrape-sample:
	@echo "🌐 Adding sample Wikipedia content..."
	@curl -X POST "http://localhost:8000/scrape" \
		-H "Content-Type: application/json" \
		-d '{"urls": ["https://en.wikipedia.org/wiki/Machine_learning", "https://en.wikipedia.org/wiki/Information_retrieval", "https://en.wikipedia.org/wiki/Natural_language_processing"]}'
	@echo "✅ Scraping started in background"

# Test search functionality
test-search:
	@echo "🔍 Testing hybrid search functionality..."
	@echo ""
	@echo "1️⃣ BM25 Search:"
	@curl -s -X POST "http://localhost:8000/search" \
		-H "Content-Type: application/json" \
		-d '{"query": "machine learning", "search_type": "bm25", "rows": 3}' | \
		jq -r '.results[] | "📄 \(.title) | Score: \(.score)"'
	@echo ""
	@echo "2️⃣ Vector Search:"
	@curl -s -X POST "http://localhost:8000/search" \
		-H "Content-Type: application/json" \
		-d '{"query": "neural networks", "search_type": "vector", "rows": 3}' | \
		jq -r '.results[] | "🧠 \(.title) | Similarity: \(.score)"'
	@echo ""
	@echo "3️⃣ Hybrid Search + LTR:"
	@curl -s -X POST "http://localhost:8000/search" \
		-H "Content-Type: application/json" \
		-d '{"query": "information retrieval", "search_type": "hybrid", "rows": 3}' | \
		jq -r '.results[] | "🎯 \(.title) | Final Score: \(.score)"'

# Show current statistics
status:
	@echo "📊 === HYBRID SEARCH STATUS ==="
	@echo ""
	@docker-compose ps
	@echo ""
	@echo "📈 Collection Statistics:"
	@curl -s "http://localhost:8000/stats" | jq '.'
	@echo ""
	@echo "🏥 Service Health:"
	@curl -s "http://localhost:8000/health" | jq '.services'

# View logs from all services
logs:
	@echo "📋 Viewing container logs..."
	docker-compose logs -f --tail 50

# Clean everything
clean: down
	@echo "🧹 Cleaning up all data..."
	docker-compose down -v
	docker system prune -f
	@echo "✅ Cleanup complete!"

# Interactive search session
search:
	@echo "🔍 Interactive Search Session"
	@echo "Enter your search query:"
	@read query; \
	echo "Choose search type (1=BM25, 2=Vector, 3=Hybrid): "; \
	read type; \
	case $type in \
		1) search_type="bm25";; \
		2) search_type="vector";; \
		3) search_type="hybrid";; \
		*) search_type="hybrid";; \
	esac; \
	curl -s -X POST "http://localhost:8000/search" \
		-H "Content-Type: application/json" \
		-d "{\"query\": \"$query\", \"search_type\": \"$search_type\", \"rows\": 5}" | \
		jq -r '.results[] | "📄 \(.title)\n   URL: \(.url)\n   Score: \(.score)\n"'

# Add custom URLs
add-urls:
	@echo "📋 Add URLs to index:"
	@echo "Enter URLs (one per line, empty line to finish):"
	@urls=""; \
	while read -r url; do \
		if [ -z "$url" ]; then break; fi; \
		if [ -z "$urls" ]; then \
			urls="\"$url\""; \
		else \
			urls="$urls, \"$url\""; \
		fi; \
	done; \
	if [ -n "$urls" ]; then \
		curl -X POST "http://localhost:8000/scrape" \
			-H "Content-Type: application/json" \
			-d "{\"urls\": [$urls]}"; \
		echo "✅ URLs added for scraping"; \
	fi
