/**
 * TrendPanel – Multi-Year Financial Trend Comparison
 * ===================================================
 * Reads per_year_scans from the API response and shows YoY changes
 * for Revenue, PAT, and Net Worth with directional badges.
 */
import { TrendingUp, TrendingDown, Minus, ArrowRight } from 'lucide-react'

const METRICS = [
    { key: 'Revenue', label: 'Revenue from Operations' },
    { key: 'PAT', label: 'Profit After Tax' },
    { key: 'Net Worth', label: 'Net Worth / Equity' },
]

function getDirection(changePct) {
    if (changePct > 5) return 'improving'
    if (changePct < -5) return 'deteriorating'
    return 'stable'
}

const DIRECTION_STYLE = {
    improving: { color: 'text-green', bg: 'bg-green/10', icon: TrendingUp, label: 'IMPROVING' },
    deteriorating: { color: 'text-red', bg: 'bg-red/10', icon: TrendingDown, label: 'DETERIORATING' },
    stable: { color: 'text-[#D4A017]', bg: 'bg-[#D4A017]/10', icon: Minus, label: 'STABLE' },
}

function formatValue(val) {
    if (val == null) return '—'
    const num = parseFloat(val)
    if (isNaN(num)) return '—'
    if (num < 0) return `(₹${Math.abs(num).toLocaleString('en-IN')} Cr)`
    return `₹${num.toLocaleString('en-IN')} Cr`
}

export default function TrendPanel({ perYearScans }) {
    if (!perYearScans) return (
        <div className="border-[3px] border-ink bg-paper p-6">
            <p className="text-sm text-muted font-serif">No multi-year data available. Upload reports for multiple years to see trends.</p>
        </div>
    )

    const years = Object.keys(perYearScans).sort()
    if (years.length < 2) return (
        <div className="border-[3px] border-ink bg-paper p-6">
            <div className="absolute -top-3 left-4 bg-paper px-2 font-display font-black text-ink uppercase tracking-wider text-sm flex items-center gap-2">
                <div className="w-2 h-2 bg-ink" />
                Financial Trends
            </div>
            <p className="text-sm text-muted font-serif mt-2">Upload reports for 2+ years to enable YoY trend analysis.</p>
        </div>
    )

    // Compare the two most recent years
    const olderYear = years[years.length - 2]
    const newerYear = years[years.length - 1]
    const olderFigs = perYearScans[olderYear]?.extracted_figures || {}
    const newerFigs = perYearScans[newerYear]?.extracted_figures || {}

    const trends = METRICS.map(m => {
        const oldVal = olderFigs[m.key]?.normalized_value ?? olderFigs[m.key]?.value ?? null
        const newVal = newerFigs[m.key]?.normalized_value ?? newerFigs[m.key]?.value ?? null
        const oldNum = oldVal != null ? parseFloat(oldVal) : null
        const newNum = newVal != null ? parseFloat(newVal) : null

        let changePct = null
        if (oldNum != null && newNum != null && oldNum !== 0) {
            changePct = ((newNum - oldNum) / Math.abs(oldNum)) * 100
        }

        return {
            ...m,
            oldVal: oldNum,
            newVal: newNum,
            changePct,
            direction: changePct != null ? getDirection(changePct) : null,
        }
    })

    return (
        <div className="border-[3px] border-ink bg-paper p-6 relative">
            <div className="absolute -top-3 left-4 bg-paper px-2 font-display font-black text-ink uppercase tracking-wider text-sm flex items-center gap-2">
                <div className="w-2 h-2 bg-ink" />
                Financial Trends
            </div>

            <p className="text-xs text-muted font-serif mb-4 mt-1">
                Year-over-year comparison: {olderYear} → {newerYear}
            </p>

            <div className="space-y-3">
                {trends.map(t => {
                    const dirStyle = t.direction ? DIRECTION_STYLE[t.direction] : null
                    const DirIcon = dirStyle?.icon || Minus
                    return (
                        <div key={t.key} className="flex items-center justify-between border-b border-border pb-3 last:border-0">
                            <div className="flex-1">
                                <span className="font-mono text-xs text-muted uppercase">{t.label}</span>
                            </div>

                            <div className="flex items-center gap-3">
                                <span className="font-mono text-xs text-ink">{formatValue(t.oldVal)}</span>
                                <ArrowRight size={12} className="text-muted" />
                                <span className="font-mono text-xs font-bold text-ink">{formatValue(t.newVal)}</span>

                                {t.changePct != null && dirStyle && (
                                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-bold uppercase ${dirStyle.color} ${dirStyle.bg}`}>
                                        <DirIcon size={10} />
                                        {t.changePct > 0 ? '+' : ''}{t.changePct.toFixed(1)}%
                                    </span>
                                )}

                                {t.changePct == null && (
                                    <span className="text-[10px] text-muted uppercase px-2">N/A</span>
                                )}
                            </div>
                        </div>
                    )
                })}
            </div>
        </div>
    )
}
