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
import { useState, useCallback } from 'react'
import axios from 'axios'
import {
    Brain, Shield, ChevronRight, AlertCircle, Download,
    BarChart2, Map, ShieldAlert, Terminal, Cpu, TrendingDown,
    FileText, Building2, Landmark, Network, ListTree, ChevronDown
} from 'lucide-react'
import PDFViewer from './components/PDFViewer'
import WaterfallChart from './components/WaterfallChart'
import ComplianceHeatmap from './components/HallucinationHeatmap'
import CompliancePanel from './components/CompliancePanel'
import NetworkAnalysis from './components/NetworkAnalysis'
import RestatementAnalysis from './components/RestatementAnalysis'

// ── Client-side penalty orchestrator (mirrors backend logic) ─────────────────
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

    const RULES = {
        'P-01': { name: 'Ghost Input Trap', bps: 100, cut: 10, manual: false, trigger: 'GSTR-2A vs 3B mismatch > 15% (Perfios)' },
        'P-03': { name: 'Statutory Default / Audit Qual', bps: 150, cut: 20, manual: false, trigger: 'CARO 2020 Clause (vii) / auditor qualification' },
        'P-04': { name: 'Emphasis of Matter', bps: 75, cut: 0, manual: true, trigger: 'Going concern or material uncertainty flagged' },
        'P-06': { name: 'Circular Fraud Detected', bps: 0, cut: 50, manual: false, trigger: 'Circular trading loop detected via network graph (Acme → Vertex → Nova → Acme)' },
        'P-09': { name: 'Financial Restatement', bps: 200, cut: 40, manual: true, trigger: 'Prior year financial comparative figures restated by >2%' },
        'P-10': { name: 'Auditor Rotation / Change', bps: 75, cut: 10, manual: true, trigger: 'Change in statutory auditor detected across reporting periods' },
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

// ── Tab config ────────────────────────────────────────────────────────────────
const TABS = [
    { id: 'compliance', label: 'Compliance Scan', icon: ShieldAlert },
    { id: 'waterfall', label: 'Rate Waterfall', icon: BarChart2 },
    { id: 'heatmap', label: 'Evidence Grid', icon: Map },
    { id: 'network', label: 'Network Analysis', icon: Network },
    { id: 'restatement', label: 'Restatement Analysis', icon: TrendingDown },
]

const ALL_RULES = [
    { id: 'P-01', label: 'Ghost Input' },
    { id: 'P-02', label: 'Family Web' },
    { id: 'P-03', label: 'Stat. Default' },
    { id: 'P-04', label: 'Emphasis' },
    { id: 'P-06', label: 'Circ. Fraud' },
    { id: 'P-09', label: 'Restatement', severity: 'CRITICAL' },
    { id: 'P-10', label: 'Auditor Change', severity: 'HIGH' },
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
                    .filter(([k]) => !['status', 'provider', 'metadata', 'active_litigations'].includes(k))
                    .slice(0, 4)
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
    const [primaryNotes, setPrimaryNotes] = useState('')
    const [loading, setLoading] = useState(false)
    const [camLoading, setCamLoading] = useState(false)
    const [error, setError] = useState(null)
    const [activeTab, setActiveTab] = useState('compliance')
    const [bureauLoading, setBureauLoading] = useState(false)
    const [progressMessage, setProgressMessage] = useState('')

    const handleFilesChange = useCallback((files) => {
        setSelectedFiles(files)
        setPdfResult(null)
        setAuditTrail(null)
        setError(null)
    }, [])

    // ── Compute unified decision from all sources ──────────────────────────────
    const decision = (pdfResult || perfiosData || networkData)
        ? orchestrateDecision(pdfResult, perfiosData, networkData)
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
        setAuditTrail(null)
        setActiveTab('compliance')
        setProgressMessage('Scanning document structure...')

        const progressInterval = setInterval(() => {
            setProgressMessage(prev => {
                if (prev === 'Scanning document structure...') return 'Running compliance checks...'
                if (prev === 'Running compliance checks...') return 'Extracting financial figures...'
                if (prev === 'Extracting financial figures...') return 'Computing penalties...'
                return prev
            })
        }, 30000)

        try {
            // Run all three in parallel
            const formData = new FormData()
            selectedFiles.forEach((f) => {
                // e.g., yearLabel might be "FY24" -> "file_fy24"
                const fieldName = `file_${f.yearLabel.toLowerCase().replace(/[^a-z0-9]/g, '')}`
                formData.append(fieldName, f.file)
            })

            const [pdfResp, perfiosResp, karzaResp, networkResp] = await Promise.all([
                axios.post('/api/v1/analyze-report', formData, {
                    headers: { 'Content-Type': 'multipart/form-data' },
                    timeout: 180_000,
                }),
                axios.get('/api/v1/mock/perfios', { timeout: 5_000 }),
                axios.get('/api/v1/mock/karza', { timeout: 5_000 }),
                axios.get('/api/v1/mock/network-graph', { timeout: 5_000 }),
            ])

            setPdfResult(pdfResp.data)
            setPerfiosData(perfiosResp.data)
            setKarzaData(karzaResp.data)
            setNetworkData(networkResp.data)

            // Auto-jump to waterfall if any rule triggered
            const pendingDecision = orchestrateDecision(
                pdfResp.data,
                perfiosResp.data,
                networkResp.data,
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
                setTimeout(() => setActiveTab('waterfall'), 1100)
            }
        } catch (err) {
            const msg = err.response?.data?.detail || err.message || 'Unexpected error'
            setError(msg)
        } finally {
            clearInterval(progressInterval)
            setProgressMessage('')
            setLoading(false)
            setBureauLoading(false)
        }
    }

    // ── Download CAM ───────────────────────────────────────────────────────────
    const handleDownloadCAM = async () => {
        if (!decision) return
        setCamLoading(true)
        try {
            const payload = {
                entity_name: karzaData?.entity || 'Acme Steels Pvt Ltd',
                primary_insights: primaryNotes,
                pdf_scan: pdfResult,
                perfios: perfiosData,
                karza: karzaData,
                decision: decision,
                triggered_rules: triggeredRules,
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
                            <span className="font-mono text-xs font-bold text-ink uppercase">Bureau Mock</span>
                            <StatusBadge status={perfiosData ? 'success' : bureauLoading ? 'loading' : 'idle'} />
                        </div>
                    </div>
                </div>
            </header>

            {/* ── Split layout ─────────────────────────────────────────────────────── */}
            <main className="flex-1 flex overflow-hidden lg:flex-row flex-col" style={{ height: 'calc(100vh - 110px)' }}>

                {/* ── LEFT: Upload + Bureau cards + Notes ──────────────────────────── */}
                <section className="lg:w-[42%] w-full flex-shrink-0 border-r-[3px] border-border p-6 overflow-y-auto flex flex-col gap-5 bg-paper">
                    <PDFViewer onFilesChange={handleFilesChange} isAnalyzing={loading} />

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

                    {loading && progressMessage && (
                        <div className="mt-2 text-center text-xs font-mono text-ink animate-pulse">
                            {progressMessage}
                        </div>
                    )}

                    <div className="mt-2">
                        {/* Bureau cards */}
                        <BureauCard icon={Building2} title="Perfios — GST Reconcil" data={perfiosData}
                            loading={bureauLoading && !perfiosData} color="inherit" />
                        <BureauCard icon={Landmark} title="Karza — Litigation & KYB" data={karzaData}
                            loading={bureauLoading && !karzaData} color="inherit" />
                    </div>

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
                </section>

                {/* ── RIGHT: Decision Engine ────────────────────────────────────────── */}
                <section className="flex-1 flex flex-col min-w-0 overflow-hidden bg-paper">
                    {/* Tab bar */}
                    <nav className="border-b-[3px] border-border px-6 flex items-center gap-4 bg-paper">
                        {TABS.map(tab => {
                            const Icon = tab.icon
                            const isActive = activeTab === tab.id
                            return (
                                <button
                                    key={tab.id}
                                    onClick={() => setActiveTab(tab.id)}
                                    className={`flex items-center gap-2 text-sm font-display font-bold uppercase tracking-wide py-4 border-b-[4px] transition-none
                    ${isActive ? 'border-red text-red' : 'border-transparent text-ink hover:text-red'}`}
                                >
                                    <Icon size={14} />
                                    {tab.label}
                                    {tab.id === 'compliance' && triggeredRules.length > 0 && (
                                        <span className="w-2 h-2 rounded-none bg-red" />
                                    )}
                                </button>
                            )
                        })}

                        {/* Download CAM button */}
                        <button
                            onClick={handleDownloadCAM}
                            disabled={!decision || camLoading}
                            className={`ml-auto flex items-center gap-2 text-xs font-mono font-bold uppercase px-4 py-2 border-2 transition-none
                          ${decision
                                    ? 'bg-paper text-ink border-border hover:bg-ink hover:text-white'
                                    : 'bg-paper text-muted border-border cursor-not-allowed opacity-50'}`}
                        >
                            {camLoading ? (
                                <span className="w-3 h-3 border border-ink/40 border-t-ink animate-spin" />
                            ) : (
                                <Download size={14} />
                            )}
                            {camLoading ? 'GENERATING…' : 'DOWNLOAD CAM'}
                        </button>
                    </nav>

                    {/* Tab content */}
                    <div className="flex-1 overflow-y-auto p-5">
                        {activeTab === 'compliance' && (
                            <CompliancePanel result={pdfResult} loading={loading} />
                        )}
                        {activeTab === 'waterfall' && (
                            <div className="flex flex-col gap-6 h-full pb-10">
                                <WaterfallChart decision={decision} triggeredRules={triggeredRules} />

                                {/* Decision Audit Trail Collapsible */}
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
                        {activeTab === 'heatmap' && (
                            <ComplianceHeatmap result={pdfResult} />
                        )}
                        {activeTab === 'network' && (
                            <NetworkAnalysis />
                        )}
                        {activeTab === 'restatement' && (
                            <RestatementAnalysis
                                restatementData={pdfResult?.restatement_data}
                                pdfResult={pdfResult}
                            />
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
                </section>
            </main>
        </div>
    )
}
