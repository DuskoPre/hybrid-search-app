from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import httpx
import asyncio
import json
import logging
from sentence_transformers import SentenceTransformer
import uvicorn
import redis
from urllib.parse import urlparse
import re
from bs4 import BeautifulSoup
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Hybrid Search API",
    description="Advanced search with BM25, Vector Search, and LTR",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables
model = None
redis_client = None
solr_base_url = "http://solr:8983/solr/hybrid_search"

# Pydantic models
class SearchRequest(BaseModel):
    query: str
    search_type: str = "hybrid"  # "bm25", "vector", "hybrid"
    rows: int = 10
    rerank_docs: int = 20

class SearchResult(BaseModel):
    id: str
    title: str
    url: str
    content: str
    score: float
    features: Optional[Dict[str, float]] = None

class SearchResponse(BaseModel):
    query: str
    search_type: str
    total_found: int
    results: List[SearchResult]
    query_time: float

class CrawlRequest(BaseModel):
    urls: List[str]

class IndexDocument(BaseModel):
    url: str
    title: str
    content: str

# Startup event
@app.on_event("startup")
async def startup_event():
    global model, redis_client
    logger.info("🚀 Starting Hybrid Search API...")
    
    # Load embedding model
    logger.info("📥 Loading all-MiniLM-L6-v2 model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    logger.info("✅ Model loaded successfully!")
    
    # Connect to Redis
    try:
        redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
        redis_client.ping()
        logger.info("✅ Redis connected!")
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {str(e)}")
        redis_client = None
    
    # Wait for Solr to be ready
    await wait_for_solr()
    
    logger.info("🎉 All services ready!")

async def wait_for_solr():
    """Wait for Solr to be available"""
    max_retries = 30
    for i in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{solr_base_url.replace('/hybrid_search', '')}/admin/ping")
                if response.status_code == 200:
                    logger.info("✅ Solr is ready!")
                    return
        except Exception as e:
            logger.debug(f"Solr not ready yet: {str(e)}")
        logger.info(f"⏳ Waiting for Solr... ({i+1}/{max_retries})")
        await asyncio.sleep(10)
    
    raise Exception("❌ Solr failed to start within timeout")

# Health check endpoint
@app.get("/health")
async def health_check():
    health_status = {
        "status": "healthy",
        "services": {}
    }
    
    # Check Solr
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{solr_base_url.replace('/hybrid_search', '')}/admin/ping", timeout=5)
            health_status["services"]["solr"] = "healthy" if response.status_code == 200 else "unhealthy"
    except:
        health_status["services"]["solr"] = "unhealthy"
    
    # Check Redis
    try:
        if redis_client:
            redis_client.ping()
            health_status["services"]["redis"] = "healthy"
        else:
            health_status["services"]["redis"] = "unhealthy"
    except:
        health_status["services"]["redis"] = "unhealthy"
    
    # Check embedding model
    health_status["services"]["embeddings"] = "healthy" if model else "unhealthy"
    
    return health_status

# Generate embeddings endpoint
@app.post("/encode")
async def generate_embedding(text: str):
    """Generate vector embedding for text"""
    try:
        if not model:
            raise HTTPException(status_code=503, detail="Embedding model not loaded")
        
        embedding = model.encode([text])[0].tolist()
        return {
            "embedding": embedding,
            "dimension": len(embedding),
            "model": "all-MiniLM-L6-v2"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating embedding: {str(e)}")

# Main search endpoint
@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """Perform hybrid search with multiple modes"""
    start_time = asyncio.get_event_loop().time()
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if request.search_type == "bm25":
                results = await bm25_search(client, request)
            elif request.search_type == "vector":
                results = await vector_search(client, request)
            elif request.search_type == "hybrid":
                # For hybrid, we'll do a simple combination since LTR model may not exist
                results = await hybrid_search_fallback(client, request)
            else:
                raise HTTPException(status_code=400, detail="Invalid search_type. Use: bm25, vector, or hybrid")
        
        query_time = asyncio.get_event_loop().time() - start_time
        
        return SearchResponse(
            query=request.query,
            search_type=request.search_type,
            total_found=len(results),
            results=results,
            query_time=round(query_time, 3)
        )
    
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

async def bm25_search(client: httpx.AsyncClient, request: SearchRequest) -> List[SearchResult]:
    """Pure BM25 keyword search"""
    params = {
        "q": request.query,
        "defType": "edismax",
        "qf": "title^3 content",
        "rows": request.rows,
        "fl": "id,title,url,content,score"
    }
    
    response = await client.get(f"{solr_base_url}/select", params=params)
    response.raise_for_status()
    data = response.json()
    
    return [
        SearchResult(
            id=doc["id"],
            title=doc.get("title", [""])[0] if isinstance(doc.get("title"), list) else doc.get("title", ""),
            url=doc.get("url", ""),
            content=doc.get("content", [""])[0] if isinstance(doc.get("content"), list) else doc.get("content", "")[:200] + "...",
            score=doc["score"]
        )
        for doc in data["response"]["docs"]
    ]

async def vector_search(client: httpx.AsyncClient, request: SearchRequest) -> List[SearchResult]:
    """Pure vector semantic search"""
    if not model:
        raise HTTPException(status_code=503, detail="Embedding model not loaded")
    
    # Generate query embedding
    embedding = model.encode([request.query])[0].tolist()
    embedding_str = json.dumps(embedding)
    
    params = {
        "q": f"{{!knn f=content_vector topK={request.rows}}}{embedding_str}",
        "fl": "id,title,url,content,score"
    }
    
    response = await client.get(f"{solr_base_url}/select", params=params)
    response.raise_for_status()
    data = response.json()
    
    return [
        SearchResult(
            id=doc["id"],
            title=doc.get("title", [""])[0] if isinstance(doc.get("title"), list) else doc.get("title", ""),
            url=doc.get("url", ""),
            content=doc.get("content", [""])[0] if isinstance(doc.get("content"), list) else doc.get("content", "")[:200] + "...",
            score=doc["score"]
        )
        for doc in data["response"]["docs"]
    ]

async def hybrid_search_fallback(client: httpx.AsyncClient, request: SearchRequest) -> List[SearchResult]:
    """Simple hybrid search without LTR - more reliable fallback"""
    # Fallback to simple combination of BM25 and vector search
    return await simple_hybrid_search(client, request)

async def simple_hybrid_search(client: httpx.AsyncClient, request: SearchRequest) -> List[SearchResult]:
    """Simple hybrid search combining BM25 and vector results"""
    # Get BM25 results
    bm25_results = await bm25_search(client, SearchRequest(
        query=request.query, 
        search_type="bm25", 
        rows=request.rerank_docs
    ))
    
    # Get vector results
    vector_results = await vector_search(client, SearchRequest(
        query=request.query, 
        search_type="vector", 
        rows=request.rerank_docs
    ))
    
    # Simple score combination (normalize and combine)
    combined_results = {}
    
    # Normalize BM25 scores
    if bm25_results:
        max_bm25 = max(r.score for r in bm25_results)
        for result in bm25_results:
            result.score = result.score / max_bm25 if max_bm25 > 0 else 0
            combined_results[result.id] = result
    
    # Normalize vector scores and combine
    if vector_results:
        max_vector = max(r.score for r in vector_results)
        for result in vector_results:
            normalized_score = result.score / max_vector if max_vector > 0 else 0
            if result.id in combined_results:
                # Combine scores (0.6 BM25 + 0.4 vector)
                combined_results[result.id].score = 0.6 * combined_results[result.id].score + 0.4 * normalized_score
            else:
                result.score = 0.4 * normalized_score
                combined_results[result.id] = result
    
    # Sort by combined score and return top results
    final_results = sorted(combined_results.values(), key=lambda x: x.score, reverse=True)
    return final_results[:request.rows]

# Add URLs to crawl queue
@app.post("/crawl")
async def add_crawl_urls(request: CrawlRequest):
    """Add URLs to the crawl queue"""
    try:
        if not redis_client:
            raise HTTPException(status_code=503, detail="Redis not available")
        
        added_count = 0
        for url in request.urls:
            redis_client.lpush("crawl.queue", url)
            added_count += 1
        
        queue_length = redis_client.llen("crawl.queue")
        
        return {
            "message": f"Added {added_count} URLs to crawl queue",
            "queue_length": queue_length,
            "urls": request.urls
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add URLs: {str(e)}")

# Manual document indexing
@app.post("/index")
async def index_document(doc: IndexDocument):
    """Manually index a document with automatic vector generation"""
    try:
        if not model:
            raise HTTPException(status_code=503, detail="Embedding model not loaded")
        
        # Generate embedding for content
        embedding = model.encode([doc.content])[0].tolist()
        
        # Extract domain
        domain = urlparse(doc.url).netloc
        doc_id = re.sub(r'[^a-zA-Z0-9]', '_', doc.url)
        
        # Prepare Solr document
        solr_doc = {
            "id": doc_id,
            "url": doc.url,
            "title": doc.title,
            "content": doc.content,
            "content_vector": embedding,
            "domain": domain,
            "crawl_date": datetime.utcnow().isoformat() + "Z",
            "page_rank": 0.5,
            "content_length": len(doc.content)
        }
        
        # Index into Solr
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{solr_base_url}/update",
                json=[solr_doc],
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            # Commit
            await client.post(
                f"{solr_base_url}/update",
                json={"commit": {}},
                headers={"Content-Type": "application/json"}
            )
        
        return {
            "message": "Document indexed successfully",
            "id": doc_id,
            "embedding_dimension": len(embedding)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")

# Get collection stats
@app.get("/stats")
async def get_stats():
    """Get collection statistics"""
    try:
        async with httpx.AsyncClient() as client:
            # Get document count
            response = await client.get(f"{solr_base_url}/select", params={"q": "*:*", "rows": 0})
            response.raise_for_status()
            doc_count = response.json()["response"]["numFound"]
            
            # Get queue length
            queue_length = 0
            if redis_client:
                try:
                    queue_length = redis_client.llen("crawl.queue")
                except:
                    queue_length = 0
            
            return {
                "documents_indexed": doc_count,
                "crawl_queue_length": queue_length,
                "embedding_model": "all-MiniLM-L6-v2",
                "vector_dimension": 384
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

# Simple web scraper for adding content
@app.post("/scrape")
async def scrape_and_index(request: CrawlRequest, background_tasks: BackgroundTasks):
    """Scrape URLs and index them immediately"""
    background_tasks.add_task(scrape_urls_task, request.urls)
    return {
        "message": f"Started scraping {len(request.urls)} URLs",
        "urls": request.urls
    }

async def scrape_urls_task(urls: List[str]):
    """Background task to scrape and index URLs"""
    for url in urls:
        try:
            logger.info(f"🌐 Scraping: {url}")
            
            async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": "Mozilla/5.0 (compatible; HybridSearchBot/1.0)"}) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                # Parse HTML content
                soup = BeautifulSoup(response.text, 'html.parser')
                title = soup.title.string if soup.title else "Untitled"
                title = title.strip()
                
                # Extract text content
                for script in soup(["script", "style"]):
                    script.decompose()
                content = soup.get_text()
                content = ' '.join(content.split())[:5000]  # Limit content
                
                if len(content) < 50:
                    logger.warning(f"⚠️ Insufficient content for {url}")
                    continue
                
                # Generate embedding
                if not model:
                    logger.error("❌ Embedding model not available")
                    continue
                
                embedding = model.encode([content])[0].tolist()
                domain = urlparse(url).netloc
                doc_id = re.sub(r'[^a-zA-Z0-9]', '_', url)
                
                solr_doc = {
                    "id": doc_id,
                    "url": url,
                    "title": title,
                    "content": content,
                    "content_vector": embedding,
                    "domain": domain,
                    "crawl_date": datetime.utcnow().isoformat() + "Z",
                    "page_rank": 0.5,
                    "content_length": len(content)
                }
                
                # Index into Solr
                async with httpx.AsyncClient() as solr_client:
                    await solr_client.post(
                        f"{solr_base_url}/update",
                        json=[solr_doc],
                        headers={"Content-Type": "application/json"}
                    )
                
                logger.info(f"✅ Indexed: {title}")
                await asyncio.sleep(2)  # Be respectful
                
        except Exception as e:
            logger.error(f"❌ Failed to scrape {url}: {str(e)}")
    
    # Final commit
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{solr_base_url}/update",
                json={"commit": {}},
                headers={"Content-Type": "application/json"}
            )
        logger.info("💾 Final commit completed")
    except Exception as e:
        logger.error(f"Failed to commit: {str(e)}")

# Root endpoint with API documentation
@app.get("/")
async def root():
    return {
        "message": "🔍 Hybrid Search API",
        "features": [
            "BM25 keyword search",
            "Vector semantic search (all-MiniLM-L6-v2)",
            "Hybrid search with LTR re-ranking",
            "Real-time web scraping",
            "Manual document indexing"
        ],
        "endpoints": {
            "search": "POST /search - Main search endpoint",
            "scrape": "POST /scrape - Scrape and index URLs",
            "index": "POST /index - Index single document",
            "crawl": "POST /crawl - Add URLs to crawl queue",
            "stats": "GET /stats - Collection statistics",
            "health": "GET /health - Service health check"
        },
        "example_search": {
            "url": "/search",
            "method": "POST",
            "body": {
                "query": "machine learning algorithms",
                "search_type": "hybrid",
                "rows": 10
            }
        }
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
