## **Architecture Overview**

Hybrid search app with FastAPI as the query interface:

**Single Docker Container** that runs:

* ✅ **Solr** with vector search (384-dim, all-MiniLM-L6-v2)  
* ✅ **Redis** for URL queue management  
* ✅ **FastAPI** as the main API interface  
* ✅ **Background web scraping** with automatic vectorization  
* ✅ **Hybrid search** (BM25 \+ Vector \+ LTR)

## **🚀 Quick Start Process**

1. **Create project structure:**  

touch app/__init__.py

2. **Build and run:**  

*\# Build the container*

make build

*\# Start everything with sample data*

make setup

3. **Test the search:**  

*\# Automated tests*

make test-search  

* *\# OR*

*\# Interactive search*

make search

## **🔗 FastAPI Endpoints**

* **`POST /search`** \- Main search with 3 modes (BM25, vector, hybrid)  
* **`POST /scrape`** \- Add URLs to scrape and auto-index  
* **`POST /index`** \- Manually index documents  
* **`GET /stats`** \- Collection statistics  
* **`GET /health`** \- Service health check  
* **`GET /`** \- API documentation

  ## **🎁 Key Advantages**

 ✅ **Simple**: One container  
 ✅ **FastAPI Interface**: Clean REST API instead of direct Solr queries  
 ✅ **Automatic Setup**: `make setup` does everything  
 ✅ **Built-in Scraper**: No need for complex StormCrawler setup  
 ✅ **Real Embeddings**: Uses actual all-MiniLM-L6-v2 model  
 ✅ **Production Ready**: Includes health checks, logging, error handling

The FastAPI app handles all the complexity of communicating with Solr, generating embeddings, and managing the hybrid search logic. You just make simple HTTP requests to get powerful search results\!

* 


