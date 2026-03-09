/**
 * DecisionPanel – Verdict + Penalty Breakdown
 * =============================================
 * Replaces the old Recharts waterfall with a clear, readable decision summary.
 * Shows: verdict banner → rate/limit impact → penalty table with human descriptions.
 */
import { AlertTriangle, CheckCircle, ShieldAlert, ArrowRight, TrendingUp, TrendingDown } from 'lucide-react'

const BASE_RATE = 9.0
const BASE_LIMIT = 10.0

const VERDICT_CONFIG = {
    APPROVE: {
        label: 'APPROVED',
        sublabel: 'No risk signals detected',
        color: 'text-green',
        bg: 'bg-green/10',
        border: 'border-green',
        icon: CheckCircle,
    },
    CONDITIONAL_APPROVAL: {
        label: 'CONDITIONAL',
        sublabel: 'Conditions must be met before disbursement',
        color: 'text-yellow',
        bg: 'bg-yellow/5',
        border: 'border-yellow',
        icon: AlertTriangle,
    },
    MANUAL_REVIEW: {
        label: 'MANUAL REVIEW',
        sublabel: 'Requires credit committee escalation',
        color: 'text-red',
        bg: 'bg-red/5',
        border: 'border-red',
        icon: ShieldAlert,
    },
}

function RateBar({ base, final, label }) {
    const max = Math.max(final, base) * 1.2
    const basePct = (base / max) * 100
    const finalPct = (final / max) * 100
    const increased = final > base

    return (
        <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono font-bold text-muted uppercase">{label}</span>
                <div className="flex items-center gap-2 text-xs font-mono">
                    <span className="text-muted">{base.toFixed(1)}</span>
                    <ArrowRight size={10} className="text-muted" />
                    <span className={`font-bold ${increased ? 'text-red' : 'text-green'}`}>
                        {final.toFixed(label === 'Interest Rate' ? 2 : 1)}
                        {label === 'Interest Rate' ? '%' : ' Cr'}
                    </span>
                </div>
            </div>
            <div className="relative h-3 bg-paper border border-border">
                <div
                    className="absolute inset-y-0 left-0 bg-muted/30"
                    style={{ width: `${basePct}%` }}
                />
                <div
                    className={`absolute inset-y-0 left-0 ${increased ? 'bg-red/70' : 'bg-green/70'}`}
                    style={{ width: `${finalPct}%` }}
                />
            </div>
        </div>
    )
}

export default function WaterfallChart({ decision }) {
    const rec = decision?.recommendation || 'APPROVE'
    const verdict = VERDICT_CONFIG[rec] || VERDICT_CONFIG.APPROVE
    const VerdictIcon = verdict.icon
    const penalties = decision?.applied_penalties || []
    const isLive = !!decision

    const finalRate = decision?.final_rate_pct ?? BASE_RATE
    const finalLimit = decision?.final_limit_cr ?? BASE_LIMIT
    const totalBps = penalties.reduce((sum, p) => sum + (p.rate_penalty_bps || 0), 0)

    return (
        <div className="flex flex-col gap-6">
            {/* ── VERDICT BANNER ─────────────────────────────────────── */}
            <div className={`border-[3px] ${verdict.border} ${verdict.bg} p-6 relative`}>
                <div className="absolute -top-3 left-4 bg-paper px-2 font-display font-black text-ink uppercase tracking-wider text-sm flex items-center gap-2">
                    <div className="w-2 h-2 bg-ink" />
                    CREDIT DECISION
                </div>

                <div className="flex items-center justify-between mt-1">
                    <div className="flex items-center gap-4">
                        <VerdictIcon size={36} className={verdict.color} strokeWidth={2.5} />
                        <div>
                            <div className={`text-2xl font-display font-black uppercase tracking-wide ${verdict.color}`}>
                                {verdict.label}
                            </div>
                            <p className="text-xs font-serif text-muted mt-0.5">
                                {isLive ? verdict.sublabel : 'Awaiting report upload'}
                            </p>
                        </div>
                    </div>

                    <div className="flex gap-6">
                        <div className="text-right">
                            <div className="text-[10px] font-mono font-bold text-muted uppercase">Rate</div>
                            <div className={`text-xl font-mono font-bold ${finalRate > BASE_RATE ? 'text-red' : 'text-green'}`}>
                                {finalRate.toFixed(2)}%
                            </div>
                        </div>
                        <div className="text-right">
                            <div className="text-[10px] font-mono font-bold text-muted uppercase">Limit</div>
                            <div className={`text-xl font-mono font-bold ${finalLimit < BASE_LIMIT ? 'text-red' : 'text-green'}`}>
                                ₹{finalLimit.toFixed(1)} Cr
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* ── RATE / LIMIT IMPACT BARS ────────────────────────────── */}
            <div className="border-[3px] border-ink bg-paper p-5 relative">
                <div className="absolute -top-3 left-4 bg-paper px-2 font-display font-black text-ink uppercase tracking-wider text-sm flex items-center gap-2">
                    <div className="w-2 h-2 bg-ink" />
                    IMPACT SUMMARY
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-2">
                    <RateBar base={BASE_RATE} final={finalRate} label="Interest Rate" />
                    <RateBar base={BASE_LIMIT} final={finalLimit} label="Credit Limit (₹ Cr)" />
                </div>

                <div className="grid grid-cols-3 gap-4 mt-5 pt-4 border-t-2 border-border">
                    <div className="text-center">
                        <div className="text-[10px] font-mono font-bold text-muted uppercase">Penalties</div>
                        <div className="text-lg font-mono font-bold text-ink">{penalties.length}</div>
                    </div>
                    <div className="text-center">
                        <div className="text-[10px] font-mono font-bold text-muted uppercase">Total BPS Added</div>
                        <div className={`text-lg font-mono font-bold ${totalBps > 0 ? 'text-red' : 'text-green'}`}>
                            {totalBps > 0 ? `+${totalBps}` : '0'}
                        </div>
                    </div>
                    <div className="text-center">
                        <div className="text-[10px] font-mono font-bold text-muted uppercase">Limit Cut</div>
                        <div className={`text-lg font-mono font-bold ${finalLimit < BASE_LIMIT ? 'text-red' : 'text-green'}`}>
                            {finalLimit < BASE_LIMIT ? `−${((1 - finalLimit / BASE_LIMIT) * 100).toFixed(0)}%` : 'None'}
                        </div>
                    </div>
                </div>
            </div>

            {/* ── PENALTY TABLE ───────────────────────────────────────── */}
            {penalties.length > 0 ? (
                <div className="border-[3px] border-ink bg-paper relative">
                    <div className="absolute -top-3 left-4 bg-paper px-2 font-display font-black text-ink uppercase tracking-wider text-sm flex items-center gap-2">
                        <div className="w-2 h-2 bg-red" />
                        TRIGGERED PENALTIES ({penalties.length})
                    </div>

                    <div className="divide-y-2 divide-border mt-2">
                        {penalties.map((p, i) => (
                            <div key={i} className="flex items-start gap-4 p-4">
                                <div className="flex-shrink-0 w-16 text-center">
                                    <span className="inline-block px-2 py-1 border-2 border-red text-red text-[10px] font-mono font-bold">
                                        {p.rule_id}
                                    </span>
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="text-sm font-mono font-bold text-ink">
                                        {(p.name || p.rule_id).replace(/^[A-Z]+-\d+:\s*/, '')}
                                    </div>
                                    <p className="text-xs font-serif text-muted mt-0.5 leading-relaxed">
                                        {p.trigger}
                                    </p>
                                </div>
                                <div className="flex-shrink-0 flex gap-3 items-center">
                                    <div className="flex items-center gap-1 text-red">
                                        <TrendingUp size={12} />
                                        <span className="text-xs font-mono font-bold">+{p.rate_penalty_bps}bps</span>
                                    </div>
                                    {p.limit_reduction_pct > 0 && (
                                        <div className="flex items-center gap-1 text-yellow">
                                            <TrendingDown size={12} />
                                            <span className="text-xs font-mono font-bold">−{p.limit_reduction_pct}%</span>
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            ) : isLive ? (
                <div className="border-[3px] border-green bg-green/5 p-6 flex items-center gap-3">
                    <CheckCircle size={20} className="text-green" />
                    <div>
                        <div className="text-sm font-mono font-bold text-green uppercase">Clean Report</div>
                        <p className="text-xs font-serif text-muted">No penalties triggered — all scanners passed.</p>
                    </div>
                </div>
            ) : null}
        </div>
    )
}
