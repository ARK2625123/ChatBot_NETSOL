# app/search/tavily_search.py
import os
from typing import List, Dict, Optional
from tavily import TavilyClient
from dotenv import load_dotenv

load_dotenv()

class TavilySearcher:
    def __init__(self):
        self.api_key = os.getenv("TAVILY_API_KEY")
        if not self.api_key:
            print("Warning: TAVILY_API_KEY not found. Web search will be disabled.")
            self.client = None
        else:
            self.client = TavilyClient(api_key=self.api_key)
    
    def search(self, query: str, max_results: int = 5) -> List[Dict]:
        """
        Search the web using Tavily
        
        Returns list of search results with title, content, url
        """
        if not self.client:
            return []
        
        try:
            response = self.client.search(
                query=query,
                search_depth="advanced",
                max_results=max_results,
                include_raw_content=False
            )
            
            results = []
            for result in response.get("results", []):
                results.append({
                    "title": result.get("title", ""),
                    "content": result.get("content", ""),
                    "url": result.get("url", ""),
                    "score": result.get("score", 0.0)
                })
            
            return results
            
        except Exception as e:
            print(f"Tavily search error: {e}")
            return []
    
    def is_available(self) -> bool:
        """Check if Tavily search is available"""
        return self.client is not None

# Global instance
tavily_searcher = TavilySearcher()