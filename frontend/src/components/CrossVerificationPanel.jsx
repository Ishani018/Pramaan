import { ShieldCheck, ShieldAlert, ShieldQuestion, AlertTriangle, CheckCircle, XCircle, HelpCircle, ChevronDown } from 'lucide-react'

const STATUS_CONFIG = {
    MATCH:          { label: 'VERIFIED',      color: 'text-green',  bg: 'bg-green/10', border: 'border-green',  icon: CheckCircle },
    MISMATCH:       { label: 'CONTRADICTED',  color: 'text-red',    bg: 'bg-red/10',   border: 'border-red',    icon: XCircle },
    PARTIAL_MATCH:  { label: 'PARTIAL',       color: 'text-yellow', bg: 'bg-yellow/10', border: 'border-yellow', icon: AlertTriangle },
    UNVERIFIABLE:   { label: 'UNVERIFIABLE',  color: 'text-muted',  bg: 'bg-muted/10',  border: 'border-border', icon: HelpCircle },
}

const SEVERITY_CONFIG = {
    HIGH:   { label: 'HIGH',   color: 'text-red',    bg: 'bg-red/10' },
    MEDIUM: { label: 'MEDIUM', color: 'text-yellow', bg: 'bg-yellow/10' },
    LOW:    { label: 'LOW',    color: 'text-muted',  bg: 'bg-muted/5' },
    INFO:   { label: 'INFO',   color: 'text-ink',    bg: 'bg-paper' },
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

export default function CrossVerificationPanel({ data, claims }) {
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

            {/* ── VERIFICATION CARDS ───────────────────────────────────────── */}
            {verifications.map((v) => (
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
                                        <p className="text-xs font-serif text-muted leading-relaxed">
                                            {check.detail}
                                        </p>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </details>
            ))}

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
