import requests, re, logging
from dataclasses import dataclass, field
from typing import List
from app.core.config import settings

logger = logging.getLogger(f"pramaan.{__name__}")

@dataclass
class MCAResult:
    company_name: str = ""
    cin: str = ""
    company_status: str = "Unknown"
    date_of_incorporation: str = ""
    registered_state: str = ""
    directors: List[dict] = field(default_factory=list)
    total_charges_cr: float = 0.0
    charge_holders: List[str] = field(default_factory=list)
    is_struck_off: bool = False
    triggered_rules: List[str] = field(default_factory=list)
    findings: List[dict] = field(default_factory=list)
    registered_address: str = ""
    business_activity: str = ""
    paid_up_capital: float = 0.0
    source: str = "MCA21"

class MCAScanner:
    
    def extract_cin_from_text(self, text: str) -> str:
        pattern = r'[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}'
        match = re.search(pattern, text)
        if match:
            logger.info(f"MCAScanner: CIN extracted = {match.group()}")
            return match.group()
        return ""
    
    def lookup_by_cin(self, cin: str) -> MCAResult:
        result = MCAResult(cin=cin)
        try:
            api_key = settings.DATA_GOV_API_KEY
            url = "https://api.data.gov.in/resource/ec58dab7-d891-4abb-936e-d5d274a6ce9b"
            params = {
                "api-key": api_key,
                "format": "json",
                "limit": 1,
                "filters[corporate_identification_number]": cin.strip().upper()
            }
            
            response = requests.get(url, params=params, timeout=10)
            logger.info(f"MCAScanner data.gov.in: HTTP {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                records = data.get("records", [])
                
                if records:
                    rec = records[0]
                    logger.info(f"MCAScanner raw record: {rec}")
                    
                    result.company_name = rec.get("company_name", "")
                    result.company_status = rec.get("company_status", "Unknown")
                    result.date_of_incorporation = rec.get("date_of_registration", "")
                    result.registered_state = rec.get("registered_state", "")
                    result.registered_address = rec.get("registered_office_address", "")
                    result.business_activity = rec.get("principal_business_activity", "")
                    
                    # Convert paid up capital
                    try:
                        result.paid_up_capital = float(rec.get("paidup_capital", 0))
                    except (ValueError, TypeError):
                        result.paid_up_capital = 0.0
                        
                    if "strike" in result.company_status.lower() or "struck" in result.company_status.lower() or "liquidation" in result.company_status.lower():
                        result.is_struck_off = True
                        if "P-14" not in result.triggered_rules:
                            result.triggered_rules.append("P-14")
                            result.findings.append({
                                "signal": f"Company struck off: {result.company_status}",
                                "severity": "CRITICAL"
                            })
                    
                    result.source = "data.gov.in — MCA Company Master (4M records)"
                    logger.info(
                        f"MCAScanner: {result.company_name} | "
                        f"{result.company_status} | "
                        f"{result.registered_state}")
                else:
                    logger.warning(f"MCAScanner: No records found for {cin}")
            else:
                logger.error(f"MCAScanner: {response.text[:300]}")
        except Exception as e:
            logger.error(f"MCAScanner failed: {e}")
        
        return result
    
    def _fallback_scrape(self, cin: str, result: MCAResult) -> MCAResult:
        try:
            url = "https://www.mca.gov.in/mcafoportal/viewCompanyMasterData.do"
            response = requests.post(url,
                data={"companyID": cin},
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            text = response.text
            
            name_match = re.search(
                r'Company Name.*?<td[^>]*>(.*?)</td>', text, re.DOTALL)
            if name_match:
                result.company_name = name_match.group(1).strip()
            
            status_match = re.search(
                r'Company Status.*?<td[^>]*>(.*?)</td>', text, re.DOTALL)
            if status_match:
                result.company_status = status_match.group(1).strip()
                
            state_match = re.search(
                r'State.*?<td[^>]*>(.*?)</td>', text, re.DOTALL)
            if state_match:
                result.registered_state = state_match.group(1).strip()
                
            if "strike" in result.company_status.lower() or "struck" in result.company_status.lower() or "liquidation" in result.company_status.lower():
                result.is_struck_off = True
                if "P-14" not in result.triggered_rules:
                    result.triggered_rules.append("P-14")
                    result.findings.append({
                        "signal": f"Company struck off: {result.company_status}",
                        "severity": "CRITICAL"
                    })
            
            logger.info(f"MCAScanner fallback: {result.company_name} | {result.company_status}")
        except Exception as e:
            logger.error(f"MCAScanner fallback failed: {e}")
        return result
    
    def scan(self, text: str, entity_name: str = "") -> MCAResult:
        cin = self.extract_cin_from_text(text)
        
        if cin:
            result = self.lookup_by_cin(cin)
            return result
        else:
            logger.warning(f"MCAScanner: No CIN found for '{entity_name}'")
            return MCAResult(
                company_name=entity_name,
                company_status="CIN not found in document",
                source="MCA21 — CIN extraction failed"
            )
