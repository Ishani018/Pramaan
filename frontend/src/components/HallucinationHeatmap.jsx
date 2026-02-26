/**
 * ComplianceHeatmap – Live Compliance Evidence Grid
 * ==================================================
 * Replaces the static mock heatmap with live findings from the compliance scanner.
 *
 * Props:
 *   result – the full API response from POST /api/v1/analyze-report
 *
 * When no result is available, renders a clear "awaiting scan" empty state.
 * When findings exist, renders a colour-coded grid of matched evidence snippets.
 * P-03 (CARO + auditor) findings are red; emphasis/going-concern (P-04) are amber.
 */
import { useState } from 'react'
import { FileSearch, AlertTriangle, CheckCircle } from 'lucide-react'

// ── Colour config by finding category ────────────────────────────────────────
const CATEGORY_STYLE = {
    caro: { bg: 'rgba(239,68,68,0.12)', border: 'rgba(239,68,68,0.35)', text: '#EF4444', badge: 'CARO 2020', rule: 'P-03' },
    qualification: { bg: 'rgba(249,115,22,0.12)', border: 'rgba(249,115,22,0.35)', text: '#F97316', badge: 'Audit Qual.', rule: 'P-03' },
    emphasis: { bg: 'rgba(245,158,11,0.12)', border: 'rgba(245,158,11,0.35)', text: '#F59E0B', badge: 'Emphasis', rule: 'P-04' },
}

function FindingCell({ finding, category, isHovered, onHover }) {
    const style = CATEGORY_STYLE[category]
    return (
        <div
            className="rounded-lg p-3 cursor-pointer relative transition-all duration-150"
            style={{
                background: style.bg,
                border: `1px solid ${isHovered ? style.text : style.border}`,
                boxShadow: isHovered ? `0 0 14px ${style.border}` : 'none',
            }}
            onMouseEnter={onHover}
            onMouseLeave={() => onHover(null)}
        >
            {/* Badge row */}
            <div className="flex items-center justify-between mb-1.5">
                <span
                    className="text-xs font-semibold px-2 py-0.5 rounded-full"
                    style={{ background: `${style.text}20`, color: style.text }}
                >
                    {style.badge}
                </span>
                <span
                    className="text-xs font-mono font-bold"
                    style={{ color: style.text }}
                >
                    {style.rule}
                </span>
            </div>

            {/* Pattern label */}
            <p className="text-xs text-text font-medium mb-1 leading-tight">
                {finding.pattern}
            </p>

            {/* Snippet preview (truncated) */}
            <p className="text-xs text-muted leading-relaxed line-clamp-3 font-mono whitespace-pre-wrap">
                {finding.snippet}
            </p>
        </div>
    )
}

function EmptyState() {
    return (
        <div className="glass p-5 flex flex-col items-center justify-center text-center py-12">
            <FileSearch size={32} className="text-muted mb-3" />
            <p className="font-medium text-text text-sm">No scan results yet</p>
            <p className="text-xs text-muted mt-1">Upload a PDF and run the compliance scan to see evidence here</p>
        </div>
    )
}

function CleanReport() {
    return (
        <div className="glass p-5 flex flex-col items-center justify-center text-center py-12 border-success/20">
            <div className="w-12 h-12 bg-success/15 rounded-2xl flex items-center justify-center mb-3">
                <CheckCircle size={24} className="text-success" />
            </div>
            <p className="font-semibold text-success text-sm">Clean Report — No Findings</p>
            <p className="text-xs text-muted mt-1">Auditor's report contains no CARO defaults or qualifications</p>
        </div>
    )
}

export default function ComplianceHeatmap({ result }) {
    const [hoveredIdx, setHoveredIdx] = useState(null)

    if (!result) return <EmptyState />

    // Flatten all findings into a unified grid
    const allFindings = [
        ...(result.caro_findings || []).map(f => ({ ...f, category: 'caro' })),
        ...(result.auditor_qualification_findings || []).map(f => ({ ...f, category: 'qualification' })),
        ...(result.emphasis_findings || []).map(f => ({ ...f, category: 'emphasis' })),
    ]

    const totalFindings = allFindings.length
    const caroCount = (result.caro_findings || []).length
    const qualificationCount = (result.auditor_qualification_findings || []).length
    const emphasisCount = (result.emphasis_findings || []).length

    return (
        <div className="glass p-5 space-y-4 animate-fade-in">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h3 className="font-semibold text-text">Compliance Evidence Grid</h3>
                    <p className="text-xs text-muted mt-0.5">
                        Every cell is a direct regex match from the auditor's report — zero inference
                    </p>
                </div>

                <div className="flex items-center gap-3 text-xs">
                    <span className="flex items-center gap-1.5">
                        <span className="w-2.5 h-2.5 rounded-sm bg-danger inline-block opacity-80" />
                        CARO ({caroCount})
                    </span>
                    <span className="flex items-center gap-1.5">
                        <span className="w-2.5 h-2.5 rounded-sm inline-block opacity-80" style={{ background: '#F97316' }} />
                        Qual. ({qualificationCount})
                    </span>
                    {emphasisCount > 0 && (
                        <span className="flex items-center gap-1.5">
                            <span className="w-2.5 h-2.5 rounded-sm bg-warn inline-block opacity-80" />
                            Emphasis ({emphasisCount})
                        </span>
                    )}
                </div>
            </div>

            {/* Triggered rule pills */}
            {(result.triggered_rules || []).length > 0 && (
                <div className="flex items-center gap-2">
                    <AlertTriangle size={12} className="text-danger" />
                    <span className="text-xs text-muted">Triggered:</span>
                    {result.triggered_rules.map(r => (
                        <span key={r} className="badge bg-danger/15 text-danger font-semibold">{r}</span>
                    ))}
                </div>
            )}

            {/* Grid */}
            {totalFindings === 0 ? (
                <CleanReport />
            ) : (
                <div className="grid grid-cols-2 gap-2.5">
                    {allFindings.map((f, i) => (
                        <FindingCell
                            key={i}
                            finding={f}
                            category={f.category}
                            isHovered={hoveredIdx === i}
                            onHover={() => setHoveredIdx(i)}
                        />
                    ))}
                </div>
            )}

            {/* Methodology footer */}
            {totalFindings > 0 && (
                <p className="text-xs text-muted leading-relaxed pt-1 border-t border-border">
                    Findings extracted by deterministic regex. Each snippet shows ±200 characters of context
                    from the original PDF text. No text was generated, inferred, or hallucinated.
                </p>
            )}
        </div>
    )
}
