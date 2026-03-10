import { ShieldCheck, ShieldQuestion, AlertTriangle, CheckCircle, XCircle, HelpCircle, ChevronDown, ArrowRightLeft, TrendingDown, TrendingUp, Network, Layers, Target, Flag } from 'lucide-react'
import NetworkAnalysis from './NetworkAnalysis'
import SupplyChainRiskPanel from './SupplyChainRiskPanel'

const STATUS_CONFIG = {
    MATCH: { label: 'VERIFIED', color: 'text-green', bg: 'bg-green/10', border: 'border-green', icon: CheckCircle },
    MISMATCH: { label: 'CONTRADICTED', color: 'text-red', bg: 'bg-red/10', border: 'border-red', icon: XCircle },
    PARTIAL_MATCH: { label: 'PARTIAL', color: 'text-yellow', bg: 'bg-yellow/10', border: 'border-yellow', icon: AlertTriangle },
    UNVERIFIABLE: { label: 'UNVERIFIABLE', color: 'text-muted', bg: 'bg-muted/10', border: 'border-border', icon: HelpCircle },
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

function parseGstDetail(detail) {
    const lines = detail.split('\n').filter(l => l.trim())
    const observations = lines.filter(l => l.startsWith('•')).map(l => l.replace('• ', ''))
    const conclusionIdx = lines.findIndex(l => l.startsWith('Conclusion:'))
    const conclusion = conclusionIdx >= 0 ? lines.slice(conclusionIdx + 1).join(' ').trim() : ''
    return { observations, conclusion }
}

// ── GST Reconciliation Card — compact square layout ──────────────────────
function GstReconciliationCard({ verification }) {
    const check = verification.checks[0]
    if (!check) return null

    const { gstTurnover, bankCredits, variance } = parseGstFinding(check.finding)
    const { observations, conclusion } = parseGstDetail(check.detail || '')
    const status = check.status
    const isUnverifiable = status === 'UNVERIFIABLE'

    const accent = status === 'MISMATCH' ? 'red' : status === 'PARTIAL_MATCH' ? 'yellow' : status === 'MATCH' ? 'green' : 'muted'
    const borderClass = `border-${accent}`
    const bgClass = `bg-${accent}/5`
    const textClass = `text-${accent}`

    if (isUnverifiable) {
        return (
            <div className="border-2 border-border bg-paper p-4 relative">
                <div className="absolute -top-2.5 left-3 bg-paper px-2 font-display font-black text-muted uppercase tracking-wider text-[11px] flex items-center gap-1.5">
                    <ArrowRightLeft size={12} />
                    GST-BANK RECONCILIATION
                </div>
                <div className="flex items-center gap-2 mt-1">
                    <HelpCircle size={16} className="text-muted shrink-0" />
                    <p className="text-xs font-serif text-muted">{check.finding}</p>
                </div>
                <p className="text-[10px] font-serif text-muted mt-1">{check.detail}</p>
            </div>
        )
    }

    const absVar = Math.min(Math.abs(variance || 0), 50)
    const barWidth = Math.max(absVar * 2, 4)

    return (
        <div className={`border-[3px] ${borderClass} ${bgClass} p-4 relative`}>
            {/* Title badge */}
            <div className={`absolute -top-2.5 left-3 ${bgClass} bg-paper px-2 font-display font-black uppercase tracking-wider text-[11px] flex items-center gap-1.5 ${textClass}`}>
                <ArrowRightLeft size={12} />
                GST-BANK RECONCILIATION
                <StatusBadge status={status} />
            </div>

            {/* Compact 3-column: square-ish boxes */}
            <div className="grid grid-cols-3 gap-2 mt-2">
                <div className="border-2 border-ink/20 bg-paper p-2.5 text-center aspect-[4/3] flex flex-col items-center justify-center">
                    <div className="text-[9px] font-mono font-bold text-muted uppercase">GST Turnover</div>
                    <div className="text-lg font-mono font-black text-ink leading-tight mt-1">
                        {gstTurnover !== null ? `₹${gstTurnover.toFixed(2)}` : '—'}
                    </div>
                    <div className="text-[9px] font-mono text-muted">Crore</div>
                </div>

                <div className={`border-2 ${borderClass} bg-paper p-2.5 text-center aspect-[4/3] flex flex-col items-center justify-center`}>
                    <div className="text-[9px] font-mono font-bold text-muted uppercase">Variance</div>
                    <div className={`text-xl font-mono font-black ${textClass} flex items-center gap-0.5 leading-tight mt-1`}>
                        {variance !== null ? (
                            <>
                                {variance > 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                                {variance > 0 ? '+' : ''}{variance}%
                            </>
                        ) : '—'}
                    </div>
                    {variance !== null && (
                        <div className="w-3/4 h-1 bg-ink/10 mt-1.5 relative">
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

                <div className="border-2 border-ink/20 bg-paper p-2.5 text-center aspect-[4/3] flex flex-col items-center justify-center">
                    <div className="text-[9px] font-mono font-bold text-muted uppercase">Bank Credits</div>
                    <div className="text-lg font-mono font-black text-ink leading-tight mt-1">
                        {bankCredits !== null ? `₹${bankCredits.toFixed(2)}` : '—'}
                    </div>
                    <div className="text-[9px] font-mono text-muted">Crore</div>
                </div>
            </div>

            {/* Compact observations */}
            {(observations.length > 0 || conclusion) && (
                <div className="mt-2 border-t border-ink/10 pt-2">
                    {observations.length > 0 && (
                        <div className="flex flex-col gap-0.5">
                            {observations.map((obs, i) => (
                                <div key={i} className="flex items-start gap-1.5">
                                    <div className={`w-1 h-1 mt-1 bg-${accent} shrink-0`} />
                                    <span className="text-[10px] font-mono text-ink">{obs}</span>
                                </div>
                            ))}
                        </div>
                    )}
                    {conclusion && (
                        <p className={`text-[10px] font-serif font-bold ${textClass} border-l-2 ${borderClass} pl-2 mt-1`}>
                            {conclusion}
                        </p>
                    )}
                </div>
            )}

            {status === 'MISMATCH' && (
                <div className="mt-2 flex items-center gap-2">
                    <span className="px-1.5 py-0.5 text-[9px] font-mono font-bold text-red border border-red bg-red/10">P-33</span>
                    <span className="text-[9px] font-mono text-muted">+125bps, Limit -20%</span>
                </div>
            )}
        </div>
    )
}

// ── Loan Purpose Verification — Claimed vs Ground Truth ─────────────────
function LoanPurposeCard({ data }) {
    if (!data || data.status === 'not_checked') return null

    const status = data.overall_status
    const accent = status === 'MISMATCH' ? 'red' : status === 'PARTIAL_MISMATCH' ? 'yellow' : 'green'
    const borderClass = `border-${accent}`
    const bgClass = `bg-${accent}/5`
    const textClass = `text-${accent}`
    const statusLabel = status === 'MISMATCH' ? 'FUND DIVERSION DETECTED' : status === 'PARTIAL_MISMATCH' ? 'PARTIAL CONCERNS' : 'ALIGNED'

    return (
        <div className={`border-[3px] ${borderClass} ${bgClass} p-4 relative`}>
            {/* Title badge */}
            <div className={`absolute -top-2.5 left-3 ${bgClass} bg-paper px-2 font-display font-black uppercase tracking-wider text-[11px] flex items-center gap-1.5 ${textClass}`}>
                <Target size={12} />
                LOAN PURPOSE VERIFICATION
                <span className={`inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-mono font-bold uppercase ${textClass} ${bgClass} border border-current`}>
                    {statusLabel}
                </span>
            </div>

            {/* Claimed vs Ground Truth — side by side */}
            <div className="grid grid-cols-2 gap-3 mt-3">
                {/* LEFT: Claimed Truth */}
                <div className="border-2 border-ink/20 bg-paper p-3">
                    <div className="text-[9px] font-mono font-bold text-muted uppercase mb-2 flex items-center gap-1">
                        <div className="w-1.5 h-1.5 bg-ink" /> CLAIMED PURPOSE
                    </div>
                    <div className="text-sm font-mono font-bold text-ink leading-snug">
                        {data.stated_purpose}
                    </div>
                    {data.mca_alignment && (
                        <div className={`mt-2 flex items-start gap-1.5 ${data.mca_alignment.aligned ? 'text-green' : 'text-yellow'}`}>
                            {data.mca_alignment.aligned ? <CheckCircle size={11} className="mt-0.5 shrink-0" /> : <AlertTriangle size={11} className="mt-0.5 shrink-0" />}
                            <span className="text-[10px] font-mono">{data.mca_alignment.detail}</span>
                        </div>
                    )}
                </div>

                {/* RIGHT: Ground Truth (fund utilization) */}
                <div className={`border-2 ${borderClass} bg-paper p-3`}>
                    <div className={`text-[9px] font-mono font-bold uppercase mb-2 flex items-center gap-1 ${textClass}`}>
                        <div className={`w-1.5 h-1.5 bg-${accent}`} /> ACTUAL FUND UTILIZATION
                    </div>
                    <div className="flex flex-col gap-1">
                        {(data.fund_utilization || []).map((item, i) => {
                            const isRisky = item.category.includes('Related Party') || item.category.includes('Real Estate') || item.category.includes('Unclassified')
                            return (
                                <div key={i} className="flex items-center gap-2">
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center justify-between">
                                            <span className={`text-[10px] font-mono truncate ${isRisky ? 'font-bold text-red' : 'text-ink'}`}>
                                                {item.category}
                                            </span>
                                            <span className={`text-[10px] font-mono font-bold ml-1 shrink-0 ${isRisky ? 'text-red' : 'text-ink'}`}>
                                                {item.percentage}%
                                            </span>
                                        </div>
                                        <div className="w-full h-1 bg-ink/10 mt-0.5">
                                            <div
                                                className={`h-full ${isRisky ? 'bg-red' : 'bg-ink/30'}`}
                                                style={{ width: `${Math.min(item.percentage * 2, 100)}%` }}
                                            />
                                        </div>
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                </div>
            </div>

            {/* Flags */}
            {data.flags && data.flags.length > 0 && (
                <div className="mt-3 border-t border-ink/10 pt-2 flex flex-col gap-1.5">
                    {data.flags.map((flag, i) => (
                        <div key={i} className="flex items-start gap-2">
                            <Flag size={10} className={`mt-0.5 shrink-0 ${flag.severity === 'HIGH' ? 'text-red' : 'text-yellow'}`} />
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                    <span className={`px-1.5 py-0.5 text-[8px] font-mono font-bold uppercase ${flag.severity === 'HIGH' ? 'text-red border border-red bg-red/10' : 'text-yellow border border-yellow bg-yellow/10'}`}>
                                        {flag.severity}
                                    </span>
                                    <span className="text-[9px] font-mono font-bold text-ink uppercase">
                                        {flag.flag.replace(/_/g, ' ')}
                                    </span>
                                </div>
                                <p className="text-[10px] font-mono text-ink mt-0.5">{flag.detail}</p>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Verdict */}
            {data.verdict && (
                <div className={`mt-2 border-l-2 ${borderClass} pl-2`}>
                    <p className={`text-[10px] font-serif font-bold ${textClass}`}>{data.verdict}</p>
                </div>
            )}

            {/* Rule trigger */}
            {data.triggered_rules && data.triggered_rules.length > 0 && (
                <div className="mt-2 flex items-center gap-2">
                    {data.triggered_rules.map(rule => (
                        <span key={rule} className="px-1.5 py-0.5 text-[9px] font-mono font-bold text-red border border-red bg-red/10">{rule}</span>
                    ))}
                </div>
            )}
        </div>
    )
}

export default function CrossVerificationPanel({ data, supplyChainData, networkData, loanPurposeData }) {
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

    const gstVerification = verifications.find(v => v.claim_id === 'gst_bank_reconciliation')
    const otherVerifications = verifications.filter(v => v.claim_id !== 'gst_bank_reconciliation')
    const hasMismatch = otherVerifications.some(v => v.overall_status === 'MISMATCH')

    return (
        <div className="flex flex-col gap-4">
            {/* ── COMPACT SUMMARY CHIPS ─────────────────────────────────────── */}
            <div className="flex items-center gap-3 flex-wrap">
                <div className="flex items-center gap-1.5 px-3 py-1.5 border-2 border-green/40 bg-green/5">
                    <CheckCircle size={12} className="text-green" />
                    <span className="text-[10px] font-mono font-bold text-green uppercase">{summary.verified || 0} Verified</span>
                </div>
                <div className="flex items-center gap-1.5 px-3 py-1.5 border-2 border-red/40 bg-red/5">
                    <XCircle size={12} className="text-red" />
                    <span className="text-[10px] font-mono font-bold text-red uppercase">{summary.mismatched || 0} Contradicted</span>
                </div>
                <div className="flex items-center gap-1.5 px-3 py-1.5 border-2 border-yellow/40 bg-yellow/5">
                    <AlertTriangle size={12} className="text-yellow" />
                    <span className="text-[10px] font-mono font-bold text-yellow uppercase">{summary.partial || 0} Partial</span>
                </div>
                <div className="flex items-center gap-1.5 px-3 py-1.5 border-2 border-border">
                    <HelpCircle size={12} className="text-muted" />
                    <span className="text-[10px] font-mono font-bold text-muted uppercase">{summary.unverifiable || 0} Unverifiable</span>
                </div>
                {triggered_rules.length > 0 && (
                    <div className="flex gap-1.5 ml-auto">
                        {triggered_rules.map(rule => (
                            <span key={rule} className="px-2 py-1 text-[10px] font-mono font-bold text-red border-2 border-red bg-red/10">
                                {rule}
                            </span>
                        ))}
                    </div>
                )}
            </div>

            {/* ── GST RECONCILIATION HERO ────────────────────────────────────── */}
            {gstVerification && <GstReconciliationCard verification={gstVerification} />}

            {/* ── LOAN PURPOSE VERIFICATION ────────────────────────────────────── */}
            {loanPurposeData && <LoanPurposeCard data={loanPurposeData} />}

            {/* ── SUPPLY CHAIN RISK ──────────────────────────────────────────── */}
            {supplyChainData && (
                <details open className="group border-[3px] border-ink bg-paper overflow-hidden [&_summary::-webkit-details-marker]:hidden">
                    <summary className="flex items-center justify-between p-3 cursor-pointer hover:bg-paper-raised border-b-2 border-transparent group-open:border-border transition-none">
                        <div className="flex items-center gap-2 font-display font-bold uppercase tracking-wide text-ink text-xs">
                            <Layers size={13} />
                            Supply Chain Risk
                        </div>
                        <ChevronDown size={14} className="text-ink transition-transform group-open:rotate-180" />
                    </summary>
                    <div className="p-4">
                        <SupplyChainRiskPanel data={supplyChainData} />
                    </div>
                </details>
            )}

            {/* ── NETWORK ANALYSIS ───────────────────────────────────────────── */}
            {networkData && (
                <details open className="group border-[3px] border-ink bg-paper overflow-hidden [&_summary::-webkit-details-marker]:hidden">
                    <summary className="flex items-center justify-between p-3 cursor-pointer hover:bg-paper-raised border-b-2 border-transparent group-open:border-border transition-none">
                        <div className="flex items-center gap-2 font-display font-bold uppercase tracking-wide text-ink text-xs">
                            <Network size={13} />
                            Counterparty Network
                        </div>
                        <ChevronDown size={14} className="text-ink transition-transform group-open:rotate-180" />
                    </summary>
                    <div className="p-4">
                        <NetworkAnalysis data={networkData} />
                    </div>
                </details>
            )}

            {/* ── CLAIM VERIFICATIONS — single collapsible ───────────────────── */}
            {otherVerifications.length > 0 && (
                <details className="group border-2 border-border bg-paper overflow-hidden [&_summary::-webkit-details-marker]:hidden" open={hasMismatch}>
                    <summary className="flex items-center justify-between p-3 cursor-pointer hover:bg-paper-raised border-b border-transparent group-open:border-border transition-none">
                        <div className="flex items-center gap-2 font-display font-bold uppercase tracking-wide text-ink text-xs">
                            <ShieldCheck size={13} />
                            Claim Verifications
                            <span className="px-1.5 py-0.5 text-[9px] font-mono font-bold bg-ink/10 text-ink">{otherVerifications.length}</span>
                        </div>
                        <ChevronDown size={14} className="text-ink transition-transform group-open:rotate-180" />
                    </summary>
                    <div className="divide-y divide-border">
                        {otherVerifications.map((v) => (
                            <div key={v.claim_id} className="p-3 hover:bg-paper-raised">
                                <div className="flex items-center justify-between gap-3">
                                    <div className="flex items-center gap-2 flex-1 min-w-0">
                                        <div className={`w-1 h-6 shrink-0 ${v.overall_status === 'MISMATCH' ? 'bg-red' : v.overall_status === 'PARTIAL_MATCH' ? 'bg-yellow' : v.overall_status === 'MATCH' ? 'bg-green' : 'bg-muted'}`} />
                                        <div className="min-w-0">
                                            <span className="text-[9px] font-mono font-bold text-muted uppercase tracking-wide block">
                                                {v.claim_id.replace(/_/g, ' ')}
                                            </span>
                                            <span className="text-xs font-serif text-ink truncate block">
                                                {v.claim_text}
                                            </span>
                                        </div>
                                    </div>
                                    <StatusBadge status={v.overall_status} />
                                </div>
                                {/* Show detail for MISMATCH items inline */}
                                {v.overall_status === 'MISMATCH' && v.checks?.[0] && (
                                    <div className="mt-2 ml-3 pl-3 border-l-2 border-red">
                                        <p className="text-[10px] font-mono text-red">{v.checks[0].finding}</p>
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </details>
            )}

            {/* ── METHODOLOGY ────────────────────────────────────────────────── */}
            <div className="border border-border bg-paper px-3 py-2">
                <p className="text-[9px] font-mono text-muted uppercase leading-relaxed">
                    Deterministic cross-verification — no LLM. MATCH = confirmed. CONTRADICTED = contradicted. PARTIAL = minor discrepancy. UNVERIFIABLE = insufficient data.
                </p>
            </div>
        </div>
    )
}
