## **Architecture Overview**

Hybrid search app with FastAPI as the query interface:

**Docker Compose** that runs:

* ✅ **Solr** with vector search (384-dim, all-MiniLM-L6-v2) in a separate container  
* ✅ **Redis** for URL queue management in a separate container  
* ✅ **FastAPI** as the main API interface in its own container  
* ✅ **Background web scraping** with automatic vectorization  
* ✅ **Hybrid search** (BM25 \+ Vector \+ LTR)

## **🚀 Quick Start Process**

1. **Create project structure:**  

touch app/__init__.py

2. **Build and run:**  

*\# Build the containers*

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

 ✅ **Modular**: Separate containers for each service  
 ✅ **FastAPI Interface**: Clean REST API instead of direct Solr queries  
 ✅ **Automatic Setup**: `make setup` does everything  
 ✅ **Built-in Scraper**: No need for complex StormCrawler setup  
 ✅ **Real Embeddings**: Uses actual all-MiniLM-L6-v2 model  
 ✅ **Production Ready**: Includes health checks, logging, error handling

The FastAPI app handles all the complexity of communicating with Solr, generating embeddings, and managing the hybrid search logic. You just make simple HTTP requests to get powerful search results\!

* 
The FastAPI application triggers Solr's re-ranking features, but \_\_only when the \`search\_type\` is set to \`"hybrid"\`\_\_.

Here's a breakdown of how it works:

1\. The main \`/search\` endpoint calls different functions based on the \`search\_type\` parameter.

2\. When \`search\_type\` is \`"hybrid"\`, it calls the \`hybrid\_search\` function.

3\. Inside \`hybrid\_search\`, the request to Solr includes a specific re-ranking parameter \`rq\`:

\`\`\`python

async def hybrid\_search(client: httpx.AsyncClient, request: SearchRequest) \-\> List\[SearchResult\]:

    """Hybrid search with LTR re-ranking"""

    params \= {

        "q": request.query,

        "defType": "edismax",

        "qf": "title^3 content",

        "rq": f"{{\!ltr model=enhanced\_hybrid\_ranker reRankDocs={request.rerank\_docs}}}",

        "rows": request.rows,

        "fl": "id,title,url,content,score,\[features\]"

    }

    \# ...

\`\`\`

The key part is \`"rq": f"{{\!ltr model=enhanced\_hybrid\_ranker ...}}"\`. The \`rq\` parameter tells Solr to execute a subsequent re-ranking query on the initial results. In this case, it uses the Learning to Rank (\`ltr\`) model named \`enhanced\_hybrid\_ranker\`.

The other search types, \`bm25\` and \`vector\`, do \_\_not\_\_ include this \`rq\` parameter, so they return the results directly from their respective search algorithms without a re-ranking step.

*
