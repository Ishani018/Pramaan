"""
MD&A NLP Analyzer — Zero LLM
Uses Loughran-McDonald Financial Sentiment Dictionary
for deterministic, explainable sentiment scoring.
"""
import logging
import re
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

FINANCIAL_NEGATIVE = [
    "abandon", "abandoned", "adverse", "adversely", "bankrupt",
    "bankruptcy", "breach", "cancellation", "ceased", "collapse",
    "conflict", "contraction", "crisis", "damage", "decay",
    "decline", "declining", "default", "defect", "deficit",
    "delinquent", "depressed", "deteriorate", "deterioration",
    "disappointing", "disruption", "disruptions", "distress",
    "downsize", "downturn", "drop", "erosion", "fail", "failure",
    "fraud", "headwind", "headwinds", "impairment", "investigation",
    "litigation", "loss", "losses", "negative", "penalty",
    "recession", "regulation", "regulatory", "restructuring",
    "severe", "shortfall", "sluggish", "suffer", "suspend",
    "threat", "weakness", "write-off", "writeoff", "winding",
    "insolvency", "insolvent", "npa", "overdue", "unpaid",
    "delinquency", "stressed", "under-recovery", "underperform"
]

FINANCIAL_POSITIVE = [
    "achieve", "achieved", "achievement", "advantage", "beneficial",
    "benefit", "boom", "boost", "breakthrough", "capable",
    "confident", "efficiency", "efficient", "empower", "enable",
    "excellent", "exceptional", "expansion", "favorable", "gain",
    "gains", "growth", "improve", "improvement", "improving",
    "innovation", "innovative", "leadership", "momentum",
    "opportunity", "optimistic", "outperform", "outperformed",
    "profitable", "progress", "prosperity", "rebound", "recovery",
    "resolve", "reward", "stable", "strength", "strengthen",
    "strong", "success", "successful", "surge", "synergy",
    "upturn", "valuable", "robust", "resilient", "sustainable"
]

UNCERTAINTY = [
    "ambiguous", "anticipate", "approximately", "assume", "assumes",
    "assumption", "believe", "believes", "caution", "cautious",
    "could", "depend", "dependence", "doubt", "doubtful",
    "fluctuate", "fluctuating", "fluctuation", "imprecise",
    "incomplete", "indefinite", "likely", "may", "might",
    "nearly", "pending", "perhaps", "possible", "possibly",
    "predict", "preliminary", "probable", "probably", "random",
    "risk", "risks", "roughly", "sometimes", "somewhat",
    "speculate", "speculation", "subject to", "suppose",
    "tentative", "uncertain", "uncertainties", "uncertainty",
    "unclear", "unconfirmed", "unexpected", "unforeseen",
    "unknown", "unpredictable", "unproven", "unsettled",
    "unusual", "variable", "volatile", "volatility"
]

HEADWIND_MARKERS = [
    "headwind", "regulation", "disruption", "inflation",
    "supply chain", "decline", "threat", "challenge", "risk",
    "pressure", "adversely", "uncertainty", "competition",
    "slowdown", "downturn", "stressed", "agr", "dues",
    "spectrum", "debt", "borrowing", "default", "npa"
]

class MDAAnalyzer:

    def _preprocess(self, text: str) -> str:
        text = text.lower()
        return re.sub(r'\s+', ' ', text)

    def _count_words(self, text: str) -> int:
        cleaned = re.sub(r'[^\w\s]', ' ', text)
        return len(cleaned.split())

    def _get_frequencies(self, text: str, keywords: List[str]) -> int:
        count = 0
        for kw in keywords:
            pattern = r'\b' + re.escape(kw) + r'\b'
            count += len(re.findall(pattern, text))
        return count

    def _extract_headwind_sentences(
        self, raw_text: str, max_sentences: int = 6) -> List[str]:
        sentences = re.split(r'(?<=[.!?])\s+', raw_text)
        results = []
        for sentence in sentences:
            s_lower = sentence.lower()
            if (any(m in s_lower for m in HEADWIND_MARKERS)
                    and len(sentence) > 40):
                clean = re.sub(r'\s+', ' ', sentence).strip()
                results.append(clean)
                if len(results) >= max_sentences:
                    break
        return results

    def analyze(self, mda_text: str) -> Dict[str, Any]:
        if not mda_text or len(mda_text.strip()) < 100:
            return {
                "status": "insufficient_text",
                "sentiment_score": 0.0,
                "risk_intensity": 0.0,
                "extracted_headwinds": [],
                "metrics": {}
            }

        preprocessed = self._preprocess(mda_text)
        total_words = self._count_words(preprocessed)

        if total_words == 0:
            return {"status": "error"}

        neg_freq = self._get_frequencies(preprocessed, FINANCIAL_NEGATIVE)
        pos_freq = self._get_frequencies(preprocessed, FINANCIAL_POSITIVE)
        unc_freq = self._get_frequencies(preprocessed, UNCERTAINTY)

        sentiment_score = (pos_freq - neg_freq) / total_words
        risk_intensity = (neg_freq + unc_freq) / total_words

        headwinds = self._extract_headwind_sentences(mda_text)

        logger.info(
            f"MDAAnalyzer: words={total_words}, "
            f"sentiment={sentiment_score:.4f}, "
            f"risk={risk_intensity:.4f}, "
            f"headwinds={len(headwinds)}")

        return {
            "status": "success",
            "sentiment_score": round(sentiment_score, 4),
            "risk_intensity": round(risk_intensity, 4),
            "extracted_headwinds": headwinds,
            "metrics": {
                "total_words": total_words,
                "negative_words": neg_freq,
                "positive_words": pos_freq,
                "uncertainty_words": unc_freq
            },
            "methodology": "Loughran-McDonald Financial Sentiment Dictionary"
        }
