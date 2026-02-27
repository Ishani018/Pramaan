# 🏦 Project Pramaan — `प्रमाण`

> **"Proof"** — *n.* evidence that compels belief; demonstration beyond doubt.

**Project Pramaan is a next-generation, deterministic corporate credit decisioning engine built for the Indian lending landscape. It automates the most time-consuming and error-prone parts of a credit analyst's workflow — without a single AI hallucination.**

---

## Table of Contents

1. [The Problem](#-the-problem)
2. [The Problem Statement](#-the-problem-statement)
3. [The Insight — Why Determinism Wins](#-the-insight--why-determinism-wins)
4. [What We Built](#-what-we-built)
5. [System Architecture](#-system-architecture)
6. [The Credit Committee Pipeline](#-the-credit-committee-pipeline)
7. [The Rule Engine](#-the-rule-engine-penalty-accumulator)
8. [Backend — Deep Dive](#-backend--deep-dive)
9. [Web Sleuth Agent](#-web-sleuth-agent--adverse-media-scanner)
10. [ML Baseline Model](#-ml-baseline-model--rate--limit-predictor)
11. [CEO Ambidexterity Scorer](#-ceo-ambidexterity-scorer)
12. [Network Analysis](#-network-analysis--circular-trading-detection)
13. [Frontend — Deep Dive](#-frontend--deep-dive)
14. [The CAM Generator](#-the-cam-generator)
15. [API Reference](#-api-reference)
16. [Getting Started](#-getting-started)
17. [Project Structure](#-project-structure)
18. [Design Decisions](#-key-design-decisions)
19. [Roadmap](#-roadmap)

---

## 🔴 The Problem

### Credit Appraisal in India Is Broken

Every year, Indian banks and NBFCs lose thousands of crores to credit defaults that were — in hindsight — **entirely predictable**. The warning signs were always there. They were buried in documents.

A mid-market corporate loan appraisal in India today looks like this:

1. **A Relationship Manager (RM)** receives a 200-400 page Annual Report PDF from the borrower.
2. The RM manually reads through the Independent Auditor's Report, the MD&A, and the Notes to Financials — looking for red flags.
3. A Credit Analyst checks the GST reconciliation (GSTR-2A vs 3B) by hand, looking for invoice mismatches that could signal ghost input tax credit fraud.
4. The Legal team runs litigation checks through MCA/Karza portals, manually.
5. All of this raw information is then typed up into a **Credit Appraisal Memo (CAM)** — a Word document — by hand. Copying and pasting from PDFs, bureau reports, and spreadsheets.
6. The CAM goes to a Credit Committee, which makes a sanction decision on rate and limit.

**This process takes 5–15 business days per case.** It is:

| Pain Point | Real-World Cost |
|---|---|
| Entirely manual | Senior analyst time: 3–5 days per appraisal |
| Error-prone | Copy-paste mistakes, missed clauses, overlooked qualifications |
| Inconsistent | Two analysts reading the same report reach different conclusions |
| Unscalable | Loan books grow, headcount stays flat — quality degrades |
| Audit-unfriendly | No traceable, verifiable link between the source document and the decision |

### The Specific Risks That Get Missed

Three categories of risk are disproportionately missed in manual appraisals:

#### 1. CARO 2020 Statutory Defaults — The Silent Killer
The **Companies (Auditor's Report) Order, 2020** mandates that auditors report on whether a company has defaulted on statutory dues — Provident Fund, ESI, TDS, GST, Customs duties. These defaults under **Clause (vii)** are a direct indicator of cash-flow stress and regulatory non-compliance. They appear in the Annexure to the Auditor's Report, often buried in dense legal prose. Analysts routinely miss them.

#### 2. Auditor Qualifications — The Red Flag in Plain Sight
A **qualified opinion** ("Except for the matter described…"), an **adverse opinion**, or a **Disclaimer of Opinion** is a screaming fire alarm from the borrowing company's own auditors. Yet analysts under time pressure often misread or skip past the Opinion paragraph entirely. An unqualified report gets the same treatment as a qualified one.

#### 3. GST Reconciliation Fraud — The Ghost Input Trap
A company's GSTR-2A (what its suppliers filed) vs GSTR-3B (what it self-declared) should match. A **mismatch above 15%** is a strong indicator of inflated input tax credit claims — essentially ghost invoices that inflate apparent profitability. This data lives in the Perfios / GST bureau, not in the annual report, and is never cross-checked systematically.

---

## 📋 The Problem Statement

> **Design and implement a credit decisioning system that can automatically extract and verify the three highest-signal risk factors from a corporate borrower's audit ecosystem, produce a verifiable, rule-based penalty calculation, and generate a complete Credit Appraisal Memo — eliminating 3 days of analyst drudgery from every credit case, with zero risk of hallucination.**

### Constraints
- **Zero LLM calls in the decisioning chain.** Every finding must be traceable to a character offset in the original document or a field in the bureau API response.
- **Every penalty must be derived from an explicit, auditable rule.** No black-box scoring. A credit committee must be able to reproduce any decision by hand.
- **The CAM document must be machine-generated but human-readable.** It must follow the Five Cs of Credit framework used by every credit professional in India.
- **The system must degrade gracefully.** If a section isn't found, it says so. If bureau data isn't available, base decisions still hold. No silent failures.

---

## 💡 The Insight — Why Determinism Wins

Most "AI credit" products fail in production because banks can't explain their decisions to regulators or credit committees. **Explainability is not optional — it is a regulatory requirement under RBI's Fair Practices Code.**

The insight behind Pramaan is that the **highest-value signals in a credit file are deterministic by nature:**

- A CARO clause is a fixed legal phrase. It either appears or it doesn't.
- "Except for" is a qualification. It either appears or it doesn't.
- A GST mismatch is a number. It's either above 15% or it isn't.

**We don't need AI to find these. We need a fast, reliable machine that never gets tired, never misses a page, and always cites its sources.**

LLMs are reserved exclusively for tasks where interpretation is genuinely ambiguous — and in our current implementation, we've found zero such tasks in the mandatory credit signal extraction chain.

---

## 🛠 What We Built

Project Pramaan is a full-stack **Credit Committee Engine** consisting of:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           PROJECT PRAMAAN                               │
│                      Intelli-Credit Engine                              │
├────────────────────────────────┬─────────────────────────────────────────┤
│   BACKEND (Python/FastAPI)     │    FRONTEND (React/Vite)               │
│                                │                                        │
│  📄 Deep Reader Agent          │  📊 Compliance Scan Tab                │
│     Section Boundary Detector  │     (Boolean flags + evidence)         │
│     Compliance Scanner (Regex) │                                        │
│     CEO Ambidexterity Scorer   │  📈 Rate Waterfall Tab                 │
│     Gemini Extractor           │     (Live penalty cascade chart)       │
│                                │                                        │
│  🌐 External Intelligence      │  🗺 Compliance Evidence Grid           │
│     Perfios GST Recon (Mock)   │     (One cell per regex match)         │
│     Karza Litigation KYB (Mock)│                                        │
│     Network Graph (Mock)       │  🕸 Network Analysis Tab               │
│                                │     (Force-directed fraud graph)       │
│  🌍 Web Sleuth Agent           │                                        │
│     Adverse Media Scanner      │  🎯 ML Score Panel                     │
│     Weighted Keyword Scoring   │     (RF model confidence gauge)        │
│                                │                                        │
│  🧠 Orchestrator               │  📝 Site Visit Notes                   │
│     Penalty Accumulator        │                                        │
│     P-01 → P-06 Rule Engine    │  ⬇  Download CAM (Word)               │
│                                │                                        │
│  🤖 ML Baseline Model          │  Rule Engine footer strip              │
│     RandomForest Regressor     │     (P-01 → P-06 live badges)          │
│     Synthetic Training Data    │                                        │
│                                │                                        │
│  📑 CAM Generator              │                                        │
│     python-docx Five Cs        │                                        │
└────────────────────────────────┴─────────────────────────────────────────┘
```

---

## 🏗 System Architecture

### High-Level Flow

```
                         CREDIT COMMITTEE ENGINE

  ┌──────────────┐    POST /analyze-report
  │  Annual      │──────────────────────────────────────────────┐
  │  Report PDF  │                                              │
  └──────────────┘                                              ▼
                                                   ┌─────────────────────┐
  ┌──────────────┐    GET /mock/perfios             │ SectionBoundary     │
  │  Perfios     │──────────────┐                  │ Detector            │
  │  GST Bureau  │              │                  │ (pdfplumber)        │
  └──────────────┘              │                  └─────────┬───────────┘
                                │                            │
  ┌──────────────┐    GET /mock/karza               ┌────────▼───────────┐
  │  Karza       │──────────────┐                  │ ComplianceScanner  │
  │  Litigation  │              │                  │ (regex / zero-LLM) │
  └──────────────┘              │                  └─────────┬───────────┘
                                │                            │
  ┌──────────────┐    GET /mock/network-graph        ┌───────▼───────────┐
  │  Network     │──────────────┐                  │ CEO Ambidexterity │
  │  Intelligence│              │                  │ Scorer            │
  └──────────────┘              │                  └─────────┬──────────┘
                                │                            │
  ┌──────────────┐              │                  ┌─────────▼───────────┐
  │  Web Sleuth  │──────────────┤                  │  ML Baseline Model  │
  │  (Crawl)     │              │                  │  (RandomForest)     │
  └──────────────┘              │                  └─────────┬───────────┘
                                │                            │
                                │                  ┌─────────▼───────────┐
                                │                  │  Orchestrator       │
                                └──────────────────►  Penalty Accumulator│
                                                   └─────────┬───────────┘
                                                             │
                                                   ┌─────────▼───────────┐
                                                   │  Unified Decision   │
                                                   │  rate, limit, reco  │
                                                   └─────────┬───────────┘
                                                             │
                                                   ┌─────────▼───────────┐
                                                   │  CAM Generator      │
                                                   │  (python-docx)      │
                                                   └─────────────────────┘
```

### Component-Level Architecture

```
backend/
├── app/
│   ├── agents/
│   │   ├── deep_reader/
│   │   │   ├── section_boundary_detector.py   ← PDF section locator (font heuristics)
│   │   │   ├── section_hierarchy_builder.py   ← Nested section tree builder
│   │   │   ├── compliance_scanner.py          ← Zero-LLM regex risk signal finder
│   │   │   ├── ceo_scorer.py                  ← Management ambidexterity scorer
│   │   │   └── gemini_extractor.py            ← LLM-based structured extraction
│   │   ├── web_sleuth.py                      ← Adverse media web crawler
│   │   ├── ml_baseline.py                     ← RandomForest rate/limit predictor
│   │   └── orchestrator.py                    ← Penalty rule engine (P-01 → P-06)
│   ├── api/
│   │   └── v1/
│   │       ├── analyze_report.py              ← Deep Reader endpoint
│   │       ├── external_mocks.py              ← Perfios + Karza + Network Graph mocks
│   │       ├── export_cam.py                  ← CAM download endpoint
│   │       └── router.py                      ← Route aggregator
│   └── utils/
│       └── cam_generator.py                   ← Word document builder (Five Cs)
├── models/
│   └── ml_baseline.joblib                     ← Persisted ML model weights
└── main.py                                    ← FastAPI app factory
```

---

## 🔄 The Credit Committee Pipeline

When a credit officer clicks **"Run Full Credit Committee"**, this is exactly what happens — in parallel:

### Step 1 — Deep Reader (`POST /api/v1/analyze-report`)

```
PDF Binary
    │
    ▼
SectionBoundaryDetector
    │
    ├── Scans every page for heading-level text
    ├── Matches against SECTION_CONFIGS (font-size heuristics + keyword matching)
    ├── Locates: "Independent Auditor's Report" (start page → end page)
    └── Locates: "Annexure to the Independent Auditor's Report" (CARO section)
    │
    ▼
extract_section_text(boundary)  ←  pdfplumber text extraction
    │
    ▼
ComplianceScanner.scan(auditor_text, annexure_text)
    │
    ├── CARO_PATTERNS      → regex for "CARO 2020" near "Clause (vii)" or "default in payment"
    ├── QUALIFICATION_PATTERNS → regex for "Except for", "Adverse opinion", "Qualified opinion"
    └── EMPHASIS_PATTERNS  → regex for "Emphasis of Matter", "Going Concern"
    │
    ▼
Returns:
  {
    caro_default_found:       true/false,
    adverse_opinion_found:    true/false,
    emphasis_of_matter_found: true/false,
    caro_findings:            [ { pattern, snippet } ],   ← char-offset-cited
    auditor_qualification_findings: [ ... ],
    triggered_rules:          ["P-03"]
  }
```

### Step 2 — Perfios GST Bureau (`GET /api/v1/mock/perfios`)

```
Returns:
  {
    gstr_2a_3b_mismatch_pct: 18.5,    ← > 15% → P-01 Ghost Input Trap
    circular_trading_flag:   false,
    itc_reversal_required:   true,
    itc_reversal_amount_lakh: 12.4
  }
```

In production: this calls the live Perfios Reconciliation API with the borrower's GSTIN.

### Step 3 — Karza Litigation & KYB (`GET /api/v1/mock/karza`)

```
Returns:
  {
    active_litigations: ["Section 138 NI Act – Cheque Bounce – Pending at JMFC Mumbai"],
    director_disqualified: false,
    mca_charge_registered: true,
    charge_amount_cr: 7.0,
    charge_holders: ["HDFC Bank Ltd"]
  }
```

In production: this calls Karza's Entity Search + Director KYB APIs.

### Step 4 — Orchestrator (Penalty Accumulation)

The penalty accumulator runs on both backend and frontend (the client-side mirror ensures the Waterfall Chart is always live without a round-trip):

```python
BASE_RATE  = 9.0%      # Repo Rate + Bank Spread
BASE_LIMIT = ₹10.0 Cr  # Hypothetical unsecured working capital facility

Rule P-01 triggered? [Perfios mismatch 18.5% > 15%]
  → Rate  += 100 bps  →  9.0 + 1.0 = 10.0%
  → Limit  -= 10%     →  10.0 - 1.0 = ₹9.0 Cr

Rule P-03 triggered? [CARO default found OR auditor qualified]
  → Rate  += 150 bps  →  10.0 + 1.5 = 11.5%
  → Limit  -= 20%     →  9.0 - 1.8 = ₹7.2 Cr

Final: Rate 11.5% p.a. | Limit ₹7.2 Cr | CONDITIONAL_APPROVAL
```

---

## ⚖ The Rule Engine — Penalty Accumulator

All rules live in a single source of truth in `app/agents/orchestrator.py`:

| Rule ID | Name | Trigger | Rate Penalty | Limit Cut | Manual Review? |
|---|---|---|---|---|---|
| **P-01** | Ghost Input Trap | GSTR-2A vs 3B mismatch > 15% (Perfios) | +100 bps | −10% | No |
| **P-02** | Hidden Family Web | RPT outflows to director-connected entities | +75 bps | −10% | **Yes** |
| **P-03** | Statutory Default | CARO 2020 Clause (vii) or Auditor Qualification (PDF scan) | +150 bps | −20% | No |
| **P-04** | Emphasis of Matter | Going Concern / Material Uncertainty flagged (PDF scan) | +75 bps | No cut | **Yes** |
| **P-06** | Circular Fraud Detected | Circular trading loop detected in network graph | No rate change | **−50%** | No |
| **P-09** | Financial Restatement | Prior year financial comparative figures restated by >2% | +200 bps | −40% | **Yes (CRITICAL)** |
| **P-10** | Auditor Rotation / Change | Change in statutory auditor detected across reporting periods | +75 bps | −10% | **Yes (HIGH)** |

Rules **accumulate** — all triggered penalties are applied sequentially on top of each other.

---

## 🔧 Backend — Deep Dive

### `SectionBoundaryDetector` — How it finds sections in a PDF

The detector uses `pdfplumber` to read every page and `PyMuPDF` (fitz) to analyse font sizes. The logic:

1. Extract all text blocks from each page with their font sizes
2. A "heading" is defined as text with a font size ≥ the page's 85th-percentile font size
3. Each heading is normalised (lowercased, stripped) and matched against `SECTION_CONFIGS`
4. When a start keyword matches, the detector records the `start_page` and begins scanning for an end keyword
5. The resulting `SectionBoundary` carries `start_page`, `end_page`, and a `confidence` score

**Why not use PDF bookmarks/outlines?**
Because 90% of Indian annual reports are either:
- Scanned PDFs with no structural metadata
- Digitally generated but with no bookmark tree
- Reports where the PDF outline doesn't match the visual headings

Font-size heuristics work across all of them.

**Section Configs:**

```python
SECTION_CONFIGS = [
  { "id": "mdna",              "max_pages": 30  },
  { "id": "auditors_report",   "max_pages": 20  },
  { "id": "auditors_annexure", "max_pages": 15  },
]
```

### `ComplianceScanner` — How the regex engine works

Three families of compiled patterns:

#### CARO 2020 Patterns
```python
# Catches: "CARO 2020 Clause (vii) – the company has not deposited…"
re.compile(r"(?i)(caro[\s,\-]*2020[\s\S]{0,200}?clause[\s\-]*\(?\s*vii\s*\)?|...)")

# Catches: "Provident Fund dues of ₹12 lakh not deposited"
re.compile(r"(?i)(statutory\s+dues[\s\S]{0,200}?(?:not\s+deposited|outstanding|overdue)...)") 
```

#### Auditor Qualification Patterns
```python
re.compile(r"(?i)except\s+for[\s\S]{0,300}?(?=\n\n|\Z)", re.DOTALL)
re.compile(r"(?i)adverse\s+opinion[\s\S]{0,300}?(?=\n\n|\Z)", re.DOTALL)
re.compile(r"(?i)qualified\s+opinion[\s\S]{0,300}?(?=\n\n|\Z)", re.DOTALL)
```

Every match returns:
- `pattern_name` — which rule fired
- `snippet` — ±200 characters of surrounding context from the original PDF
- `start_char`, `end_char` — raw character offsets for full traceability

Overlapping matches are **deduplicated** — if two patterns fire on overlapping text, only the larger span is kept.

### `Orchestrator` — Single source of truth for all rules

```python
# Checks Perfios first (external bureau signal)
if perfios_data["gstr_2a_3b_mismatch_pct"] > 15:
    triggered.append("P-01")

# Then checks PDF scan signals
if pdf_scan["caro_default_found"] or pdf_scan["adverse_opinion_found"]:
    triggered.append("P-03")

if pdf_scan["emphasis_of_matter_found"]:
    triggered.append("P-04")
```

The orchestrator is imported by `analyze_report.py` so there's zero duplication of penalty logic between the endpoint and the decision layer.

---

## 🌍 Web Sleuth Agent — Adverse Media Scanner

The `WebSleuth` agent (`app/agents/web_sleuth.py`) is a lightweight secondary research crawler that scans the open web for adverse media signals related to the borrower entity.

### How It Works

1. **Query Builder**: Constructs 2–3 targeted search queries combining the entity name with risk keywords (e.g., `"Acme Steels" fraud default NCLT RBI action`)
2. **Web Scraper**: Fetches search results from DuckDuckGo / Bing (failover chain) using `requests` + `BeautifulSoup`
3. **Keyword Scorer**: Scans retrieved text against a **weighted negative keyword dictionary** (50+ terms):

| Weight | Keywords |
|---|---|
| **2.0** (high signal) | fraud, money laundering, NCLT, SFIO, ED raid, Ponzi |
| **1.5** (medium signal) | default, NPA, wilful defaulter, insolvency, CIRP |
| **1.0** (baseline) | litigation, dispute, penalty, downgrade, forensic audit |

4. **Mitigant Detection**: If a negative keyword appears in the same sentence as a mitigant word ("resolved", "dismissed", "acquitted", "settled"), the hit is neutralised
5. **Deterministic Fallback**: If live search is blocked (CAPTCHAs, network issues), the agent returns a mock result — only flagging entities whose names contain `STRESS` or `DEFAULT` for testing purposes

---

## 🤖 ML Baseline Model — Rate & Limit Predictor

The `ml_baseline.py` agent uses a **scikit-learn `RandomForestRegressor`** (multi-output) trained on synthetic financial ratio data to predict a machine-recommended base rate and credit limit.

### Features Used

| Feature | Description | Source |
|---|---|---|
| `dscr` | Debt Service Coverage Ratio | Derived from Perfios / financial statements |
| `leverage_ratio` | Total Debt / Total Assets | Derived from balance sheet |
| `gst_compliance_pct` | GST filing regularity score | Perfios bureau |
| `promoter_pledge_pct` | % of promoter shares pledged | Shareholding pattern |
| `litigation_count` | Active litigations count | Karza bureau |
| `caro_flag` | 1 if CARO default found, else 0 | PDF compliance scan |
| `auditor_flag` | 1 if adverse/qualified opinion, else 0 | PDF compliance scan |

### Model Lifecycle

1. **Auto-train**: If no saved model exists at `models/ml_baseline.joblib`, the model generates 2,000 synthetic samples and trains a fresh RandomForest on startup
2. **Persist**: Trained model is serialised using `joblib` for instant loading on subsequent restarts
3. **Predict**: Given a dict of financial ratios, returns `{ ml_rate, ml_limit, feature_vector, model_status }`
4. **Transparent**: The full feature vector used for prediction is returned alongside the output for explainability

> The ML model provides a **second opinion** alongside the deterministic rule engine — it does not override the penalty accumulator.

---

## 🎓 CEO Ambidexterity Scorer

The `ceo_scorer.py` agent analyses the Management Discussion & Analysis (MD&A) section for **organisational ambidexterity** — a measure of whether management balances exploration (innovation) with exploitation (operational efficiency).

Based on the **McKenny et al. (2018)** academic framework:

- **Exploration keywords** (50+): "breakthrough", "R&D", "prototype", "patent", "novel", "pioneered"
- **Exploitation keywords** (50+): "streamline", "optimize", "throughput", "standardized", "production"

### Output
```json
{
  "exploration_score": 0.0034,
  "exploitation_score": 0.0078,
  "exploration_exploitation_ratio": 0.44,
  "top_exploration_keywords": { "research": 12, "novel": 3 },
  "top_exploitation_keywords": { "production": 28, "efficiency": 15 }
}
```

A ratio significantly skewed towards exploitation may indicate a company focused on short-term efficiency at the expense of long-term growth — a subtle credit risk signal.

---

## 🕸 Network Analysis — Circular Trading Detection

The Network Analysis module detects **circular trading fraud** — a common pattern where a borrower routes funds through shell entities in a loop to inflate revenue.

### Backend (`GET /mock/network-graph`)
Returns a node-edge graph structure:
- **Nodes**: Acme Steels (applicant), Vertex Holdings (shell), Nova Corp (shell)
- **Edges**: Directional money flows with amounts (₹5.0 Cr → ₹4.8 Cr → ₹4.5 Cr back)
- **Flag**: `circular_trading_detected: true` → triggers **P-06 (−50% credit limit)**

### Frontend (`NetworkAnalysis.jsx`)
Built with `react-force-graph-2d`:
- Interactive force-directed graph with draggable nodes
- Distinct colour coding: 🔵 Applicant vs 🔴 Shell entities
- Animated directional particles on edges showing money flow direction
- Circular loop highlighted with amount annotations

---

## 🎨 Frontend — Deep Dive

Built with **React 18 + Vite**, styled with **Vanilla CSS** using a custom dark-mode design system.

### Component Map

```
App.jsx
├── PDFViewer              — Drag-and-drop PDF uploader with preview
├── [Left Panel]
│   ├── Site Visit Notes textarea  — Primary Insights for CAM C2
│   ├── "Run Full Credit Committee" button
│   ├── BureauCard (Perfios)       — Live GST recon data
│   └── BureauCard (Karza)         — Live litigation/KYB data
└── [Right Panel — Decision Engine]
    ├── Tab: CompliancePanel       — Boolean flag cards + section metadata
    ├── Tab: WaterfallChart        — Recharts waterfall with penalty bars
    ├── Tab: ComplianceHeatmap     — Evidence grid (one cell per regex match)
    ├── Tab: NetworkAnalysis       — Force-graph circular fraud visualisation
    ├── Tab: ScorePanel            — ML model confidence + feature breakdown
    ├── [Download CAM button]      — Triggers POST /export-cam → .docx download
    └── Rule Engine footer strip   — P-01 → P-06 live status badges
```

### Client-Side Orchestrator (mirrors backend)

`App.jsx` contains a pure JavaScript port of the Python orchestrator. This means:
- The Waterfall Chart updates **instantly** as data arrives from any of the three parallel API calls
- No second round-trip needed to recompute the decision after bureau data loads
- The rate and limit in the footer strip are always in sync with what the CAM will say

### The Waterfall Chart

Built with **Recharts `ComposedChart`** using a stacked invisible+visible bar trick:

```
Rate (%)
 14 |
 12 |                    ██ +150bps (P-03)
 11 |         ██ +100bps  ║
 10 |         ║  (P-01)   ║
  9 |  ████████           ████████
    |  Base    P-01       P-03    Final
    |  9.0%    10.0%      11.5%   11.5%
```

Each bar is dynamically built from `decision.applied_penalties` — the chart self-assembles from whatever the orchestrator returns.

---

## 📑 The CAM Generator

`app/utils/cam_generator.py` generates a fully formatted Word (.docx) document using `python-docx`, structured around the **Five Cs of Credit**:

| Section | Cs | Data Source | Colour Logic |
|---|---|---|---|
| **C1: Character** | Who is this borrower? | Karza (litigations, director KYB, MCA charges) | 🟡 Amber = watch flag, 🔴 Red = disqualified |
| **C2: Capacity** | Can they repay? | Perfios (GST recon) + Site Visit Notes (officer input) | 🔴 Red = mismatch >15%, 🟢 Green = clean |
| **C3: Capital** | What is their net worth? | Manual officer entry (free-text fields in API body) | — |
| **C4: Collateral** | What secures us? | Karza (MCA charges) + officer entry | 🟡 Amber = existing charge |
| **C5: Conditions** | What do auditors say? | PDF ComplianceScanner (CARO, qualifications) | 🔴 Red = flagged, 🟢 Green = clean |

The document also contains:
- **Title block** with entity name, date, and preparing system
- **Summary KV table** with recommended rate, limit, and decision (colour-coded)
- **Penalty Accumulation table** with a deep blue header row listing every triggered rule
- **Evidence snippets** — up to 3 direct quotes from the PDF for every CARO/qualification finding
- **Credit Committee Sign-Off block** with three signature lines (RM / Credit Analyst / Committee Head)
- **Footer** — generation timestamp and determinism disclaimer

---

## 📡 API Reference

Base URL: `http://localhost:8000/api/v1`

Interactive docs: `http://localhost:8000/docs`

### `POST /analyze-report`
Upload an annual report PDF. Runs full compliance scan.

**Request:** `multipart/form-data` with `file` field (PDF only)

**Response:**
```json
{
  "status": "success",
  "file_name": "AnnualReport_FY23.pdf",
  "sections_detected": {
    "auditors_report":    { "start_page": 60, "end_page": 72, "confidence": 0.91 },
    "auditors_annexure":  { "start_page": 73, "end_page": 80, "confidence": 0.87 }
  },
  "caro_default_found":       true,
  "adverse_opinion_found":    false,
  "emphasis_of_matter_found": false,
  "triggered_rules":          ["P-03"],
  "caro_findings": [
    {
      "pattern": "CARO / statutory-dues",
      "snippet": "…CARO 2020 Clause (vii): The company has not deposited Provident Fund dues of ₹14.2 lakh…"
    }
  ],
  "auditor_qualification_findings": [],
  "total_caro_matches": 1,
  "total_qualification_matches": 0,
  "decision": {
    "base_rate_pct": 9.0,
    "final_rate_pct": 10.5,
    "base_limit_cr": 10.0,
    "final_limit_cr": 8.0,
    "recommendation": "CONDITIONAL_APPROVAL",
    "applied_penalties": [
      { "rule_id": "P-03", "rate_penalty_bps": 150, "limit_reduction_pct": 20 }
    ]
  },
  "methodology": "All findings extracted by deterministic regex — zero LLM calls."
}
```

---

### `GET /mock/network-graph`
Returns a simulated network intelligence response for circular trading detection.

```json
{
  "status": "success",
  "circular_trading_detected": true,
  "nodes": [
    { "id": "acme", "label": "Acme Steels (Applicant)", "type": "applicant" },
    { "id": "vertex", "label": "Vertex Holdings (Shell)", "type": "shell" },
    { "id": "nova", "label": "Nova Corp (Shell)", "type": "shell" }
  ],
  "links": [
    { "source": "acme", "target": "vertex", "value": 5.0, "label": "₹5.0 Cr" },
    { "source": "vertex", "target": "nova", "value": 4.8, "label": "₹4.8 Cr" },
    { "source": "nova", "target": "acme", "value": 4.5, "label": "₹4.5 Cr" }
  ]
}
```

In production: this would be powered by a graph database (Neo4j) analysing GST transaction chains across entity networks.

---

### `GET /mock/perfios`
Returns a simulated GST reconciliation bureau response.

```json
{
  "status": "success",
  "gstr_2a_3b_mismatch_pct": 18.5,
  "circular_trading_flag": false,
  "itc_reversal_required": true,
  "itc_reversal_amount_lakh": 12.4
}
```

---

### `GET /mock/karza`
Returns a simulated litigation and director KYB response.

```json
{
  "status": "success",
  "active_litigations": ["Section 138 NI Act – Cheque Bounce – Pending at JMFC Mumbai"],
  "director_disqualified": false,
  "mca_charge_registered": true,
  "charge_amount_cr": 7.0,
  "charge_holders": ["HDFC Bank Ltd"]
}
```

---

### `POST /export-cam`
Generate and download a `.docx` Credit Appraisal Memo.

**Request body:**
```json
{
  "entity_name": "Acme Steels Pvt Ltd",
  "primary_insights": "Plant visit: capacity utilisation ~70%. Management experienced.",
  "pdf_scan": { ... },
  "perfios":  { ... },
  "karza":    { ... },
  "decision": { ... },
  "triggered_rules": ["P-01", "P-03"]
}
```

**Response:** Binary `.docx` file stream with `Content-Disposition: attachment`

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+

### Backend

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Run the development server
uvicorn main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`
Swagger UI: `http://localhost:8000/docs`

### Frontend

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Run the dev server
npm run dev
```

The dashboard will be available at `http://localhost:5173`

> The frontend proxies `/api/v1/...` to `localhost:8000` via Vite's proxy config.

---

## 📁 Project Structure

```
Pramaan/
├── README.md                          ← You are here
│
├── backend/
│   ├── main.py                        ← FastAPI app factory, CORS, lifespan hooks
│   ├── requirements.txt               ← Python dependencies
│   ├── models/
│   │   └── ml_baseline.joblib         ← Persisted ML model weights
│   └── app/
│       ├── core/
│       │   └── config.py              ← Settings (Pydantic BaseSettings)
│       ├── agents/
│       │   ├── orchestrator.py        ← Rule engine + penalty accumulator (P-01→P-06)
│       │   ├── web_sleuth.py          ← Adverse media web crawler + keyword scorer
│       │   ├── ml_baseline.py         ← RandomForest rate/limit predictor
│       │   └── deep_reader/
│       │       ├── section_boundary_detector.py ← Font-heuristic PDF section locator
│       │       ├── section_hierarchy_builder.py ← Nested section tree builder
│       │       ├── compliance_scanner.py        ← Zero-LLM regex compliance engine
│       │       ├── ceo_scorer.py                ← Management ambidexterity scorer
│       │       └── gemini_extractor.py          ← LLM-based structured extraction
│       ├── api/
│       │   └── v1/
│       │       ├── router.py          ← Route aggregator
│       │       ├── analyze_report.py  ← POST /analyze-report
│       │       ├── external_mocks.py  ← GET /mock/perfios, /mock/karza, /mock/network-graph
│       │       └── export_cam.py      ← POST /export-cam
│       └── utils/
│           └── cam_generator.py       ← python-docx Five Cs document builder
│
└── frontend/
    ├── index.html
    ├── vite.config.js                 ← API proxy config
    └── src/
        ├── App.jsx                    ← Root: Credit Committee orchestration
        ├── index.css                  ← Design system (dark mode, custom tokens)
        └── components/
            ├── PDFViewer.jsx           ← Drag-and-drop uploader + metadata preview
            ├── CompliancePanel.jsx     ← Boolean flag cards + section scan badge
            ├── WaterfallChart.jsx      ← Recharts waterfall (data-driven from API)
            ├── HallucinationHeatmap.jsx← Compliance evidence grid (zero hallucination)
            ├── NetworkAnalysis.jsx     ← Force-directed circular fraud graph
            └── ScorePanel.jsx         ← ML model confidence + feature breakdown
```

---

## 🧠 Key Design Decisions

### 1. Zero-LLM Decisioning Chain
Every signal in the penalty accumulator is computed deterministically. No generative model is called anywhere in the critical decision path. This is a deliberate architectural constraint, not a limitation — it ensures:
- **Regulatory defensibility:** Every decision can be reproduced and explained
- **Zero hallucination risk:** The system cannot invent findings
- **Consistent output:** Running the same PDF twice always produces the same result

### 2. Section Boundary Detection via Font-Size Heuristics
Rather than relying on PDF bookmarks (unreliable in Indian reports) or LLM prompting (expensive, non-deterministic), we use pdfplumber + PyMuPDF to identify heading-level text by font size percentile. This works reliably across:
- Digitally generated PDFs
- MCA-filed reports
- Scanned + OCR'd documents (with readable text layer)

### 3. Client-Side Orchestrator Mirror
The penalty accumulator is implemented in both Python (backend) and JavaScript (frontend). This lets the React dashboard update the Waterfall Chart instantly as responses arrive from the parallel API calls — without waiting for a backend round-trip to recompute the combined decision.

### 4. Five Cs as the Organisational Framework
The Credit Appraisal Memo is intentionally structured around the Five Cs (Character, Capacity, Capital, Collateral, Conditions) because:
- Every credit professional in India is trained in this framework
- It maps cleanly to the three data sources (Karza → Character, Perfios → Capacity, PDF → Conditions)
- It produces a document that a credit committee can immediately use without any formatting work

### 5. Graceful Degradation
- If the auditor section is not found → returns `section_not_found` status (no crash)
- If the PDF is image-only with no text layer → returns 422 with a clear message
- If Perfios or Karza are unavailable → PDF-only decision still runs
- If python-docx is not installed → CAM endpoint returns a clear 500 with install instructions

---

## 🗺 Roadmap

### Completed ✅
- [x] **P-06 Circular Fraud:** Network graph analysis detecting circular trading loops (−50% limit)
- [x] **Web Sleuth Agent:** Adverse media crawler with weighted keyword scoring + mitigant detection
- [x] **ML Baseline Model:** RandomForest rate/limit predictor trained on synthetic financial ratios
- [x] **CEO Ambidexterity Scorer:** Management exploration/exploitation analysis (McKenny framework)
- [x] **Network Analysis UI:** Interactive force-directed graph with animated directional particles
- [x] **Score Panel UI:** ML model confidence gauge with feature breakdown

### Phase 2 — Next Up
- [ ] **Primary Insight Portal:** Structured credit officer input (factory utilization, management quality) wired into scoring
- [ ] **Bank Statement Cross-Leverage:** Compare GST turnover vs bank credits to detect revenue inflation
- [ ] **Audit Trail Timeline:** Chronological step-by-step decision log for full explainability
- [ ] **CIBIL Commercial Score Integration:** Mock bureau for credit score, DPD history, enquiry count
- [ ] **P-05 DSCR Watch:** Parse cash flow statement to compute DSCR < 1.2x trigger

### Phase 3 — Production Integrations
- [ ] Replace Perfios mock with live GST reconciliation API integration
- [ ] Replace Karza mock with live Entity Search + Director KYB API
- [ ] Replace Network Graph mock with Neo4j-powered entity relationship analysis
- [ ] Add user authentication (JWT) for multi-analyst access
- [ ] Audit log database (PostgreSQL) — every scan persisted with timestamp + analyst ID
- [ ] Email delivery of the final CAM to the credit committee

### Phase 4 — Scale
- [ ] Batch processing endpoint for portfolio-level scans (50+ PDFs in one run)
- [ ] Multi-year annual report comparison with YoY trend analysis
- [ ] Webhook support for triggering downstream LOS (Loan Origination System) updates
- [ ] Historical decision dashboard for credit committee to track rule trigger rates over time

---

## 🛡 Philosophy

> *"Give me a fact or give me nothing. Good general statements and unsupported statistics I abhor."*
> — Credit Committee Proverb

Project Pramaan is built on the belief that **in regulated finance, explainability is not a nice-to-have — it is the product.** A credit officer who can point to page 67 of an annual report and say "here is the exact sentence that triggered our higher rate" is worth infinitely more to a bank than a black-box model that says "we think this borrower is risky."

Every line of code in Pramaan is written with one question in mind: **"Could a credit committee reproduce this finding by hand, given the same input?"**

If the answer is yes, it ships. If the answer is no, it doesn't.

---

<div align="center">

Built with 🏦 for India's credit ecosystem

**Project Pramaan** — *Proof, not probability.*

</div>
