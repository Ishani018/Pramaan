import { ShieldCheck, ShieldAlert, ShieldQuestion, AlertTriangle, CheckCircle, XCircle, HelpCircle, ChevronDown, ArrowRightLeft, TrendingDown, TrendingUp } from 'lucide-react'
import NetworkAnalysis from './NetworkAnalysis'
import SupplyChainRiskPanel from './SupplyChainRiskPanel'

const STATUS_CONFIG = {
    MATCH: { label: 'VERIFIED', color: 'text-green', bg: 'bg-green/10', border: 'border-green', icon: CheckCircle },
    MISMATCH: { label: 'CONTRADICTED', color: 'text-red', bg: 'bg-red/10', border: 'border-red', icon: XCircle },
    PARTIAL_MATCH: { label: 'PARTIAL', color: 'text-yellow', bg: 'bg-yellow/10', border: 'border-yellow', icon: AlertTriangle },
    UNVERIFIABLE: { label: 'UNVERIFIABLE', color: 'text-muted', bg: 'bg-muted/10', border: 'border-border', icon: HelpCircle },
}

const SEVERITY_CONFIG = {
    HIGH: { label: 'HIGH', color: 'text-red', bg: 'bg-red/10' },
    MEDIUM: { label: 'MEDIUM', color: 'text-yellow', bg: 'bg-yellow/10' },
    LOW: { label: 'LOW', color: 'text-muted', bg: 'bg-muted/5' },
    INFO: { label: 'INFO', color: 'text-ink', bg: 'bg-paper' },
}

function StatusBadge({ status }) {
    const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.UNVERIFIABLE
    const Icon = cfg.icon
    return (
        <span className={`inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-mono font-bold uppercase ${cfg.color} ${cfg.bg} border border-current`}>
            <Icon size={10} />
            {cfg.label}
        </span>
    )
}

function SeverityBadge({ severity }) {
    const cfg = SEVERITY_CONFIG[severity] || SEVERITY_CONFIG.INFO
    return (
        <span className={`px-1.5 py-0.5 text-[9px] font-mono font-bold uppercase ${cfg.color} ${cfg.bg}`}>
            {cfg.label}
        </span>
    )
}

function SourceLabel({ name }) {
    return (
        <span className="text-[10px] font-mono font-bold text-muted uppercase tracking-wide">
            {name}
        </span>
    )
}

// ── Parse GST numbers from finding string ────────────────────────────────
function parseGstFinding(finding) {
    const gstMatch = finding.match(/GST Turnover:\s*₹([\d,.]+)\s*Cr/)
    const bankMatch = finding.match(/Bank Credits:\s*₹([\d,.]+)\s*Cr/)
    const varMatch = finding.match(/Variance:\s*([+-]?\d+)%/)
    return {
        gstTurnover: gstMatch ? parseFloat(gstMatch[1].replace(/,/g, '')) : null,
        bankCredits: bankMatch ? parseFloat(bankMatch[1].replace(/,/g, '')) : null,
        variance: varMatch ? parseInt(varMatch[1]) : null,
    }
}

// ── Parse observations from detail string ────────────────────────────────
function parseGstDetail(detail) {
    const lines = detail.split('\n').filter(l => l.trim())
    const observations = lines.filter(l => l.startsWith('•')).map(l => l.replace('• ', ''))
    const conclusionIdx = lines.findIndex(l => l.startsWith('Conclusion:'))
    const conclusion = conclusionIdx >= 0 ? lines.slice(conclusionIdx + 1).join(' ').trim() : ''
    return { observations, conclusion }
}

// ── GST Reconciliation Hero Card ─────────────────────────────────────────
function GstReconciliationCard({ verification }) {
    const check = verification.checks[0]
    if (!check) return null

    const { gstTurnover, bankCredits, variance } = parseGstFinding(check.finding)
    const { observations, conclusion } = parseGstDetail(check.detail || '')
    const status = check.status
    const isUnverifiable = status === 'UNVERIFIABLE'

    // Color scheme based on status
    const accent = status === 'MISMATCH' ? 'red' : status === 'PARTIAL_MATCH' ? 'yellow' : status === 'MATCH' ? 'green' : 'muted'
    const borderClass = `border-${accent}`
    const bgClass = `bg-${accent}/5`
    const textClass = `text-${accent}`

    // Variance bar width (capped at 50% for display, centered at 50%)
    const absVar = Math.min(Math.abs(variance || 0), 50)
    const barWidth = Math.max(absVar * 2, 4) // min 4% width for visibility

    if (isUnverifiable) {
        return (
            <div className="border-[3px] border-border bg-paper p-5 relative">
                <div className="absolute -top-3 left-4 bg-paper px-2 font-display font-black text-muted uppercase tracking-wider text-sm flex items-center gap-2">
                    <ArrowRightLeft size={14} />
                    GST-BANK RECONCILIATION
                </div>
                <div className="flex items-center gap-3 mt-2">
                    <HelpCircle size={20} className="text-muted" />
                    <p className="text-sm font-serif text-muted">{check.finding}</p>
                </div>
                <p className="text-xs font-serif text-muted mt-2">{check.detail}</p>
            </div>
        )
    }

    return (
        <div className={`border-[3px] ${borderClass} ${bgClass} p-5 relative`}>
            {/* Title badge */}
            <div className={`absolute -top-3 left-4 ${bgClass} bg-paper px-2 font-display font-black uppercase tracking-wider text-sm flex items-center gap-2 ${textClass}`}>
                <ArrowRightLeft size={14} />
                GST-BANK RECONCILIATION
                <StatusBadge status={status} />
            </div>

            {/* Big numbers row */}
            <div className="grid grid-cols-3 gap-3 mt-3">
                {/* GST Turnover */}
                <div className="border-2 border-ink/20 bg-paper p-3 text-center">
                    <div className="text-[10px] font-mono font-bold text-muted uppercase mb-1">GST Turnover</div>
                    <div className="text-xl font-mono font-black text-ink">
                        {gstTurnover !== null ? `₹${gstTurnover.toFixed(1)}` : '—'}
                    </div>
                    <div className="text-[10px] font-mono text-muted">Cr</div>
                </div>

                {/* Variance — center with visual indicator */}
                <div className={`border-2 ${borderClass} bg-paper p-3 text-center flex flex-col items-center justify-center`}>
                    <div className="text-[10px] font-mono font-bold text-muted uppercase mb-1">Variance</div>
                    <div className={`text-2xl font-mono font-black ${textClass} flex items-center gap-1`}>
                        {variance !== null ? (
                            <>
                                {variance > 0 ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
                                {variance > 0 ? '+' : ''}{variance}%
                            </>
                        ) : '—'}
                    </div>
                    {/* Variance bar */}
                    {variance !== null && (
                        <div className="w-full h-1.5 bg-ink/10 mt-2 relative">
                            <div className="absolute top-0 left-1/2 w-px h-full bg-ink/30" />
                            <div
                                className={`absolute top-0 h-full bg-${accent}`}
                                style={{
                                    left: variance < 0 ? `${50 - barWidth / 2}%` : '50%',
                                    width: `${barWidth / 2}%`,
                                }}
                            />
                        </div>
                    )}
                </div>

                {/* Bank Credits */}
                <div className="border-2 border-ink/20 bg-paper p-3 text-center">
                    <div className="text-[10px] font-mono font-bold text-muted uppercase mb-1">Bank Credits</div>
                    <div className="text-xl font-mono font-black text-ink">
                        {bankCredits !== null ? `₹${bankCredits.toFixed(1)}` : '—'}
                    </div>
                    <div className="text-[10px] font-mono text-muted">Cr</div>
                </div>
            </div>

            {/* Observations + Conclusion */}
            {(observations.length > 0 || conclusion) && (
                <div className="mt-3 border-t-2 border-ink/10 pt-3">
                    {observations.length > 0 && (
                        <div className="flex flex-col gap-1 mb-2">
                            {observations.map((obs, i) => (
                                <div key={i} className="flex items-start gap-2">
                                    <div className={`w-1 h-1 mt-1.5 bg-${accent} shrink-0`} />
                                    <span className="text-xs font-mono text-ink">{obs}</span>
                                </div>
                            ))}
                        </div>
                    )}
                    {conclusion && (
                        <p className={`text-xs font-serif font-bold ${textClass} border-l-2 ${borderClass} pl-2`}>
                            {conclusion}
                        </p>
                    )}
                </div>
            )}

            {/* Rule tag if P-33 */}
            {status === 'MISMATCH' && (
                <div className="mt-3 flex items-center gap-2">
                    <span className="px-2 py-0.5 text-[10px] font-mono font-bold text-red border border-red bg-red/10">
                        P-33: RECON-01
                    </span>
                    <span className="text-[10px] font-mono text-muted">GST-Bank Turnover Mismatch — Rate penalty 125bps, Limit -20%</span>
                </div>
            )}
        </div>
    )
}

export default function CrossVerificationPanel({ data, claims, supplyChainData, networkData }) {
    if (!data || !data.verifications || data.verifications.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center p-10 bg-paper border-[3px] border-ink">
                <ShieldQuestion size={48} className="text-muted mb-4" />
                <p className="text-sm font-serif text-muted">
                    Cross-verification not available. Upload an annual report to extract claims.
                </p>
            </div>
        )
    }

    const { verifications, summary = {}, triggered_rules = [] } = data

    // Separate GST reconciliation from other verifications
    const gstVerification = verifications.find(v => v.claim_id === 'gst_bank_reconciliation')
    const otherVerifications = verifications.filter(v => v.claim_id !== 'gst_bank_reconciliation')

    return (
        <div className="flex flex-col gap-6">
            {/* ── SUMMARY BAR ──────────────────────────────────────────────── */}
            <div className="border-[3px] border-ink bg-paper p-6 relative">
                <div className="absolute -top-3 left-4 bg-paper px-2 font-display font-black text-ink uppercase tracking-wider text-sm flex items-center gap-2">
                    <div className="w-2 h-2 bg-ink" />
                    CROSS-VERIFICATION SUMMARY
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-2">
                    <div className="border-2 border-green/30 p-3">
                        <div className="text-[10px] font-mono font-bold text-muted uppercase mb-1">Verified</div>
                        <div className="text-2xl font-mono font-bold text-green">{summary.verified || 0}</div>
                    </div>
                    <div className="border-2 border-red/30 p-3">
                        <div className="text-[10px] font-mono font-bold text-muted uppercase mb-1">Contradicted</div>
                        <div className="text-2xl font-mono font-bold text-red">{summary.mismatched || 0}</div>
                    </div>
                    <div className="border-2 border-yellow/30 p-3">
                        <div className="text-[10px] font-mono font-bold text-muted uppercase mb-1">Partial Match</div>
                        <div className="text-2xl font-mono font-bold text-yellow">{summary.partial || 0}</div>
                    </div>
                    <div className="border-2 border-border p-3">
                        <div className="text-[10px] font-mono font-bold text-muted uppercase mb-1">Unverifiable</div>
                        <div className="text-2xl font-mono font-bold text-muted">{summary.unverifiable || 0}</div>
                    </div>
                </div>

                {triggered_rules.length > 0 && (
                    <div className="mt-4 p-3 border-2 border-red bg-red/5">
                        <div className="text-[10px] font-mono font-bold text-red uppercase mb-1">
                            Penalty Rules Triggered by Cross-Verification
                        </div>
                        <div className="flex gap-2 flex-wrap">
                            {triggered_rules.map(rule => (
                                <span key={rule} className="px-2 py-1 text-xs font-mono font-bold text-red border border-red bg-red/10">
                                    {rule}
                                </span>
                            ))}
                        </div>
                    </div>
                )}
            </div>

            {/* ── GST RECONCILIATION HERO CARD ─────────────────────────────── */}
            {gstVerification && <GstReconciliationCard verification={gstVerification} />}

            {/* ── VERIFICATION CARDS ───────────────────────────────────────── */}
            {otherVerifications.map((v) => (
                <details key={v.claim_id} className="group border-[3px] border-ink bg-paper relative" open={v.overall_status === 'MISMATCH'}>
                    <summary className="flex items-center justify-between p-4 cursor-pointer hover:bg-paper-raised">
                        <div className="flex items-center gap-3 flex-1 min-w-0">
                            <div className={`w-1 h-8 ${v.overall_status === 'MISMATCH' ? 'bg-red' : v.overall_status === 'PARTIAL_MATCH' ? 'bg-yellow' : v.overall_status === 'MATCH' ? 'bg-green' : 'bg-muted'}`} />
                            <div className="flex flex-col min-w-0">
                                <span className="text-[10px] font-mono font-bold text-muted uppercase tracking-wide">
                                    {v.claim_id.replace(/_/g, ' ')}
                                </span>
                                <span className="text-sm font-serif text-ink truncate">
                                    {v.claim_text}
                                </span>
                            </div>
                        </div>
                        <div className="flex items-center gap-2 ml-3 shrink-0">
                            <StatusBadge status={v.overall_status} />
                            <ChevronDown size={14} className="text-muted group-open:rotate-180 transition-transform" />
                        </div>
                    </summary>

                    <div className="border-t-2 border-border">
                        {v.checks.map((check, ci) => (
                            <div key={ci} className={`p-4 ${ci > 0 ? 'border-t border-border' : ''}`}>
                                <div className="flex items-start justify-between gap-4">
                                    <div className="flex-1">
                                        <div className="flex items-center gap-2 mb-1">
                                            <SourceLabel name={check.source} />
                                            <StatusBadge status={check.status} />
                                            <SeverityBadge severity={check.severity} />
                                        </div>
                                        <p className="text-sm font-mono text-ink font-bold mb-1">
                                            {check.finding}
                                        </p>
                                        <p className="text-xs font-serif text-muted leading-relaxed whitespace-pre-wrap">
                                            {check.detail}
                                        </p>

                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </details>
            ))}

            {/* ── SUPPLY CHAIN RISK ────────────────────────────────────────── */}
            {supplyChainData && (
                <details className="group border-[3px] border-ink bg-paper overflow-hidden [&_summary::-webkit-details-marker]:hidden">
                    <summary className="flex items-center justify-between p-4 cursor-pointer hover:bg-paper-raised border-b-2 border-transparent group-open:border-border transition-none">
                        <div className="flex items-center gap-2 font-display font-bold uppercase tracking-wide text-ink text-sm">
                            <div className="w-2 h-2 bg-ink" />
                            Supply Chain Risk
                        </div>
                        <ChevronDown size={16} className="text-ink transition-transform group-open:rotate-180" />
                    </summary>
                    <div className="p-5">
                        <SupplyChainRiskPanel data={supplyChainData} />
                    </div>
                </details>
            )}

            {/* ── NETWORK ANALYSIS ─────────────────────────────────────────── */}
            {networkData && (
                <details className="group border-[3px] border-ink bg-paper overflow-hidden [&_summary::-webkit-details-marker]:hidden">
                    <summary className="flex items-center justify-between p-4 cursor-pointer hover:bg-paper-raised border-b-2 border-transparent group-open:border-border transition-none">
                        <div className="flex items-center gap-2 font-display font-bold uppercase tracking-wide text-ink text-sm">
                            <div className="w-2 h-2 bg-ink" />
                            Network Analysis
                        </div>
                        <ChevronDown size={16} className="text-ink transition-transform group-open:rotate-180" />
                    </summary>
                    <div className="p-5">
                        <NetworkAnalysis data={networkData} />
                    </div>
                </details>
            )}

            {/* ── METHODOLOGY NOTE ─────────────────────────────────────────── */}
            <div className="border-2 border-border bg-paper p-4">
                <p className="text-[10px] font-mono text-muted uppercase leading-relaxed">
                    Cross-verification is deterministic — each claim from the annual report is checked
                    against external data sources using threshold-based rules. No LLM calls are made.
                    MATCH = external data confirms claim. CONTRADICTED = external data contradicts claim.
                    PARTIAL = minor discrepancy. UNVERIFIABLE = insufficient external data.
                </p>
            </div>
        </div>
    )
}
