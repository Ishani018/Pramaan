/**
 * WaterfallChart – Live Rule Engine Penalty Visualisation
 * ========================================================
 * Props:
 *   decision  – the `decision` object from the API response (optional, uses mock if null)
 *   triggered – the `triggered_rules` array from the API response
 *
 * The waterfall is computed dynamically from whatever the backend returns.
 * When the API returns caro_default_found=true or adverse_opinion_found=true,
 * P-03 appears as a triggered penalty bar.
 */
import { ComposedChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Cell, ResponsiveContainer, ReferenceLine } from 'recharts'
import { AlertTriangle, CheckCircle, Info } from 'lucide-react'

const BASE_RATE = 9.0
const BASE_LIMIT = 10.0

const RULE_META = {
    'P-01': { label: 'P-01 Ghost Input', color: '#EF4444', desc: 'GSTR-2A vs 3B mismatch > 15%' },
    'P-02': { label: 'P-02 Hidden Family', color: '#F97316', desc: 'RPT outflows to family-owned director firms' },
    'P-03': { label: 'P-03 Stat. Default', color: '#DC2626', desc: 'CARO 2020 Clause (vii) / Auditor qualification' },
    'P-04': { label: 'P-04 Power Mismatch', color: '#F59E0B', desc: 'Factory capacity vs power expenses – manual review' },
    'P-06': { label: 'P-06 Circular Fraud Detected', color: '#7C3AED', desc: 'Circular trading loop detected via network graph' },
}

const WATERFALL_LABELS = {
    "Base Rate": "Base Rate",
    "P-01": "GST-01",
    "P-02": "KYC-01",
    "P-03": "AUDIT-01",
    "P-04": "AUDIT-02",
    "P-06": "FRAUD-01",
    "P-07": "PRIMARY-01",
    "P-08": "BANK-01",
    "P-09": "RESTATE-01",
    "P-10": "AUDIT-03",
    "P-11": "RATING-01",
    "P-12": "RATING-02",
    "P-13": "MEDIA-01",
    "P-14": "CORP-01",
    "Final Rate": "Final Rate"
}

const MOCK_DECISION = {
    base_rate_pct: BASE_RATE,
    final_rate_pct: BASE_RATE,
    base_limit_cr: BASE_LIMIT,
    final_limit_cr: BASE_LIMIT,
    recommendation: 'APPROVE',
    applied_penalties: [],
}

const RECOMMENDATION_STYLES = {
    APPROVE: { color: 'text-success', bg: 'bg-success/10', border: 'border-success/20', icon: CheckCircle },
    CONDITIONAL_APPROVAL: { color: 'text-warn', bg: 'bg-warn/10', border: 'border-warn/20', icon: AlertTriangle },
    MANUAL_REVIEW: { color: 'text-danger', bg: 'bg-danger/10', border: 'border-danger/20', icon: AlertTriangle },
}

const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null
    const d = payload[0]?.payload
    return (
        <div className="glass p-3 text-xs w-60">
            <p className="font-semibold text-text mb-1">{d.label}</p>
            <p className="text-muted mb-1">{d.desc}</p>
            {d.ruleId && (
                <p className="text-warn text-xs">Rule: {d.ruleId}</p>
            )}
            <p className="text-accent mt-1 font-mono font-bold">
                {d.type === 'penalty' ? `+${d.bps} bps` : `${d.rate.toFixed(2)}%`}
            </p>
        </div>
    )
}

function buildChartData(decision) {
    if (!decision) return buildChartData(MOCK_DECISION)

    const rows = []

    // Base rate bar
    rows.push({
        label: 'Base Rate',
        rate: decision.base_rate_pct,
        invisible: 0,
        visible: decision.base_rate_pct,
        type: 'base',
        desc: 'Repo Rate + Bank Spread',
        ruleId: null,
        bps: 0,
    })

    // One bar per applied penalty
    let running = decision.base_rate_pct
    for (const p of (decision.applied_penalties || [])) {
        const bps = p.rate_penalty_bps || 0
        const meta = RULE_META[p.rule_id] || {}
        rows.push({
            label: meta.label || p.rule_id,
            rate: running + bps / 100,
            invisible: running,
            visible: bps / 100,
            type: 'penalty',
            desc: p.trigger || meta.desc || '',
            ruleId: p.rule_id,
            bps,
        })
        running += bps / 100
    }

    // Final rate bar
    rows.push({
        label: 'Final Rate',
        rate: decision.final_rate_pct,
        invisible: 0,
        visible: decision.final_rate_pct,
        type: 'final',
        desc: 'Recommended lending rate',
        ruleId: null,
        bps: 0,
    })

    return rows
}

const COLORS = { base: '#3B82F6', penalty: '#EF4444', final: '#10B981' }

const CustomLabel = ({ x, y, width, value, type, bps }) => {
    if (type !== 'penalty' || !bps) return null
    return (
        <text x={x + width / 2} y={y - 6} fill="#F59E0B" textAnchor="middle" fontSize={11} fontWeight={600}>
            +{bps}bps
        </text>
    )
}

export default function WaterfallChart({ decision, triggeredRules = [] }) {
    const chartData = buildChartData(decision)
    const rec = decision?.recommendation || 'APPROVE'
    const recStyle = RECOMMENDATION_STYLES[rec] || RECOMMENDATION_STYLES.APPROVE
    const RecIcon = recStyle.icon

    const isLive = !!decision

    return (
        <div className="glass p-5 animate-fade-in space-y-5">
            <div className="flex items-center justify-between">
                <div>
                    <h3 className="font-semibold text-text flex items-center gap-2">
                        Rate Waterfall
                        {isLive && (
                            <span className="badge bg-success/15 text-success text-xs">Live</span>
                        )}
                    </h3>
                    <p className="text-xs text-muted mt-0.5">
                        {isLive ? 'Penalties computed from your uploaded report' : 'Awaiting analysis — showing mock baseline'}
                    </p>
                </div>
                <div className="flex items-center gap-3 text-xs">
                    <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-accent inline-block" />Base</span>
                    <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-danger inline-block" />Penalty</span>
                    <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-success inline-block" />Final</span>
                </div>
            </div>

            <ResponsiveContainer width="100%" height={240}>
                <ComposedChart data={chartData} margin={{ top: 20, right: 10, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1E2D4A" vertical={false} />
                    <XAxis dataKey="label" tick={{ fill: '#64748B', fontSize: 10 }} tickLine={false} axisLine={false}
                        tickFormatter={(val) => {
                            const key = Object.keys(WATERFALL_LABELS).find(k => val.startsWith(k))
                            return key ? WATERFALL_LABELS[key] : val
                        }}
                    />
                    <YAxis tickFormatter={v => `${v}%`} tick={{ fill: '#64748B', fontSize: 11 }} tickLine={false} axisLine={false} domain={[0, 14]} />
                    <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(59,130,246,0.05)' }} />
                    <ReferenceLine y={BASE_RATE} stroke="#3B82F6" strokeDasharray="4 2" strokeOpacity={0.4} />
                    <Bar dataKey="invisible" stackId="a" fill="transparent" />
                    <Bar dataKey="visible" stackId="a" radius={[4, 4, 0, 0]}
                        label={<CustomLabel />}
                    >
                        {chartData.map((entry, i) => (
                            <Cell key={i} fill={COLORS[entry.type]} fillOpacity={entry.type === 'penalty' ? 0.85 : 1} />
                        ))}
                    </Bar>
                </ComposedChart>
            </ResponsiveContainer>

            {/* Applied penalties list */}
            {(decision?.applied_penalties?.length > 0) ? (
                <div className="space-y-2">
                    {decision.applied_penalties.map((p, i) => {
                        const meta = RULE_META[p.rule_id] || {}
                        return (
                            <div key={i} className="flex items-center gap-3 bg-void rounded-lg px-3 py-2">
                                <span className="badge bg-danger/15 text-danger">{WATERFALL_LABELS[p.rule_id] || p.rule_id}</span>
                                <span className="text-xs text-muted flex-1">{p.trigger}</span>
                                <span className="font-mono text-xs text-danger">+{p.rate_penalty_bps}bps</span>
                                {p.limit_reduction_pct > 0 && (
                                    <span className="font-mono text-xs text-warn">−{p.limit_reduction_pct}% limit</span>
                                )}
                            </div>
                        )
                    })}
                </div>
            ) : isLive ? (
                <div className="flex items-center gap-2 bg-success/5 border border-success/20 rounded-lg px-3 py-2.5">
                    <CheckCircle size={13} className="text-success" />
                    <p className="text-xs text-success">No penalties triggered — report is clean</p>
                </div>
            ) : (
                <div className="flex items-center gap-2 text-xs text-muted bg-void rounded-lg px-3 py-2.5">
                    <Info size={13} />
                    Upload a report to compute live penalties
                </div>
            )}

            {/* Final decision card */}
            <div className={`flex items-center justify-between ${recStyle.bg} border ${recStyle.border} rounded-lg px-4 py-3`}>
                <div className="flex items-center gap-2">
                    <RecIcon size={16} className={recStyle.color} />
                    <div>
                        <p className="text-xs text-muted">Decision</p>
                        <p className={`font-bold ${recStyle.color}`}>{rec.replace(/_/g, ' ')}</p>
                    </div>
                </div>
                <div className="text-right space-y-0.5">
                    <p className="text-xs text-muted">
                        Rate: <span className={`font-mono font-bold ${recStyle.color}`}>{decision?.final_rate_pct?.toFixed(2) ?? BASE_RATE.toFixed(2)}%</span>
                    </p>
                    <p className="text-xs text-muted">
                        Limit: <span className="font-semibold text-text">₹{decision?.final_limit_cr?.toFixed(1) ?? BASE_LIMIT.toFixed(1)} Cr</span>
                    </p>
                </div>
            </div>
        </div>
    )
}
