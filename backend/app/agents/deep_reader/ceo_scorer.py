"""
Deep Reader Agent – CEO / Management Ambidexterity Scorer
=========================================================
Extracted and adapted from:
  github.com/srinix18/pdf-to-structured-reports
  →  metricsobjective/scripts/calculate_ceo_scores.py

Applies the Exploration & Exploitation keyword dictionaries
(McKenny, Aguinis, Short & Anglin, 2018 – Journal of Management 44, 2909-2933)
against any text block to produce a deterministic, fully explainable score.

No LLM involved.  Every keyword hit is traceable.
"""
import logging
import re
from typing import Dict, List, Tuple

logger = logging.getLogger(f"pramaan.{__name__}")

# ---------------------------------------------------------------------------
# Keyword Dictionaries  (source: McKenny et al., 2018)
# ---------------------------------------------------------------------------
EXPLORATION_DICTIONARY: List[str] = [
    "beta-phase", "beta-testing", "breakthrough", "breakthroughs",
    "clinical studies", "clinical study", "clinical test", "clinical testing",
    "clinical tests", "clinical trial", "clinical trials", "creative",
    "develop", "developed", "developing", "development", "developmental",
    "developments", "develops", "experiment", "experimental", "experimentalism",
    "experimentalist", "experimentalists", "experimentalize", "experimentally",
    "experimentarian", "experimentarians", "experimentation", "experimentations",
    "experimentative", "experimentator", "experimented", "experimenter",
    "experimenters", "experimenting", "experimentist", "experimentists",
    "experimentor", "experimentors", "experiments", "innovate", "innovated",
    "innovates", "innovating", "innovation", "innovations", "innovative",
    "innovativeness", "innovator", "innovators", "innovatory", "inventions",
    "IPR&D", "IPRD", "laboratories", "laboratory", "labs", "launch", "launched",
    "launches", "launching", "new drug", "new drugs", "new generic product",
    "new generic products", "new mobile product", "new mobile products",
    "new offering", "new offerings", "new product", "new products",
    "new program", "new programming", "new programs", "new system", "new systems",
    "new technologies", "new technology", "novel", "patent application",
    "patent applications", "patent development", "patent developments",
    "Phase 1", "Phase 1a", "Phase 1b", "Phase 2", "Phase 2a", "Phase 2b",
    "Phase 3", "Phase 4", "Phase I", "Phase I/II", "Phase Ia", "Phase IB",
    "Phase II", "Phase Iia", "Phase Iib", "Phase III", "Phase IV",
    "pioneer", "pioneered", "preclinical", "pre-clinical", "proof of concept",
    "prototype", "prototypes", "prototyping", "R&D", "research", "researching",
    "unveiled",
]

EXPLOITATION_DICTIONARY: List[str] = [
    "adaptations", "advertising", "commercialization", "commercialize",
    "commercialized", "commercializes", "commercializing", "commoditized",
    "commoditizing", "current offering", "current offerings", "current product",
    "current products", "efficience", "efficiencies", "efficiency", "efficient",
    "efficiently", "existing offering", "existing offerings", "existing product",
    "existing products", "existing technology", "exploit", "exploitability",
    "exploitable", "exploitation", "exploitational", "exploitationally",
    "exploitations", "exploitative", "exploitatively", "exploitatory",
    "exploited", "exploiting", "exploitive", "exploitively", "exploits",
    "exploiture", "extension", "extensions", "implement", "implementable",
    "implemental", "implementation", "implementations", "implemented",
    "implementer", "implementers", "implementing", "implementor",
    "implementors", "implements", "integrate", "integration", "maintenance",
    "manufacture", "manufactured", "manufacturing", "marketed", "marketing",
    "new features", "new formulation", "new formulations", "new indication",
    "new indications", "optimization", "optimize", "optimized", "optimizes",
    "optimizing", "optimum", "produce", "produced", "produces", "producing",
    "production", "productions", "productivity", "promotion", "promotional",
    "promotions", "redesign", "reengineering", "re-engineering", "refine",
    "refined", "refinedly", "refinedness", "refinement", "refinements",
    "refines", "refining", "reformulated", "reformulating", "reformulation",
    "refreshed", "re-launch", "replicated", "replication", "replicators",
    "retooled", "salesforce", "salespeople", "salespersons", "standardized",
    "streamline", "throughput", "upgrade", "upgraded", "upgrades", "upgrading",
    "version", "versions",
]


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------
def _preprocess(text: str) -> str:
    """Lowercase + normalise whitespace."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def _count_words(text: str) -> int:
    cleaned = re.sub(r"[^\w\s]", " ", text)
    return len(cleaned.split())


def _count_keywords(
    text: str, keywords: List[str]
) -> Tuple[int, Dict[str, int]]:
    """
    Count keyword occurrences using word-boundary regex.
    Returns (total_hits, {keyword: count, ...}) — only entries with count > 0.
    """
    preprocessed = _preprocess(text)
    detail: Dict[str, int] = {}
    total = 0

    for kw in keywords:
        pattern = r"\b" + re.escape(kw.lower()) + r"\b"
        hits = len(re.findall(pattern, preprocessed))
        if hits:
            detail[kw] = hits
            total += hits

    return total, detail


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def calculate_scores(text: str) -> Dict:
    """
    Calculate Exploration & Exploitation ambidexterity scores for any text chunk.

    Args:
        text: Raw text to analyse (typically the MD&A section of an annual report)

    Returns:
        {
          "total_words": int,
          "exploration_frequency": int,
          "exploration_score": float,
          "exploitation_frequency": int,
          "exploitation_score": float,
          "ambidexterity_score": float,
          "exploration_exploitation_ratio": float | "N/A",
          "top_exploration_keywords": {kw: count, ...},   # top-10
          "top_exploitation_keywords": {kw: count, ...},  # top-10
        }
    """
    if not text or not text.strip():
        logger.warning("calculate_scores received empty text")
        return {
            "total_words": 0,
            "exploration_frequency": 0,
            "exploration_score": 0.0,
            "exploitation_frequency": 0,
            "exploitation_score": 0.0,
            "ambidexterity_score": 0.0,
            "exploration_exploitation_ratio": "N/A",
            "top_exploration_keywords": {},
            "top_exploitation_keywords": {},
        }

    total_words = _count_words(text)
    logger.info(f"Scoring text: {total_words:,} words")

    expl_freq, expl_detail = _count_keywords(text, EXPLORATION_DICTIONARY)
    exploit_freq, exploit_detail = _count_keywords(text, EXPLOITATION_DICTIONARY)

    expl_score = expl_freq / total_words if total_words else 0.0
    exploit_score = exploit_freq / total_words if total_words else 0.0
    ambidexterity = (expl_freq + exploit_freq) / total_words if total_words else 0.0

    if exploit_freq > 0:
        ratio: float | str = round(expl_freq / exploit_freq, 4)
    elif expl_freq > 0:
        ratio = "∞ (exploitation=0)"
    else:
        ratio = "N/A"

    # Top-10 keywords for transparency
    top_expl = dict(sorted(expl_detail.items(), key=lambda x: x[1], reverse=True)[:10])
    top_exploit = dict(sorted(exploit_detail.items(), key=lambda x: x[1], reverse=True)[:10])

    logger.info(
        f"Scores — exploration={expl_score:.6f}, exploitation={exploit_score:.6f}, "
        f"ambidexterity={ambidexterity:.6f}, ratio={ratio}"
    )

    return {
        "total_words": total_words,
        "exploration_frequency": expl_freq,
        "exploration_score": round(expl_score, 6),
        "exploitation_frequency": exploit_freq,
        "exploitation_score": round(exploit_score, 6),
        "ambidexterity_score": round(ambidexterity, 6),
        "exploration_exploitation_ratio": ratio,
        "top_exploration_keywords": top_expl,
        "top_exploitation_keywords": top_exploit,
    }
