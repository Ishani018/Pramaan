import logging
import requests
from dataclasses import dataclass, field
from typing import List, Dict, Any
from fastapi.concurrency import run_in_threadpool

logger = logging.getLogger(f"pramaan.{__name__}")

@dataclass
class NewsResult:
    entity: str = ""
    articles_found: int = 0
    red_flag_count: int = 0
    articles: List[Dict[str, Any]] = field(default_factory=list)
    adverse_media_detected: bool = False
    triggered_rules: List[str] = field(default_factory=list)

class NewsScanner:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://newsapi.org/v2/everything"
    
    async def scan(self, entity_name: str) -> NewsResult:
        # Strip "Limited", "Ltd", "Private" etc for better search matching
        search_name = entity_name.replace("Limited", "").replace("Ltd", "").replace("Private", "").strip()
        logger.info(f"NewsScanner searching: '{search_name}'")
        
        # Search for entity name + red flag keywords
        query = f'"{search_name}" AND (fraud OR default OR "ED raid" OR SFIO OR insolvency OR NPA OR "loan default" OR bankruptcy OR scam OR "money laundering")'
        
        try:
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
            data = response.json()
            raw_articles = data.get("articles", [])
        except Exception as e:
            logger.error(f"NewsScanner API call failed: {e}")
            raw_articles = []
        
        # Score each article for severity
        red_flags = []
        for article in raw_articles:
            headline = article.get("title", "") or ""
            
            severity = "HIGH" if any(w in headline.lower() 
                       for w in ["fraud", "ed raid", "arrested", 
                       "default", "insolvency", "NCLT"]) else "MEDIUM"
            
            red_flags.append({
                "headline": headline,
                "source": article.get("source", {}).get("name", "Unknown"),
                "published": article.get("publishedAt", ""),
                "url": article.get("url", ""),
                "severity": severity
            })
            
        triggered_rules = []
        if len(red_flags) > 0:
            triggered_rules.append("P-13")
            
        logger.info(f"NewsScanner: {len(raw_articles)} articles, {len(red_flags)} red flags, triggered_rules={triggered_rules}")
        
        return NewsResult(
            entity=entity_name,
            articles_found=len(raw_articles),
            red_flag_count=len(red_flags),
            articles=red_flags,
            adverse_media_detected=len(red_flags) > 0,
            triggered_rules=triggered_rules
        )
