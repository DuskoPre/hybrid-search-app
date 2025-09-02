## **Architecture Overview**

Hybrid search app with FastAPI as the query interface:

**Single Docker Container** that runs:

* ✅ **Solr** with vector search (384-dim, all-MiniLM-L6-v2)  
* ✅ **Redis** for URL queue management  
* ✅ **FastAPI** as the main API interface  
* ✅ **Background web scraping** with automatic vectorization  
* ✅ **Hybrid search** (BM25 \+ Vector \+ LTR)
