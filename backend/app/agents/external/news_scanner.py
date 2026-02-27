import logging
import requests

logger = logging.getLogger(__name__)

class NewsScanner:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://newsapi.org/v2/everything"
    
    async def scan(self, entity_name: str) -> dict:
        logger.info(f"NewsScanner searching: '{entity_name}'")
        
        # Search for entity name + red flag keywords
        query = f'"{entity_name}" AND (fraud OR default OR insolvency OR "ED raid" OR NCLT OR "cheque bounce" OR RBI OR SEBI)'
        
        response = requests.get(self.base_url, params={
            "q": query,
            "apiKey": self.api_key,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 10
        })
        
        articles = response.json().get("articles", [])
        
        # Score each article for severity
        red_flags = []
        for article in articles:
            headline = article.get("title", "")
            severity = "HIGH" if any(w in headline.lower() for w in ["fraud", "ed raid", "arrested", "default"]) else "MEDIUM"
            red_flags.append({
                "headline": headline,
                "source": article["source"]["name"],
                "published": article["publishedAt"][:10],
                "url": article["url"],
                "severity": severity
            })
            
        logger.info(f"NewsScanner: {len(articles)} articles, {len(red_flags)} red flags")
        
        return {
            "entity": entity_name,
            "articles_found": len(articles),
            "red_flags": red_flags,
            "adverse_media_detected": len(red_flags) > 0
        }
