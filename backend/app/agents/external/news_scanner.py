import logging
import requests
from fastapi.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

class NewsScanner:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://newsapi.org/v2/everything"
    
    async def scan(self, entity_name: str) -> dict:
        # Strip "Limited", "Ltd", "Private" etc for better search matching
        search_name = entity_name.replace("Limited", "").replace("Ltd", "").replace("Private", "").strip()
        logger.info(f"NewsScanner searching: '{search_name}'")
        
        # Search for entity name + red flag keywords
        query = f'"{search_name}" AND (fraud OR default OR "ED raid" OR SFIO OR insolvency OR NPA OR "loan default" OR bankruptcy OR scam OR "money laundering")'
        
        response = await run_in_threadpool(
            requests.get,
            self.base_url, 
            params={
                "q": query,
                "apiKey": self.api_key,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": 10
            }
        )
        
        articles = response.json().get("articles", [])
        
        # Score each article for severity
        red_flags = []
        for article in articles:
            headline = article.get("title", "") or ""
            
            severity = "HIGH" if any(w in headline.lower() 
                       for w in ["fraud", "ed raid", "arrested", 
                       "default", "insolvency", "NCLT"]) else "MEDIUM"
            
            # Fix date parsing
            published = article.get("publishedAt", "")
            
            red_flags.append({
                "headline": headline,
                "source": article["source"]["name"],
                "published": published,
                "url": article["url"],
                "severity": severity
            })
            
        triggered_rules = []
        if len(red_flags) > 0:
            triggered_rules.append("P-13")
            
        logger.info(f"NewsScanner: {len(articles)} articles, {len(red_flags)} red flags, triggered_rules={triggered_rules}")
        
        return {
            "entity": entity_name,
            "articles_found": len(articles),
            "red_flags": red_flags,
            "adverse_media_detected": len(red_flags) > 0,
            "triggered_rules": triggered_rules
        }
