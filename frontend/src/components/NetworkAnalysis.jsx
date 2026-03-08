/**
 * NetworkAnalysis.jsx – Counterparty Intelligence Network Graph
 * ==============================================================
 * Renders an interactive physics-based 2D force graph from real
 * counterparty intelligence data (shared directors, shell companies,
 * address matches, circular flows).
 *
 * Receives data as props from the analysis response — no mock fetch.
 *
 * Visual conventions:
 *   - Applicant node  → dark (#111111)
 *   - Counterparty    → blue (#2563EB)
 *   - Shell suspect   → red  (#B91C1C)
 *   - Director        → teal (#0F766E)
 *   - Transaction     → flowing particles
 */
import { useEffect, useRef, useState, useCallback } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import { AlertTriangle, Activity, Shield, Users, MapPin, Building2 } from 'lucide-react'

const NODE_COLORS = {
    applicant: '#111111',
    counterparty: '#2563EB',
    shell: '#B91C1C',
    director: '#0F766E',
}
const LINK_COLOR = '#555555'
const PARTICLE_COLOR = '#92400E'

const FLAG_ICONS = {
    shared_director: Users,
    same_address: MapPin,
    shell_indicator: Building2,
    family_name: Users,
    circular_loop: AlertTriangle,
}

const SEVERITY_COLORS = {
    CRITICAL: 'text-danger',
    HIGH: 'text-warn',
    MEDIUM: 'text-muted',
}

/* Paint custom node: filled circle + two-line label */
function drawNode(node, ctx, globalScale) {
    const r = 18
    const label1 = (node.label || node.id).split('\n')[0]
    const label2 = (node.label || node.id).split('\n')[1] || ''

    // Glow
    ctx.shadowColor = NODE_COLORS[node.type] || '#60A5FA'
    ctx.shadowBlur = 12

    // Circle
    ctx.beginPath()
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI, false)
    ctx.fillStyle = NODE_COLORS[node.type] || '#60A5FA'
    ctx.fill()

    ctx.shadowBlur = 0

    // Outer ring
    ctx.strokeStyle = 'rgba(255,255,255,0.25)'
    ctx.lineWidth = 1.5
    ctx.stroke()

    // Label line 1
    const fontSize = Math.max(10 / globalScale, 4.5)
    ctx.font = `bold ${fontSize}px Inter, sans-serif`
    ctx.fillStyle = '#F5F0E4'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(label1, node.x, node.y + r + fontSize * 0.9)

    // Label line 2 (italic, smaller, dimmed)
    if (label2) {
        ctx.font = `italic ${fontSize * 0.85}px Inter, sans-serif`
        ctx.fillStyle = 'rgba(245,240,228,0.55)'
        ctx.fillText(label2, node.x, node.y + r + fontSize * 2.0)
    }
}

/* Paint edge amount label at the midpoint */
function drawLink(link, ctx) {
    if (!link.label) return
    const mx = (link.source.x + link.target.x) / 2
    const my = (link.source.y + link.target.y) / 2
    ctx.font = 'bold 8px Inter, sans-serif'
    ctx.fillStyle = link.type === 'directorship' ? '#0F766E' : '#F97316'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(link.label, mx, my - 8)
}

export default function NetworkAnalysis({ data }) {
    const [graphData, setGraphData] = useState(null)
    const graphRef = useRef()
    const containerRef = useRef()
    const [dims, setDims] = useState({ w: 600, h: 420 })

    const detected = data?.circular_trading_detected || false
    const flags = data?.relationship_flags || []
    const profiles = data?.counterparty_profiles || []
    const findings = data?.findings || []

    /* Measure container */
    useEffect(() => {
        if (!containerRef.current) return
        const ro = new ResizeObserver(entries => {
            const { width, height } = entries[0].contentRect
            setDims({ w: Math.floor(width), h: Math.max(360, Math.floor(height)) })
        })
        ro.observe(containerRef.current)
        return () => ro.disconnect()
    }, [])

    /* Build graph from data prop */
    useEffect(() => {
        if (!data?.nodes || !data?.links) {
            setGraphData(null)
            return
        }
        setGraphData({
            nodes: data.nodes.map(n => ({ ...n })),
            links: data.links.map(l => ({ ...l })),
        })
    }, [data])

    /* Auto-fit on data load */
    const handleEngineStop = useCallback(() => {
        graphRef.current?.zoomToFit(400, 60)
    }, [])

    /* ── No data state ── */
    if (!data || (!data.nodes?.length && !flags.length)) {
        return (
            <div className="glass p-8 flex flex-col items-center gap-3 text-center animate-fade-in">
                <Shield size={28} className="text-success" />
                <p className="text-sm font-semibold text-text">No Counterparty Risk Detected</p>
                <p className="text-xs text-muted">
                    Upload a bank statement CSV to enable counterparty intelligence.
                    The system will look up transaction partners on MCA and detect
                    shared directors, shell entities, and circular flows.
                </p>
            </div>
        )
    }

    const shellCount = profiles.filter(p => p.is_shell_suspect).length
    const mcaMatches = profiles.filter(p => p.mca_found).length

    return (
        <div className="space-y-4 animate-fade-in">
            {/* ── Header ── */}
            <div className="flex items-start justify-between">
                <div>
                    <h3 className="font-semibold text-text flex items-center gap-2">
                        <Activity size={15} className="text-accent" />
                        Counterparty Intelligence
                        {mcaMatches > 0 && (
                            <span className="badge bg-accent/15 text-accent text-xs">
                                {mcaMatches} MCA matches
                            </span>
                        )}
                    </h3>
                    <p className="text-xs text-muted mt-0.5">
                        {profiles.length} counterparties analyzed — {flags.length} relationship flags found
                    </p>
                </div>
                {detected && (
                    <div className="flex items-center gap-2 bg-danger/10 border border-danger/30 rounded-lg px-3 py-1.5">
                        <AlertTriangle size={13} className="text-danger flex-shrink-0" />
                        <span className="text-xs font-bold text-danger">Circular Trading Network</span>
                    </div>
                )}
            </div>

            {/* ── Legend ── */}
            <div className="flex flex-wrap gap-4 text-xs">
                {[
                    { color: '#111111', label: 'Applicant' },
                    { color: '#2563EB', label: 'Counterparty' },
                    { color: '#B91C1C', label: 'Shell Suspect' },
                    { color: '#0F766E', label: 'Shared Director' },
                    { color: '#92400E', label: 'Money Flow' },
                ].map(({ color, label }) => (
                    <span key={label} className="flex items-center gap-1.5">
                        <span className="w-3 h-3 rounded-full inline-block border border-border" style={{ background: color }} />
                        <span className="text-muted">{label}</span>
                    </span>
                ))}
            </div>

            {/* ── Graph canvas ── */}
            <div
                ref={containerRef}
                className="rounded-2xl overflow-hidden border border-border relative"
                style={{ backgroundColor: '#111111', minHeight: 380 }}
            >
                {graphData && (
                    <ForceGraph2D
                        ref={graphRef}
                        width={dims.w}
                        height={dims.h}
                        graphData={graphData}
                        d3AlphaDecay={0.015}
                        d3VelocityDecay={0.3}
                        cooldownTicks={120}
                        onEngineStop={handleEngineStop}
                        nodeCanvasObject={drawNode}
                        nodeCanvasObjectMode={() => 'replace'}
                        nodePointerAreaPaint={(node, color, ctx) => {
                            ctx.fillStyle = color
                            ctx.beginPath()
                            ctx.arc(node.x, node.y, 20, 0, 2 * Math.PI, false)
                            ctx.fill()
                        }}
                        linkColor={() => LINK_COLOR}
                        linkWidth={2.5}
                        linkDirectionalArrowLength={10}
                        linkDirectionalArrowRelPos={1}
                        linkCurvature={0.25}
                        linkCanvasObjectMode={() => 'after'}
                        linkCanvasObject={drawLink}
                        linkDirectionalParticles={l => l.type === 'directorship' ? 0 : 4}
                        linkDirectionalParticleWidth={3}
                        linkDirectionalParticleSpeed={0.006}
                        linkDirectionalParticleColor={() => PARTICLE_COLOR}
                        backgroundColor="transparent"
                    />
                )}

                {/* P-06 watermark */}
                {detected && (
                    <div className="absolute top-3 left-3 flex items-center gap-1.5 bg-danger/20 border border-danger/40 rounded-full px-2.5 py-1 pointer-events-none">
                        <span className="w-1.5 h-1.5 rounded-full bg-danger animate-pulse" />
                        <span className="text-xs font-semibold text-danger">P-06 Triggered</span>
                    </div>
                )}

                {/* Shell count badge */}
                {shellCount > 0 && (
                    <div className="absolute top-3 right-3 flex items-center gap-1.5 bg-warn/20 border border-warn/40 rounded-full px-2.5 py-1 pointer-events-none">
                        <Building2 size={11} className="text-warn" />
                        <span className="text-xs font-semibold text-warn">{shellCount} Shell Suspect{shellCount > 1 ? 's' : ''}</span>
                    </div>
                )}
            </div>

            {/* ── Relationship Flags ── */}
            {flags.length > 0 && (
                <div className="space-y-2">
                    <h4 className="text-xs font-bold text-text uppercase tracking-wider">Relationship Flags</h4>
                    <div className="grid gap-2">
                        {flags.map((flag, i) => {
                            const Icon = FLAG_ICONS[flag.flag_type] || AlertTriangle
                            const severityColor = SEVERITY_COLORS[flag.severity] || 'text-muted'
                            const bgColor = flag.severity === 'CRITICAL' ? 'bg-danger/5 border-danger/30'
                                : flag.severity === 'HIGH' ? 'bg-warn/5 border-warn/30'
                                : 'bg-surface border-border'
                            return (
                                <div key={i} className={`glass ${bgColor} p-3 space-y-1`}>
                                    <div className="flex items-center gap-2">
                                        <Icon size={13} className={severityColor} />
                                        <span className={`text-xs font-bold ${severityColor}`}>
                                            {flag.flag_type.replace(/_/g, ' ').toUpperCase()}
                                        </span>
                                        <span className={`text-xs px-1.5 py-0.5 rounded ${
                                            flag.severity === 'CRITICAL' ? 'bg-danger/20 text-danger'
                                            : flag.severity === 'HIGH' ? 'bg-warn/20 text-warn'
                                            : 'bg-muted/20 text-muted'
                                        }`}>
                                            {flag.severity}
                                        </span>
                                    </div>
                                    <p className="text-xs text-text">{flag.evidence}</p>
                                    <p className="text-xs text-muted">
                                        {flag.entity_a} &harr; {flag.entity_b}
                                    </p>
                                </div>
                            )
                        })}
                    </div>
                </div>
            )}

            {/* ── P-06 Alert Card ── */}
            {detected && (
                <div className="glass border-danger/30 bg-danger/5 p-4 space-y-2 animate-fade-in">
                    <p className="text-xs font-bold text-danger flex items-center gap-2">
                        <AlertTriangle size={13} />
                        Rule P-06 — Circular Trading Network Detected
                    </p>
                    {findings.map((f, i) => (
                        <p key={i} className="text-xs text-text">{f}</p>
                    ))}
                    <p className="text-xs text-muted">
                        Penalty: <span className="text-danger font-semibold">+200 bps rate, −30% credit limit</span>
                        &nbsp;·&nbsp;Requires manual review
                    </p>
                </div>
            )}

            {/* ── Counterparty Profiles Table ── */}
            {profiles.length > 0 && (
                <div className="space-y-2">
                    <h4 className="text-xs font-bold text-text uppercase tracking-wider">Counterparty Profiles</h4>
                    <div className="overflow-x-auto">
                        <table className="w-full text-xs">
                            <thead>
                                <tr className="text-left text-muted border-b border-border">
                                    <th className="py-2 pr-3">Counterparty</th>
                                    <th className="py-2 pr-3 text-right">Volume</th>
                                    <th className="py-2 pr-3">MCA Status</th>
                                    <th className="py-2 pr-3 text-right">Paid-up Capital</th>
                                    <th className="py-2">Flags</th>
                                </tr>
                            </thead>
                            <tbody>
                                {profiles.map((p, i) => (
                                    <tr key={i} className={`border-b border-border/50 ${p.is_shell_suspect ? 'bg-danger/5' : ''}`}>
                                        <td className="py-2 pr-3">
                                            <span className="font-medium text-text">{p.name}</span>
                                            {p.cin && <span className="text-muted ml-1">({p.cin})</span>}
                                        </td>
                                        <td className="py-2 pr-3 text-right font-mono">
                                            ₹{(p.total_volume / 100000).toFixed(1)}L
                                        </td>
                                        <td className="py-2 pr-3">
                                            {p.mca_found ? (
                                                <span className={p.company_status?.toLowerCase().includes('active') ? 'text-success' : 'text-warn'}>
                                                    {p.company_status}
                                                </span>
                                            ) : (
                                                <span className="text-muted">Not found</span>
                                            )}
                                        </td>
                                        <td className="py-2 pr-3 text-right font-mono">
                                            {p.mca_found ? `₹${(p.paid_up_capital / 100000).toFixed(1)}L` : '—'}
                                        </td>
                                        <td className="py-2">
                                            {p.is_shell_suspect && (
                                                <span className="text-danger font-bold">SHELL</span>
                                            )}
                                            {p.shell_reasons?.map((r, j) => (
                                                <p key={j} className="text-muted text-xs">{r}</p>
                                            ))}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    )
}
