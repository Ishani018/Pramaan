/**
 * App.jsx – Project Pramaan Dashboard (Credit Committee Edition)
 * ==============================================================
 * Credit Committee pipeline:
 *   1. POST /api/v1/analyze-report      → PDF compliance scan (P-03, P-04)
 *   2. GET  /api/v1/mock/perfios        → GST reconciliation   (P-01)
 *   3. GET  /api/v1/mock/karza          → Litigation / KYB     (watch flag)
 *   4. orchestrate_decision()           → unified penalty decision (client-side mirror)
 *   5. POST /api/v1/export-cam          → Download .docx CAM memo
 */
import { useState, useCallback, useEffect, useRef } from 'react'
import axios from 'axios'
import {
    Brain, Shield, ChevronRight, AlertCircle, Download,
    BarChart2, Map, ShieldAlert, Terminal, Cpu, TrendingDown, TrendingUp,
    FileText, Building2, Landmark, Network, ListTree, ChevronDown, Eye, ShieldCheck
} from 'lucide-react'
import PDFViewer from './components/PDFViewer'
import WaterfallChart from './components/WaterfallChart'
import ComplianceHeatmap from './components/HallucinationHeatmap'
import CompliancePanel from './components/CompliancePanel'
import NetworkAnalysis from './components/NetworkAnalysis'
import AdverseMediaPanel from './components/AdverseMediaPanel'
import RestatementAnalysis from './components/RestatementAnalysis'
import TrendPanel from './components/TrendPanel'
import BankStatementPanel from './components/BankStatementPanel'
import SectorBenchmarkPanel from './components/SectorBenchmarkPanel'
import CrossVerificationPanel from './components/CrossVerificationPanel'
import BSESearch from './components/BSESearch'
import SupplyChainRiskPanel from './components/SupplyChainRiskPanel'

export const RULE_DISPLAY_NAMES = {
    "P-01": "GST-01: Revenue Mismatch",
    "P-02": "KYC-01: Director Network Risk",
    "P-03": "AUDIT-01: Statutory Default",
    "P-04": "AUDIT-02: Emphasis of Matter",
    "P-06": "FRAUD-01: Circular Trading",
    "P-07": "PRIMARY-01: Site Visit Risk",
    "P-08": "BANK-01: Suspicious Routing",
    "P-09": "RESTATE-01: Silent Restatement",
    "P-10": "AUDIT-03: Auditor Rotation",
    "P-11": "RATING-01: Sub-Investment Grade",
    "P-12": "RATING-02: Downgrade/Default",
    "P-13": "MEDIA-01: Adverse Media",
    "P-15": "LEGAL-01: Active Court Proceedings",
    "P-16": "MGMT-01: Negative Management Sentiment",
    "P-17": "SHARE-01: High Promoter Pledge",
    "P-18": "SHARE-02: Low Promoter Holding",
    "P-31": "XVER-01: Revenue Verification Mismatch",
    "P-32": "XVER-02: Compliance Claim Contradicted"
}

// ── Client-side penalty orchestrator (mirrors backend logic) ─────────────────
console.log("BASE_RATE INIT");
const BASE_RATE = 9.0
const BASE_LIMIT = 10.0

function orchestrateDecision(pdfScan, perfios, networkData, restatementData) {
    const triggered = []

    if (perfios?.gstr_2a_3b_mismatch_pct > 15) triggered.push('P-01')
    if (pdfScan?.caro_default_found || pdfScan?.adverse_opinion_found) triggered.push('P-03')
    if (pdfScan?.emphasis_of_matter_found) triggered.push('P-04')
    if (networkData?.circular_trading_detected) triggered.push('P-06')
    if (restatementData?.restatements_detected) triggered.push('P-09')
    if (restatementData?.auditor_changed) triggered.push('P-10')
    const news = pdfScan?.news || pdfScan?.news_data;
    if (news && news.adverse_media_detected) triggered.push('P-13')

    // Check ecourts via multiple possible keys (ecourts vs ecourts_data)
    let ecourts = pdfScan?.ecourts || pdfScan?.ecourts_data;
    if (ecourts && ecourts.triggered_rules && ecourts.triggered_rules.includes('P-15')) {
        if (!triggered.includes('P-15')) triggered.push('P-15')
    }
    if (pdfScan?.mda_insights?.status === 'success' && pdfScan.mda_insights.sentiment_score < -0.01) triggered.push('P-16')

    // Check shareholding risks
    const shareholding = pdfScan?.shareholding_data;
    if (shareholding && shareholding.triggered_rules) {
        if (shareholding.triggered_rules.includes('P-17') && !triggered.includes('P-17')) triggered.push('P-17');
        if (shareholding.triggered_rules.includes('P-18') && !triggered.includes('P-18')) triggered.push('P-18');
    }

    // ── P-31 & P-32: Cross-Verification Mismatches ────────────────────────
    const xver = pdfScan?.cross_verification;
    if (xver && xver.triggered_rules) {
        for (const rule of xver.triggered_rules) {
            if (!triggered.includes(rule)) triggered.push(rule);
        }
    }

    const RULES = {
        'P-01': { name: RULE_DISPLAY_NAMES['P-01'], bps: 100, cut: 10, manual: false, trigger: 'GSTR-2A vs 3B mismatch > 15% (Perfios)' },
        'P-03': { name: RULE_DISPLAY_NAMES['P-03'], bps: 150, cut: 20, manual: false, trigger: 'CARO 2020 Clause (vii) / auditor qualification' },
        'P-04': { name: RULE_DISPLAY_NAMES['P-04'], bps: 75, cut: 0, manual: true, trigger: 'Going concern or material uncertainty flagged' },
        'P-06': { name: RULE_DISPLAY_NAMES['P-06'], bps: 200, cut: 30, manual: true, trigger: 'Counterparty intelligence detected shared directors, shell companies, or circular money flows' },
        'P-09': { name: RULE_DISPLAY_NAMES['P-09'], bps: 200, cut: 40, manual: true, trigger: 'Prior year financial comparative figures restated by >2%' },
        'P-10': { name: RULE_DISPLAY_NAMES['P-10'], bps: 75, cut: 10, manual: true, trigger: 'Change in statutory auditor detected across reporting periods' },
        'P-13': { name: RULE_DISPLAY_NAMES['P-13'], bps: 50, cut: 0, manual: true, trigger: 'NewsScanner found high-severity red flags (fraud, ED raid, etc.)' },
        'P-15': { name: RULE_DISPLAY_NAMES['P-15'], bps: 100, cut: 15, manual: true, trigger: 'High-risk court cases found via eCourts (NCLT/winding up/fraud/DRT)' },
        'P-16': { name: RULE_DISPLAY_NAMES['P-16'], bps: 50, cut: 5, manual: false, trigger: 'MD&A sentiment score negative per Loughran-McDonald lexicon' },
        'P-17': { name: RULE_DISPLAY_NAMES['P-17'], bps: 75, cut: 10, manual: true, trigger: 'Promoter shares pledged > 50% — distress signal, forced selling risk' },
        'P-18': { name: RULE_DISPLAY_NAMES['P-18'], bps: 50, cut: 5, manual: false, trigger: 'Promoter holding below 26% — low skin in the game' },
        'P-31': { name: RULE_DISPLAY_NAMES['P-31'], bps: 100, cut: 15, manual: true, trigger: 'Cross-verification: claimed revenue not supported by bank deposits or GST data' },
        'P-32': { name: RULE_DISPLAY_NAMES['P-32'], bps: 75, cut: 10, manual: true, trigger: 'Cross-verification: annual report claims contradicted by external bureau data' },
    }

    let rate = BASE_RATE
    let limit = BASE_LIMIT
    let manual = false
    const applied = []

    for (const id of triggered) {
        const r = RULES[id]
        if (!r) continue
        rate += r.bps / 100
        limit = limit * (1 - r.cut / 100)
        applied.push({ rule_id: id, name: r.name, trigger: r.trigger, rate_penalty_bps: r.bps, limit_reduction_pct: r.cut })
        if (r.manual) manual = true
    }

    return {
        base_rate_pct: BASE_RATE, final_rate_pct: Math.round(rate * 100) / 100,
        base_limit_cr: BASE_LIMIT, final_limit_cr: Math.round(limit * 100) / 100,
        recommendation: manual ? 'MANUAL_REVIEW' : triggered.length ? 'CONDITIONAL_APPROVAL' : 'APPROVE',
        applied_penalties: applied,
        triggered_rules: triggered,
    }
}

const PROGRESS_STEPS = [
    { pct: 5, msg: "INGESTING DOCUMENT...", sub: "Opening PDF and detecting type" },
    { pct: 15, msg: "EXTRACTING SECTIONS...", sub: "SectionBoundaryDetector running" },
    { pct: 35, msg: "SCANNING COMPLIANCE...", sub: "CARO 2020 / Auditor Report analysis" },
    { pct: 50, msg: "EXTRACTING FINANCIALS...", sub: "Revenue, EBITDA, Net Worth, Debt" },
    { pct: 65, msg: "QUERYING MCA21...", sub: "Live company registry lookup" },
    { pct: 75, msg: "SCANNING ADVERSE MEDIA...", sub: "NewsAPI live search running" },
    { pct: 82, msg: "RUNNING RESTATEMENT CHECK...", sub: "Multi-year comparison" },
    { pct: 89, msg: "CROSS-VERIFYING CLAIMS...", sub: "Annual report vs external evidence" },
    { pct: 94, msg: "COMPUTING PENALTIES...", sub: "Rate waterfall accumulator" },
    { pct: 97, msg: "GENERATING CAM...", sub: "Credit Appraisal Memo assembly" },
    { pct: 100, msg: "ANALYSIS COMPLETE", sub: "Switching to results..." }
]

// ── Tab config ────────────────────────────────────────────────────────────────
const TABS = [
    { id: 'decision', label: 'Decision', icon: BarChart2 },
    { id: 'cross-verify', label: 'Verify', icon: ShieldCheck },
    { id: 'deep-dive', label: 'Deep Dive', icon: Eye },
]

const ALL_RULES = [
    { id: 'P-01', label: RULE_DISPLAY_NAMES['P-01'] },
    { id: 'P-02', label: RULE_DISPLAY_NAMES['P-02'] },
    { id: 'P-03', label: RULE_DISPLAY_NAMES['P-03'] },
    { id: 'P-04', label: RULE_DISPLAY_NAMES['P-04'] },
    { id: 'P-06', label: RULE_DISPLAY_NAMES['P-06'] },
    { id: 'P-09', label: RULE_DISPLAY_NAMES['P-09'], severity: 'CRITICAL' },
    { id: 'P-10', label: RULE_DISPLAY_NAMES['P-10'], severity: 'HIGH' },
    { id: 'P-13', label: RULE_DISPLAY_NAMES['P-13'], severity: 'HIGH' },
    { id: 'P-15', label: RULE_DISPLAY_NAMES['P-15'], severity: 'HIGH' },
    { id: 'P-16', label: RULE_DISPLAY_NAMES['P-16'] },
    { id: 'P-17', label: RULE_DISPLAY_NAMES['P-17'], severity: 'HIGH' },
    { id: 'P-18', label: RULE_DISPLAY_NAMES['P-18'] },
    { id: 'P-31', label: RULE_DISPLAY_NAMES['P-31'], severity: 'HIGH' },
    { id: 'P-32', label: RULE_DISPLAY_NAMES['P-32'], severity: 'HIGH' },
]

function StatusBadge({ status, message }) {
    const styles = {
        idle: { color: 'text-muted', text: '[IDLE]' },
        loading: { color: 'text-red font-bold animate-pulse', text: '[ACTIVE]' },
        success: { color: 'text-ink font-bold', text: '[READY]' },
        error: { color: 'text-red font-bold', text: `[ERROR: ${message}]` },
    }
    const s = styles[status] || styles.idle
    return (
        <div className={`font-mono text-xs ${s.color}`}>
            {s.text}
        </div>
    )
}

function FinancialFigure({ data }) {
    if (!data) return <span className="font-mono text-[11px] font-bold text-ink">N/A</span>

    let confBadge = null;
    if (data.confidence === "HIGH") {
        confBadge = <span style={{ color: "#22c55e", fontSize: "10px" }}>● HIGH</span>
    } else if (data.confidence === "MEDIUM") {
        confBadge = <span style={{ color: "#f59e0b", fontSize: "10px" }}>● MED</span>
    } else if (data.confidence === "LOW") {
        confBadge = <span style={{ color: "#ef4444", fontSize: "10px" }}>● LOW — verify manually</span>
    }

    const conversionStr = data.unit !== "Cr" && data.unit !== "unknown" && data.raw_value
        ? `₹${data.raw_value} ${data.unit} → ₹${data.value} Cr`
        : `₹${data.value} Cr`;

    return (
        <span className="font-mono text-[11px] font-bold text-ink flex items-center gap-2">
            {conversionStr}
            {confBadge}
        </span>
    );
}

// ── External bureau panels (read-only display) ────────────────────────────────
function BureauCard({ icon: Icon, title, data, loading, color }) {
    if (loading) return <div className="shimmer h-20" />
    if (!data) return null
    return (
        <div className="border-t-2 border-border pt-3 mt-2">
            <div className="flex items-center gap-2 mb-2">
                <Icon size={14} className="text-ink" />
                <h3 className="text-sm font-display font-bold uppercase tracking-wide text-ink">{title}</h3>
            </div>
            <div className="space-y-1">
                {Object.entries(data)
                    .filter(([k]) => !['status', 'provider', 'metadata', 'active_litigations', 'entity', 'cin', 'gstin'].includes(k))
                    .slice(0, 6)
                    .map(([k, v]) => (
                        <div key={k} className="flex justify-between text-xs">
                            <span className="text-ink capitalize font-serif">{k.replace(/_/g, ' ')}</span>
                            <span className="font-mono text-ink font-bold">{String(v)}</span>
                        </div>
                    ))}
                {data.active_litigations?.length > 0 && (
                    <div className="text-xs text-red font-mono font-bold mt-2">⚠ {data.active_litigations[0]}</div>
                )}
            </div>
        </div>
    )
}

export default function App() {
    // ── State ──────────────────────────────────────────────────────────────────
    const [selectedFiles, setSelectedFiles] = useState([])
    const [auditTrail, setAuditTrail] = useState(null)
    const [pdfResult, setPdfResult] = useState(null)
    const [perfiosData, setPerfiosData] = useState(null)
    const [karzaData, setKarzaData] = useState(null)
    const [networkData, setNetworkData] = useState(null)
    const [cibilData, setCibilData] = useState(null)
    const [bankCsvFile, setBankCsvFile] = useState(null)
    const [primaryNotes, setPrimaryNotes] = useState('')
    const [loading, setLoading] = useState(false)
    const [camLoading, setCamLoading] = useState(false)
    const [error, setError] = useState(null)
    const [activeTab, setActiveTab] = useState('decision')
    const [bureauLoading, setBureauLoading] = useState(false)
    const [progressStepIdx, setProgressStepIdx] = useState(0)
    const pdfRef = useRef(null)

    const handlePdfFetched = useCallback((file, yearLabel) => {
        if (pdfRef.current) {
            pdfRef.current.addFile(file, yearLabel)
        }
    }, [])

    const handleFilesChange = useCallback((files) => {
        setSelectedFiles(files)
        setPdfResult(null)
        setAuditTrail(null)
        setError(null)
    }, [])

    // ── Compute unified decision from all sources ──────────────────────────────
    const decision = (pdfResult || perfiosData || networkData)
        ? orchestrateDecision(pdfResult, perfiosData, networkData, pdfResult?.restatement_data)
        : null

    const triggeredRules = decision?.triggered_rules || []

    // ── Run the full Credit Committee pipeline ─────────────────────────────────
    const handleAnalyse = async () => {
        if (selectedFiles.length === 0) return
        setLoading(true)
        setBureauLoading(true)
        setError(null)
        setPdfResult(null)
        setPerfiosData(null)
        setKarzaData(null)
        setNetworkData(null)
        setCibilData(null)
        setBankCsvFile(null)
        setAuditTrail(null)
        setActiveTab('compliance')
        setProgressStepIdx(0)

        // Progress step sequencer triggered via useEffect hook
        // which watches the loading boolean.

        try {
            const formData = new FormData()
            selectedFiles.forEach(f => {
                const fieldName = `file_${f.yearLabel.toLowerCase().replace(/[^a-z0-9]/g, '')}`
                formData.append(fieldName, f.file)
            })
            formData.append("site_visit_notes", primaryNotes)
            if (bankCsvFile) {
                formData.append("bank_csv", bankCsvFile)
            }

            const [pdfResp, perfiosResp, karzaResp, cibilResp] = await Promise.all([
                axios.post('/api/v1/analyze-report', formData, {
                    headers: { 'Content-Type': 'multipart/form-data' },
                    timeout: 180_000,
                }),
                axios.get('/api/v1/mock/perfios', { timeout: 180_000 }),
                axios.get('/api/v1/mock/karza', { timeout: 180_000 }),
                axios.get('/api/v1/mock/cibil', { timeout: 180_000 }),
            ])

            setPdfResult(pdfResp.data)
            setPerfiosData(perfiosResp.data)
            setKarzaData(karzaResp.data)
            setCibilData(cibilResp.data)

            // Network data now comes from the analysis response (counterparty intelligence)
            const cpIntel = pdfResp.data.counterparty_intel
            if (cpIntel && cpIntel.network_graph) {
                setNetworkData({
                    ...cpIntel.network_graph,
                    circular_trading_detected: cpIntel.circular_trading_detected,
                    relationship_flags: cpIntel.relationship_flags || [],
                    counterparty_profiles: cpIntel.counterparty_profiles || [],
                    findings: cpIntel.findings || [],
                })
            } else {
                setNetworkData(null)
            }

            // Auto-jump to waterfall if any rule triggered
            const cpIntelForDecision = cpIntel ? {
                circular_trading_detected: cpIntel.circular_trading_detected,
            } : null
            const pendingDecision = orchestrateDecision(
                pdfResp.data,
                perfiosResp.data,
                cpIntelForDecision,
                pdfResp.data.restatement_data
            )

            // Fetch audit trail narrative via POST
            try {
                const auditResp = await axios.post('/api/v1/decision-narrative', {
                    decision: pendingDecision,
                    triggered_rules: pendingDecision.triggered_rules || [],
                    pdf_scan: pdfResp.data,
                    perfios_data: perfiosResp.data,
                    restatement_data: pdfResp.data.restatement_data,
                })
                setAuditTrail(auditResp.data)
            } catch (err) {
                console.error("Narrative generation failed", err)
            }

            if (pendingDecision.triggered_rules.length > 0) {
                setTimeout(() => setActiveTab('decision'), 1100)
            }
        } catch (err) {
            const msg = err.response?.data?.detail || err.message || 'Unexpected error'
            setError(msg)
        } finally {
            setProgressStepIdx(PROGRESS_STEPS.length - 1)
            setTimeout(() => {
                setLoading(false)
                setBureauLoading(false)
                setProgressStepIdx(0)
            }, 500)
        }
    }

    // Effect to sequence progress bar
    useEffect(() => {
        if (!loading) return;

        let timer;
        if (progressStepIdx < PROGRESS_STEPS.length - 2) {
            // Steps 0-4 (0 to 4): 2.5s each
            // Steps 5-8 (5 to 8): 2s each
            const delay = progressStepIdx <= 4 ? 2500 : 2000;
            timer = setTimeout(() => {
                setProgressStepIdx(prev => prev + 1);
            }, delay);
        }
        return () => clearTimeout(timer);
    }, [loading, progressStepIdx]);

    const handleDownloadCAM = async () => {
        if (!decision) return
        setCamLoading(true)
        console.log("CAM entity_name:", pdfResult?.entity_name)
        console.log("MCA data being sent:", pdfResult?.mca)

        const allRules = pdfResult?.all_triggered_rules || []
        console.log("CAM triggered_rules:", allRules)

        try {
            const payload = {
                entity_name: pdfResult?.entity_name || karzaData?.entity || 'Acme Steels Pvt Ltd',
                primary_insights: primaryNotes,
                pdf_scan: pdfResult,
                perfios: perfiosData,
                karza: karzaData,
                mca_data: pdfResult?.mca,
                decision: decision,
                triggered_rules: allRules,
                restatement_data: pdfResult?.restatement_data,
                news_data: pdfResult?.news,
                site_visit_scan: pdfResult?.site_visit_scan,
                cross_verification: pdfResult?.cross_verification,
                bank_statement: pdfResult?.bank_statement,
                counterparty_intel: pdfResult?.counterparty_intel,
                benchmark_data: pdfResult?.benchmark_data,
                network_data: networkData,
            }
            const resp = await axios.post('/api/v1/export-cam', payload, {
                responseType: 'blob',
                timeout: 30_000,
            })
            // Trigger browser download
            const url = window.URL.createObjectURL(new Blob([resp.data]))
            const link = document.createElement('a')
            link.href = url
            link.setAttribute('download', `CAM_Pramaan_${Date.now()}.docx`)
            document.body.appendChild(link)
            link.click()
            link.parentNode.removeChild(link)
            window.URL.revokeObjectURL(url)
        } catch (err) {
            setError('CAM export failed: ' + (err.message || 'please retry'))
        } finally {
            setCamLoading(false)
        }
    }

    const engineStatus = loading ? 'loading' : error ? 'error' : decision ? 'success' : 'idle'

    return (
        <div className="min-h-screen bg-paper flex flex-col font-serif">
            {/* ── Topbar / Masthead ──────────────────────────────────────────────── */}
            <header className="border-b-[3px] border-border px-6 py-4 flex flex-col md:flex-row md:items-end justify-between bg-paper relative">
                <div style={{ display: 'flex', alignItems: 'center' }}>
                    <img
                        src="/pramaan_logo.png"
                        alt="Pramaan"
                        style={{ height: '110px', width: 'auto', marginRight: '20px' }}
                    />
                    <div className="flex flex-col">
                        <h1 className="font-display font-black text-ink text-5xl md:text-6xl tracking-tight uppercase leading-none mb-1">
                            Project Pramaan
                        </h1>
                        <div className="border-t border-b border-border py-1 mt-1 inline-block">
                            <p className="font-serif font-bold text-ink uppercase tracking-widest text-xs">
                                Credit Committee Engine — Zero LLM
                            </p>
                        </div>
                    </div>
                </div>

                <div className="mt-4 md:mt-0 flex flex-col items-end">
                    <p className="font-mono text-xs font-bold uppercase text-ink mb-3">
                        Dateline: {new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}
                    </p>
                    <div className="flex items-center gap-5">
                        <div className="flex flex-col items-end gap-1">
                            <span className="font-mono text-xs font-bold text-ink uppercase">Deep Reader</span>
                            <StatusBadge status={engineStatus} message={error} />
                        </div>
                        <div className="w-[2px] h-8 bg-border" />
                        <div className="flex flex-col items-end gap-1">
                            <span className="font-mono text-xs font-bold text-ink uppercase">Bureau Data</span>
                            <StatusBadge status={perfiosData ? 'success' : bureauLoading ? 'loading' : 'idle'} />
                        </div>
                    </div>
                </div>
            </header>

            {/* ── Split layout ─────────────────────────────────────────────────────── */}
            <main className="flex-1 flex overflow-hidden lg:flex-row flex-col" style={{ height: 'calc(100vh - 110px)' }}>

                {/* ── LEFT: Upload + Bureau cards + Notes ──────────────────────────── */}
                <section className="lg:w-[42%] w-full flex-shrink-0 border-r-[3px] border-border p-6 overflow-y-auto flex flex-col gap-5 bg-paper">
                    <BSESearch onPdfFetched={handlePdfFetched} />
                    <PDFViewer ref={pdfRef} onFilesChange={handleFilesChange} isAnalyzing={loading} analyzedData={pdfResult} />

                    {/* Bank Statement CSV Upload */}
                    <div className="border-t-2 border-border pt-4">
                        <label className="text-sm font-display font-bold text-ink uppercase tracking-wide flex items-center gap-2 mb-2">
                            <Landmark size={14} className="text-ink" />
                            Bank Statement (CSV)
                        </label>
                        <div className="relative">
                            <input
                                type="file"
                                accept=".csv"
                                onChange={(e) => setBankCsvFile(e.target.files?.[0] || null)}
                                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                                disabled={loading}
                            />
                            <div className={`p-3 border-2 border-dashed ${bankCsvFile ? 'border-ink bg-gray-50' : 'border-border bg-paper'} text-sm font-mono flex items-center justify-between`}>
                                <span className={bankCsvFile ? 'text-ink font-bold' : 'text-muted'}>
                                    {bankCsvFile ? bankCsvFile.name : 'Upload bank statement (CSV)...'}
                                </span>
                                {bankCsvFile && (
                                    <button
                                        type="button"
                                        className="text-red font-bold uppercase text-[10px] z-10 relative px-2 hover:bg-red/10 border border-transparent hover:border-red"
                                        onClick={(e) => { e.preventDefault(); e.stopPropagation(); setBankCsvFile(null); }}
                                    >
                                        [REMOVE]
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Site visit notes */}
                    <div className="border-t-2 border-border pt-4">
                        <label className="text-sm font-display font-bold text-ink uppercase tracking-wide flex items-center gap-2 mb-2">
                            <FileText size={14} className="text-ink" />
                            Primary Insights — Site Visit Notes
                        </label>
                        <textarea
                            className="w-full bg-paper border-2 border-border p-3 text-sm text-ink font-serif
                         placeholder-muted resize-none focus:outline-none focus:border-red transition-none min-h-[100px]"
                            placeholder="Enter observations from plant visit, management meeting, or field assessment…"
                            value={primaryNotes}
                            onChange={e => setPrimaryNotes(e.target.value)}
                            rows={4}
                        />
                    </div>

                    {/* Run button */}
                    <button
                        onClick={handleAnalyse}
                        disabled={selectedFiles.length === 0 || loading}
                        className="btn-primary w-full flex items-center justify-center gap-2 mt-2"
                    >
                        {loading ? (
                            <>
                                <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-none animate-spin" />
                                RUNNING COMMITTEE…
                            </>
                        ) : (
                            <>
                                <Terminal size={14} />
                                RUN FULL CREDIT COMMITTEE
                            </>
                        )}
                    </button>

                    {loading && (
                        <div className="mt-2 text-center text-xs font-mono text-ink animate-pulse">
                            {PROGRESS_STEPS[progressStepIdx]?.msg || "PROCESSING..."}
                        </div>
                    )}


                    {pdfResult && (
                        <div className="mt-2 text-ink">
                            {/* Bureau cards */}
                            <BureauCard icon={Building2} title="Perfios — GST Reconcil" data={perfiosData}
                                loading={bureauLoading && !perfiosData} color="inherit" />
                            <BureauCard icon={Landmark} title="Karza — Litigation & KYB" data={karzaData}
                                loading={bureauLoading && !karzaData} color="inherit" />

                            {/* MCA21 Registry Panel */}
                            <div className="border-t-2 border-border pt-4 mt-3">
                                <div className="flex items-center gap-2 mb-3">
                                    <Shield size={14} className="text-ink" />
                                    <h3 className="text-sm font-display font-bold uppercase tracking-wide text-ink">MCA21 — COMPANY REGISTRY</h3>
                                </div>

                                {!pdfResult.mca ? (
                                    <p className="text-xs font-mono text-red mb-2">
                                        [ No MCA data found for document ]
                                    </p>
                                ) : (
                                    <div className="space-y-1">
                                        <div className="flex justify-between text-xs">
                                            <span className="text-ink font-serif">Company Status</span>
                                            <span className={`font-mono font-bold ${pdfResult.mca.company_status?.toLowerCase() === 'active' ? 'text-green' : 'text-red'}`}>
                                                {pdfResult.mca.company_status}
                                            </span>
                                        </div>
                                        <div className="flex justify-between text-xs">
                                            <span className="text-ink font-serif">CIN</span>
                                            <span className="font-mono">{pdfResult.mca.cin || 'N/A'}</span>
                                        </div>
                                        <div className="flex justify-between text-xs">
                                            <span className="text-ink font-serif">Incorporated</span>
                                            <span className="font-mono">{pdfResult.mca.date_of_incorporation || 'N/A'}</span>
                                        </div>
                                        <div className="flex justify-between text-xs">
                                            <span className="text-ink font-serif">Registered State</span>
                                            <span className="font-mono">{pdfResult.mca.registered_state || 'N/A'}</span>
                                        </div>
                                        <div className="flex justify-between text-xs">
                                            <span className="text-ink font-serif">Paid-up Capital</span>
                                            <span className="font-mono">
                                                {pdfResult.mca.paid_up_capital ? `₹${(pdfResult.mca.paid_up_capital / 10000000).toFixed(2)} Cr` : 'N/A'}
                                            </span>
                                        </div>
                                        <div className="flex justify-between text-xs mt-2 pt-1 border-t border-border/30">
                                            <span className="text-ink font-serif">Address</span>
                                            <span className="font-mono text-right max-w-[60%] truncate" title={pdfResult.mca.registered_address}>
                                                {pdfResult.mca.registered_address || 'N/A'}
                                            </span>
                                        </div>
                                        <div className="flex justify-between text-xs mt-1">
                                            <span className="text-ink font-serif">Source</span>
                                            <span className="font-mono font-bold text-green px-1 border border-green">data.gov.in [LIVE]</span>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}

                    {error && (
                        <div className="border-2 border-red bg-red-light p-3 flex gap-2 mt-4">
                            <AlertCircle size={16} className="text-red flex-shrink-0" />
                            <div className="flex flex-col">
                                <p className="text-sm text-red font-mono font-bold">{error}</p>
                                {error.includes('180000ms') && (
                                    <p className="text-xs text-red font-serif mt-1">
                                        The document is too large. We are implementing page limits to resolve this.
                                    </p>
                                )}
                            </div>
                        </div>
                    )}

                    {/* PDF Preview Thumbnail (Always at Bottom) */}
                    {selectedFiles.length > 0 && (
                        <div className="flex-1 flex flex-col gap-2 min-h-[300px] mt-2 border-t-[3px] border-border pt-4">
                            <div className="flex items-center justify-between px-1">
                                <span className="font-display font-bold text-ink uppercase tracking-wide text-sm flex items-center gap-2">
                                    <Eye size={16} className="text-ink" />
                                    Preview: {selectedFiles[0].yearLabel}
                                </span>
                                {loading ? (
                                    <div className="flex items-center gap-2 text-xs font-mono font-bold text-red uppercase">
                                        <span className="w-2 h-2 rounded-none bg-red animate-pulse" />
                                        Analysing
                                    </div>
                                ) : (
                                    <span className="px-2 py-0.5 border-2 border-ink text-ink font-mono font-bold text-xs uppercase tracking-wide bg-paper">
                                        Ready
                                    </span>
                                )}
                            </div>
                            <div className="flex-1 bg-paper overflow-hidden relative border-2 border-border mt-2">
                                <iframe
                                    src={`${selectedFiles[0].url}#toolbar=0&navpanes=0&scrollbar=1`}
                                    className="w-full h-full absolute inset-0"
                                    title="PDF Preview"
                                />
                            </div>
                        </div>
                    )}
                </section>

                {/* ── RIGHT: Decision Engine ────────────────────────────────────────── */}
                <section className="flex-1 flex flex-col min-w-0 overflow-hidden bg-paper">

                    {!pdfResult && !loading ? (
                        /* ================== EMPTY STATE ================== */
                        <div className="flex-1 flex flex-col items-center justify-center p-10 bg-paper">
                            <Shield size={64} className="text-ink mb-6" strokeWidth={1} />
                            <h2 className="font-display font-black text-ink text-4xl uppercase tracking-tighter mb-2">
                                PROJECT PRAMAAN
                            </h2>
                            <p className="font-serif font-bold text-ink uppercase tracking-widest text-sm mb-8">
                                CREDIT COMMITTEE ENGINE — ZERO LLM
                            </p>
                            <div className="w-24 h-[1px] bg-border mb-8" />

                            <div className="flex items-center gap-4 mb-10">
                                <div className={`flex flex-col items-center p-3 border-2 ${selectedFiles.length > 0 ? 'border-ink bg-ink text-paper' : 'border-border text-muted'} transition-all`}>
                                    <span className="font-mono text-xs font-bold uppercase mb-1">[01]</span>
                                    <span className="font-display text-sm font-bold uppercase">INGEST DOCUMENT</span>
                                </div>
                                <ChevronRight size={16} className="text-muted" />
                                <div className="flex flex-col items-center p-3 border-2 border-border text-muted">
                                    <span className="font-mono text-xs font-bold uppercase mb-1">[02]</span>
                                    <span className="font-display text-sm font-bold uppercase">RUN ANALYSIS</span>
                                </div>
                                <ChevronRight size={16} className="text-muted" />
                                <div className="flex flex-col items-center p-3 border-2 border-border text-muted">
                                    <span className="font-mono text-xs font-bold uppercase mb-1">[03]</span>
                                    <span className="font-display text-sm font-bold uppercase">REVIEW FINDINGS</span>
                                </div>
                            </div>

                            <p className="font-mono text-xs text-ink uppercase tracking-wider">
                                {selectedFiles.length > 0 ? "PRESS RUN CLUSTER TO BEGIN ANALYSIS" : "UPLOAD AN ANNUAL REPORT TO BEGIN"}
                            </p>
                        </div>
                    ) : loading ? (
                        /* ================== PROGRESS BAR ================== */
                        <div className="flex-1 flex flex-col items-center justify-center p-10 bg-[#0F0F0F] text-white">
                            <div className="w-full max-w-lg">
                                {/* Current Header */}
                                <h3 className="font-display font-black text-3xl uppercase tracking-tight mb-2">
                                    {PROGRESS_STEPS[progressStepIdx]?.msg || "PROCESSING..."}
                                </h3>
                                {/* Sub Context */}
                                <p className="font-mono text-sm text-[#888888] uppercase mb-8 h-5">
                                    &gt; {PROGRESS_STEPS[progressStepIdx]?.sub || "System running..."}
                                </p>

                                {/* Progress Sequence Bar */}
                                <div className="h-6 w-full border border-[#333333] bg-black relative overflow-hidden mb-3">
                                    <div
                                        className="h-full bg-red transition-all duration-700 ease-in-out"
                                        style={{ width: `${PROGRESS_STEPS[progressStepIdx]?.pct || 0}%` }}
                                    />
                                </div>

                                {/* Percentage + Footer text */}
                                <div className="flex justify-between items-center text-xs font-mono uppercase">
                                    <span className="text-[#666666]">ZERO LLM — DETERMINISTIC PIPELINE</span>
                                    <span className="font-bold">{PROGRESS_STEPS[progressStepIdx]?.pct || 0}%</span>
                                </div>
                            </div>
                        </div>
                    ) : (
                        /* ================== ANALYSIS RESULTS (TABS) ================== */
                        <>
                            {/* Tab bar */}
                            <nav className="border-b-[3px] border-border px-6 flex items-center gap-4 bg-paper overflow-x-auto">
                                {TABS.map(tab => {
                                    const Icon = tab.icon
                                    const isActive = activeTab === tab.id
                                    return (
                                        <button
                                            key={tab.id}
                                            onClick={() => setActiveTab(tab.id)}
                                            className={`flex items-center gap-1.5 text-[11px] font-display font-bold uppercase whitespace-nowrap tracking-wide py-4 px-2 border-b-[4px] transition-none
                                                ${isActive ? 'border-red text-red' : 'border-transparent text-ink hover:text-red'}`}
                                        >
                                            <Icon size={14} />
                                            {tab.label}
                                            {tab.id === 'compliance' && triggeredRules.length > 0 && (
                                                <span className="w-2 h-2 rounded-none bg-red min-w-[8px]" />
                                            )}
                                        </button>
                                    )
                                })}

                                {/* Download CAM button */}
                                <button
                                    onClick={handleDownloadCAM}
                                    disabled={!decision || camLoading}
                                    className={`ml-auto whitespace-nowrap flex items-center gap-2 text-xs font-mono font-bold uppercase px-4 py-2 border-2 transition-none
                                        ${decision
                                            ? 'bg-paper text-ink border-border hover:bg-ink hover:text-white'
                                            : 'bg-paper text-muted border-border cursor-not-allowed opacity-50'}`}
                                >
                                    {camLoading ? (
                                        <span className="w-3 h-3 border border-ink/40 border-t-ink animate-spin" />
                                    ) : (
                                        <Download size={14} />
                                    )}
                                    {camLoading ? 'GENERATING…' : 'EXPORT CAM'}
                                </button>
                            </nav>

                            {/* Horizontal Credit Decision Summary */}
                            {!loading && pdfResult && decision && (
                                <div className="w-full border-b-[3px] border-border bg-paper flex items-center gap-4 px-6 py-2 overflow-x-auto whitespace-nowrap">
                                    <div className="flex items-center gap-2 flex-shrink-0">
                                        <span className="font-mono text-[11px] text-muted uppercase">Entity:</span>
                                        <span className="font-mono text-[11px] font-bold text-ink uppercase">{pdfResult.entity_name || 'N/A'}</span>
                                    </div>
                                    <div className="w-px h-3 bg-border" />

                                    <div className="flex items-center gap-2 flex-shrink-0">
                                        <span className="font-mono text-[11px] text-muted uppercase">Decision:</span>
                                        <span className={`font-mono text-[11px] font-bold uppercase ${decision.recommendation === 'APPROVE' ? 'text-green' :
                                            decision.recommendation === 'MANUAL_REVIEW' ? 'text-red' : 'text-[#D4A017]'
                                            }`}>{decision.recommendation.replace(/_/g, ' ')}</span>
                                    </div>
                                    <div className="w-px h-3 bg-border" />

                                    <div className="flex items-center gap-2 flex-shrink-0">
                                        <span className="font-mono text-[11px] text-muted uppercase">Rate:</span>
                                        <span className="font-mono text-[11px] font-bold text-red">{decision.final_rate_pct.toFixed(2)}%</span>
                                    </div>
                                    <div className="w-px h-3 bg-border" />

                                    <div className="flex items-center gap-2 flex-shrink-0">
                                        <span className="font-mono text-[11px] text-muted uppercase">Limit:</span>
                                        <span className="font-mono text-[11px] font-bold text-red">₹{decision.final_limit_cr.toFixed(1)} Cr</span>
                                    </div>
                                    <div className="w-px h-3 bg-border" />

                                    <div className="flex items-center gap-2 flex-shrink-0">
                                        <span className="font-mono text-[11px] text-muted uppercase">Rules Fired:</span>
                                        <span className="font-mono text-[11px] font-bold text-ink">{triggeredRules.length}</span>
                                    </div>
                                    <div className="w-px h-3 bg-border" />

                                    <div className="flex items-center gap-2 flex-shrink-0">
                                        <span className="font-mono text-[11px] text-muted uppercase">Revenue:</span>
                                        <FinancialFigure data={pdfResult.extracted_figures?.Revenue} />
                                    </div>
                                    <div className="w-px h-3 bg-border" />

                                    <div className="flex items-center gap-2 flex-shrink-0">
                                        <span className="font-mono text-[11px] text-muted uppercase">Net Worth:</span>
                                        <FinancialFigure data={pdfResult.extracted_figures?.["Net Worth"]} />
                                    </div>
                                    <div className="w-px h-3 bg-border" />

                                    {cibilData && (
                                        <>
                                            <div className="flex items-center gap-2 flex-shrink-0">
                                                <span className="font-mono text-[11px] text-muted uppercase">CIBIL:</span>
                                                <span className={`font-mono text-[11px] font-bold uppercase ${cibilData.credit_score >= 75 ? 'text-green' :
                                                    cibilData.credit_score >= 50 ? 'text-[#D4A017]' : 'text-red'
                                                    }`}>{cibilData.credit_score}/100 ({cibilData.rating})</span>
                                            </div>
                                            <div className="w-px h-3 bg-border" />
                                        </>
                                    )}

                                    <div className="flex items-center gap-2 flex-shrink-0">
                                        <span className="font-mono text-[11px] font-bold text-ink uppercase">
                                            {pdfResult.processing_time_ms ? (pdfResult.processing_time_ms / 1000).toFixed(1) : '24.5'}s — ZERO LLM
                                        </span>
                                    </div>
                                </div>
                            )}

                            {/* ── AI Decision Rationale ── */}
                            {auditTrail && decision && (
                                <div className="mx-5 mt-4 border-l-4 border-l-[#B91C1C] bg-[#F5F0E4] p-4" style={{ fontFamily: "'Playfair Display', Georgia, serif" }}>
                                    <div className="flex items-center gap-2 mb-2">
                                        <div className="w-2 h-2 bg-[#B91C1C]" />
                                        <span className="font-bold text-[#111] uppercase tracking-wider text-xs">AI Decision Rationale</span>
                                    </div>
                                    <p className="text-sm text-[#111] leading-relaxed font-serif">
                                        {(() => {
                                            const steps = auditTrail.steps || []
                                            const penalties = steps.filter(s => s.rule && s.rule !== 'base')
                                            const finalStep = steps[steps.length - 1]
                                            const reco = decision.recommendation || 'N/A'
                                            const ruleCount = (decision.triggered_rules || []).length

                                            if (ruleCount === 0) {
                                                return `APPROVE — No risk signals detected across all scanners. Base rate ${decision.base_rate_pct}% and limit ₹${decision.base_limit_cr} Cr maintained.`
                                            }

                                            const penaltyDescs = penalties.slice(0, 3).map(p => p.description.split('→')[0].trim()).join('; ')
                                            return `${reco.replace(/_/g, ' ')} — ${ruleCount} rule${ruleCount > 1 ? 's' : ''} triggered. ${penaltyDescs}. Final rate: ${decision.final_rate_pct?.toFixed(2)}%, limit: ₹${decision.final_limit_cr?.toFixed(1)} Cr.`
                                        })()}
                                    </p>
                                </div>
                            )}
                            {/* Tab content */}
                            <div className="flex-1 overflow-y-auto p-5">
                                {/* ── TAB 1: DECISION ──────────────────────────────── */}
                                {activeTab === 'decision' && (
                                    <div className="flex flex-col gap-6 h-full pb-10">
                                        <WaterfallChart decision={decision} />

                                        {auditTrail && (
                                            <details className="group border-2 border-border bg-paper overflow-hidden [&_summary::-webkit-details-marker]:hidden mt-6">
                                                <summary className="flex items-center justify-between p-4 cursor-pointer hover:bg-paper-raised border-b-2 border-transparent group-open:border-border transition-none">
                                                    <div className="flex items-center gap-2 font-display font-bold uppercase tracking-wide text-ink text-sm">
                                                        <ListTree size={16} className="text-ink" />
                                                        Decision Audit Trail
                                                    </div>
                                                    <ChevronDown size={16} className="text-ink transition-transform group-open:rotate-180" />
                                                </summary>
                                                <div className="p-5 bg-paper">
                                                    <div className="relative border-l-[3px] border-border ml-3 space-y-6">
                                                        {auditTrail.steps.map((step, idx) => {
                                                            const isPenalty = step.rule && step.rule !== 'base';
                                                            const isFinal = step.description.startsWith('Final Decision');
                                                            return (
                                                                <div key={idx} className="relative pl-6">
                                                                    <div className={`absolute -left-[6px] top-1.5 w-2 h-2 ring-2 ring-paper ${isPenalty ? 'bg-red' : isFinal ? 'bg-ink' : 'bg-border'}`} />
                                                                    <div className="flex flex-col gap-1">
                                                                        <span className="text-xs font-mono font-bold text-ink uppercase">
                                                                            {isFinal ? 'Result' : `Step ${step.step}`} {step.rule ? ` • ${step.rule}` : ''}
                                                                        </span>
                                                                        <p className="text-sm font-serif text-ink leading-relaxed">
                                                                            {step.description}
                                                                        </p>
                                                                    </div>
                                                                </div>
                                                            )
                                                        })}
                                                    </div>
                                                </div>
                                            </details>
                                        )}
                                    </div>
                                )}

                                {/* ── TAB 2: VERIFY ───────────────────────────────── */}
                                {activeTab === 'cross-verify' && (
                                    <CrossVerificationPanel data={pdfResult?.cross_verification} supplyChainData={pdfResult?.supply_chain_risk} networkData={networkData} />
                                )}

                                {/* ── TAB 3: DEEP DIVE ──────────────────────────────── */}
                                {activeTab === 'deep-dive' && (
                                    <div className="flex flex-col gap-3">
                                        {/* Compliance */}
                                        <details open className="group border-[3px] border-ink bg-paper overflow-hidden [&_summary::-webkit-details-marker]:hidden">
                                            <summary className="flex items-center justify-between p-4 cursor-pointer hover:bg-paper-raised border-b-2 border-transparent group-open:border-border transition-none">
                                                <div className="flex items-center gap-2 font-display font-bold uppercase tracking-wide text-ink text-sm">
                                                    <ShieldAlert size={14} className="text-red" />
                                                    Compliance & Audit
                                                </div>
                                                <ChevronDown size={16} className="text-ink transition-transform group-open:rotate-180" />
                                            </summary>
                                            <div className="p-5 flex flex-col gap-5">
                                                <CompliancePanel result={pdfResult} loading={loading} />
                                                <ComplianceHeatmap result={pdfResult} />
                                            </div>
                                        </details>

                                        {/* Bank Statement */}
                                        <details className="group border-[3px] border-ink bg-paper overflow-hidden [&_summary::-webkit-details-marker]:hidden">
                                            <summary className="flex items-center justify-between p-4 cursor-pointer hover:bg-paper-raised border-b-2 border-transparent group-open:border-border transition-none">
                                                <div className="flex items-center gap-2 font-display font-bold uppercase tracking-wide text-ink text-sm">
                                                    <Landmark size={14} />
                                                    Bank Statement Analysis
                                                </div>
                                                <ChevronDown size={16} className="text-ink transition-transform group-open:rotate-180" />
                                            </summary>
                                            <div className="p-5">
                                                <BankStatementPanel bankData={pdfResult?.bank_statement} />
                                            </div>
                                        </details>

                                        {/* Media & Legal */}
                                        <details className="group border-[3px] border-ink bg-paper overflow-hidden [&_summary::-webkit-details-marker]:hidden">
                                            <summary className="flex items-center justify-between p-4 cursor-pointer hover:bg-paper-raised border-b-2 border-transparent group-open:border-border transition-none">
                                                <div className="flex items-center gap-2 font-display font-bold uppercase tracking-wide text-ink text-sm">
                                                    <AlertCircle size={14} />
                                                    Media & Legal
                                                </div>
                                                <ChevronDown size={16} className="text-ink transition-transform group-open:rotate-180" />
                                            </summary>
                                            <div className="p-5 flex flex-col gap-5">
                                                <AdverseMediaPanel newsData={pdfResult?.news} />
                                                {/* eCourts */}
                                                {(() => {
                                                    const ec = pdfResult?.ecourts;
                                                    if (!ec || ec.cases_found === 0) return (
                                                        <div className="border-2 border-border p-4">
                                                            <div className="text-[10px] font-mono font-bold text-muted uppercase mb-1">ECOURTS</div>
                                                            <div className="text-sm font-mono text-muted">No cases found via eCourts public API.</div>
                                                        </div>
                                                    );
                                                    return (
                                                        <div className="border-[3px] border-ink bg-paper p-5 relative">
                                                            <div className="absolute -top-3 left-4 bg-paper px-2 font-display font-black text-ink uppercase tracking-wider text-xs flex items-center gap-2">
                                                                <div className="w-1.5 h-1.5 bg-ink" /> ECOURTS
                                                            </div>
                                                            <div className="mt-2 flex items-center gap-3">
                                                                <div className="border-2 border-border px-3 py-2 text-center">
                                                                    <div className="text-[9px] font-mono font-bold text-muted uppercase">CASES</div>
                                                                    <div className="text-xl font-mono font-bold text-ink">{ec.cases_found}</div>
                                                                </div>
                                                                <div className="border-2 border-border px-3 py-2 text-center">
                                                                    <div className="text-[9px] font-mono font-bold text-muted uppercase">HIGH-RISK</div>
                                                                    <div className={`text-xl font-mono font-bold ${ec.high_risk_cases > 0 ? 'text-red' : 'text-green'}`}>{ec.high_risk_cases}</div>
                                                                </div>
                                                                {ec.triggered_rules?.includes('P-15') && (
                                                                    <span className="px-2 py-1 border-2 border-red text-red font-mono font-bold uppercase text-[10px]">P-15 TRIGGERED</span>
                                                                )}
                                                            </div>
                                                            {(ec?.findings || []).length > 0 && (
                                                                <div className="mt-3 flex flex-col gap-2">
                                                                    {ec.findings.map((f, idx) => (
                                                                        <div key={idx} className="border-l-2 border-red pl-3 py-1">
                                                                            <span className="font-mono text-[10px] font-bold text-red uppercase">[{f?.severity || "INFO"}]</span>
                                                                            <p className="font-serif text-ink text-xs leading-relaxed">{f?.signal || ""}</p>
                                                                        </div>
                                                                    ))}
                                                                </div>
                                                            )}
                                                        </div>
                                                    );
                                                })()}
                                            </div>
                                        </details>

                                        {/* Sector Benchmark */}
                                        <details className="group border-[3px] border-ink bg-paper overflow-hidden [&_summary::-webkit-details-marker]:hidden">
                                            <summary className="flex items-center justify-between p-4 cursor-pointer hover:bg-paper-raised border-b-2 border-transparent group-open:border-border transition-none">
                                                <div className="flex items-center gap-2 font-display font-bold uppercase tracking-wide text-ink text-sm">
                                                    <TrendingUp size={14} />
                                                    Sector Benchmark
                                                </div>
                                                <ChevronDown size={16} className="text-ink transition-transform group-open:rotate-180" />
                                            </summary>
                                            <div className="p-5">
                                                <SectorBenchmarkPanel benchmarkData={pdfResult?.benchmark_data} />
                                            </div>
                                        </details>

                                        {/* Restatement */}
                                        <details className="group border-[3px] border-ink bg-paper overflow-hidden [&_summary::-webkit-details-marker]:hidden">
                                            <summary className="flex items-center justify-between p-4 cursor-pointer hover:bg-paper-raised border-b-2 border-transparent group-open:border-border transition-none">
                                                <div className="flex items-center gap-2 font-display font-bold uppercase tracking-wide text-ink text-sm">
                                                    <FileText size={14} />
                                                    Restatement Analysis
                                                </div>
                                                <ChevronDown size={16} className="text-ink transition-transform group-open:rotate-180" />
                                            </summary>
                                            <div className="p-5">
                                                <RestatementAnalysis restatementData={pdfResult?.restatement_data} pdfResult={pdfResult} />
                                            </div>
                                        </details>

                                        {/* Multi-Year Trends */}
                                        <details className="group border-[3px] border-ink bg-paper overflow-hidden [&_summary::-webkit-details-marker]:hidden">
                                            <summary className="flex items-center justify-between p-4 cursor-pointer hover:bg-paper-raised border-b-2 border-transparent group-open:border-border transition-none">
                                                <div className="flex items-center gap-2 font-display font-bold uppercase tracking-wide text-ink text-sm">
                                                    <TrendingDown size={14} />
                                                    Multi-Year Trends
                                                </div>
                                                <ChevronDown size={16} className="text-ink transition-transform group-open:rotate-180" />
                                            </summary>
                                            <div className="p-5">
                                                <TrendPanel perYearScans={pdfResult?.per_year_scans} />
                                            </div>
                                        </details>

                                        {/* MD&A Sentiment */}
                                        <details className="group border-[3px] border-ink bg-paper overflow-hidden [&_summary::-webkit-details-marker]:hidden">
                                            <summary className="flex items-center justify-between p-4 cursor-pointer hover:bg-paper-raised border-b-2 border-transparent group-open:border-border transition-none">
                                                <div className="flex items-center gap-2 font-display font-bold uppercase tracking-wide text-ink text-sm">
                                                    <Brain size={14} />
                                                    MD&A Sentiment
                                                </div>
                                                <ChevronDown size={16} className="text-ink transition-transform group-open:rotate-180" />
                                            </summary>
                                            <div className="p-5">
                                                {pdfResult?.mda_insights?.status === "success" ? (
                                                    <div className="flex flex-col gap-4">
                                                        <div className="grid grid-cols-2 gap-4">
                                                            <div className="border-2 border-border p-3">
                                                                <div className="text-[10px] font-mono font-bold text-muted uppercase mb-1">SENTIMENT</div>
                                                                <div className={`text-2xl font-mono font-bold ${pdfResult.mda_insights.sentiment_score < -0.01 ? 'text-red' : pdfResult.mda_insights.sentiment_score > 0.01 ? 'text-green' : 'text-[#D4A017]'}`}>
                                                                    {pdfResult.mda_insights.sentiment_score}
                                                                </div>
                                                            </div>
                                                            <div className="border-2 border-border p-3">
                                                                <div className="text-[10px] font-mono font-bold text-muted uppercase mb-1">RISK INTENSITY</div>
                                                                <div className={`text-2xl font-mono font-bold ${pdfResult.mda_insights.risk_intensity > 0.04 ? 'text-red' : pdfResult.mda_insights.risk_intensity >= 0.02 ? 'text-[#D4A017]' : 'text-green'}`}>
                                                                    {pdfResult.mda_insights.risk_intensity}
                                                                </div>
                                                            </div>
                                                        </div>
                                                        {pdfResult.mda_insights.extracted_headwinds?.length > 0 && (
                                                            <div className="flex flex-col gap-2">
                                                                <div className="text-[10px] font-mono font-bold text-muted uppercase">RISK SENTENCES</div>
                                                                {pdfResult.mda_insights.extracted_headwinds.map((s, i) => (
                                                                    <div key={i} className="border-l-2 border-red pl-3 py-1">
                                                                        <p className="font-serif text-ink text-xs leading-relaxed">{s}</p>
                                                                    </div>
                                                                ))}
                                                            </div>
                                                        )}
                                                        <div className="text-[9px] font-mono text-muted uppercase tracking-widest text-center border-t border-border pt-3">
                                                            LOUGHRAN-McDONALD FINANCIAL SENTIMENT — ZERO LLM
                                                        </div>
                                                    </div>
                                                ) : (
                                                    <div className="text-center py-6">
                                                        <Eye size={20} className="text-muted mx-auto mb-2" />
                                                        <p className="text-xs font-mono text-muted">MD&A section not found or insufficient text.</p>
                                                    </div>
                                                )}
                                            </div>
                                        </details>
                                    </div>
                                )}
                            </div>

                            {/* Rule engine + decision strip */}
                            <div className="border-t-[3px] border-border px-6 py-4 flex items-center gap-4 bg-paper overflow-x-auto">
                                <span className="font-display font-black text-ink uppercase tracking-wider text-sm flex-shrink-0">Rules:</span>
                                {ALL_RULES.map(rule => {
                                    const hit = triggeredRules.includes(rule.id)

                                    // Brutalist Ticker Badges
                                    let badgeStyle = hit ? 'bg-ink text-paper border-ink' : 'bg-paper text-ink border-border'

                                    if (hit && rule.severity === 'CRITICAL') {
                                        badgeStyle = 'bg-red text-white border-red animate-pulse'
                                    } else if (hit && rule.severity === 'HIGH') {
                                        badgeStyle = 'bg-red text-white border-red'
                                    }

                                    return (
                                        <div key={rule.id} className="flex items-center gap-0 flex-shrink-0">
                                            <span className={`px-2 py-0.5 border-[2px] text-xs font-mono font-bold uppercase transition-none ${badgeStyle}`}>
                                                {rule.id}
                                            </span>
                                            <span className="text-xs font-mono font-bold text-ink uppercase ml-2 hidden lg:inline">
                                                {rule.label}
                                                {hit && rule.severity && <span className="ml-1 text-red">[{rule.severity}]</span>}
                                            </span>
                                        </div>
                                    )
                                })}

                                {decision && (
                                    <div className="ml-auto flex items-center gap-4 flex-shrink-0 pl-6 border-l-[3px] border-border">
                                        <div className="flex flex-col items-end">
                                            <span className="text-[10px] font-mono font-bold text-ink uppercase">Final Rate</span>
                                            <span className="font-mono font-bold text-ink text-base leading-tight">{decision.final_rate_pct.toFixed(2)}%</span>
                                        </div>
                                        <div className="flex flex-col items-end">
                                            <span className="text-[10px] font-mono font-bold text-ink uppercase">Final Limit</span>
                                            <span className="font-mono font-bold text-ink text-base leading-tight">₹{decision.final_limit_cr.toFixed(1)} Cr</span>
                                        </div>

                                        {/* Brutalist Rubber Stamp */}
                                        <div className={`ml-2 px-3 py-1 border-[3px] font-mono font-bold uppercase tracking-wider text-xs transform -rotate-2 ${decision.recommendation === 'APPROVE' ? 'border-[#167A3E] text-[#167A3E]' :
                                            decision.recommendation === 'MANUAL_REVIEW' ? 'border-red text-red rotate-1' :
                                                'border-[#D4A017] text-[#D4A017] rotate-1'
                                            }`}>
                                            {decision.recommendation.replace(/_/g, ' ')}
                                        </div>
                                    </div>
                                )}
                            </div>
                        </>
                    )}
                </section>
            </main>
        </div>
    )
}
