/**
 * NetworkAnalysis.jsx – Counterparty Intelligence Network Graph
 * ==============================================================
 * Renders an interactive physics-based 2D force graph from real
 * counterparty intelligence data (shared directors, shell companies,
 * address matches, circular flows).
 *
 * Receives data as props from the analysis response — no mock fetch.
 *
 * Visual conventions (canvas):
 *   - Applicant node  → ink black (#0A0A0A)
 *   - Counterparty    → dark blue (#1E3A5F)
 *   - Shell suspect   → newspaper red (#CC0000)
 *   - Director        → gold (#D4A017)
 *   - Transaction     → flowing particles
 */
import { useEffect, useRef, useState, useCallback } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import { AlertTriangle, Shield, Users, MapPin, Building2 } from 'lucide-react'

const NODE_COLORS = {
    applicant: '#0A0A0A',
    counterparty: '#1E3A5F',
    shell: '#CC0000',
    director: '#D4A017',
}
const LINK_COLOR = '#444444'
const PARTICLE_COLOR = '#CC0000'

const FLAG_ICONS = {
    shared_director: Users,
    same_address: MapPin,
    shell_indicator: Building2,
    family_name: Users,
    circular_loop: AlertTriangle,
}

/* Paint custom node: filled circle + two-line label */
function drawNode(node, ctx, globalScale) {
    const r = 18
    const label1 = (node.label || node.id).split('\n')[0]
    const label2 = (node.label || node.id).split('\n')[1] || ''
    const color = NODE_COLORS[node.type] || '#444444'

    // Hard shadow (brutalist — no glow)
    ctx.shadowColor = 'rgba(0,0,0,0.3)'
    ctx.shadowBlur = 0
    ctx.shadowOffsetX = 2
    ctx.shadowOffsetY = 2

    // Circle
    ctx.beginPath()
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI, false)
    ctx.fillStyle = color
    ctx.fill()

    // Reset shadow
    ctx.shadowOffsetX = 0
    ctx.shadowOffsetY = 0

    // Outer ring
    ctx.strokeStyle = '#FFFFF0'
    ctx.lineWidth = 2
    ctx.stroke()

    // Label line 1 — monospace, bold
    const fontSize = Math.max(10 / globalScale, 4.5)
    ctx.font = `bold ${fontSize}px "IBM Plex Mono", monospace`
    ctx.fillStyle = '#FFFFF0'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(label1, node.x, node.y + r + fontSize * 0.9)

    // Label line 2 (smaller, dimmed)
    if (label2) {
        ctx.font = `${fontSize * 0.85}px "IBM Plex Mono", monospace`
        ctx.fillStyle = 'rgba(255,255,240,0.5)'
        ctx.fillText(label2, node.x, node.y + r + fontSize * 2.0)
    }
}

/* Paint edge amount label at the midpoint */
function drawLink(link, ctx) {
    if (!link.label) return
    const mx = (link.source.x + link.target.x) / 2
    const my = (link.source.y + link.target.y) / 2
    ctx.font = 'bold 8px "IBM Plex Mono", monospace'
    ctx.fillStyle = link.type === 'directorship' ? '#D4A017' : '#CC0000'
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
            <div className="flex flex-col items-center justify-center p-10 bg-paper border-[3px] border-ink">
                <Shield size={36} className="text-ink-muted mb-4" />
                <p className="text-sm font-display font-bold text-ink uppercase tracking-wide">No Counterparty Risk Detected</p>
                <p className="text-xs text-ink-muted mt-2 max-w-sm text-center font-serif">
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
        <div className="flex flex-col gap-6 animate-fade-in">
            {/* ── NETWORK GRAPH ── */}
            <div className="border-[3px] border-ink bg-paper relative">
                <div className="absolute -top-3 left-4 bg-paper px-2 font-display font-black text-ink uppercase tracking-wider text-sm flex items-center gap-2 z-10">
                    <div className="w-2 h-2 bg-ink" />
                    COUNTERPARTY INTELLIGENCE
                </div>

                {/* Sub-header stats */}
                <div className="flex items-center justify-between px-4 pt-5 pb-2">
                    <p className="text-[10px] font-mono font-bold text-ink-muted uppercase">
                        {profiles.length} counterparties &middot; {flags.length} flags
                        {mcaMatches > 0 && <> &middot; {mcaMatches} MCA matches</>}
                    </p>
                    {detected && (
                        <div className="inline-block px-2 py-0.5 bg-red text-white text-[10px] font-bold font-mono uppercase">
                            CIRCULAR TRADING DETECTED
                        </div>
                    )}
                </div>

                {/* Legend */}
                <div className="flex flex-wrap gap-4 px-4 pb-3 text-[10px] font-mono font-bold uppercase">
                    {[
                        { color: '#0A0A0A', label: 'Applicant' },
                        { color: '#1E3A5F', label: 'Counterparty' },
                        { color: '#CC0000', label: 'Shell Suspect' },
                        { color: '#D4A017', label: 'Director' },
                    ].map(({ color, label }) => (
                        <span key={label} className="flex items-center gap-1.5">
                            <span className="w-2.5 h-2.5 inline-block border border-ink" style={{ background: color }} />
                            <span className="text-ink-muted">{label}</span>
                        </span>
                    ))}
                </div>

                {/* Graph canvas — dark bg is intentional for contrast */}
                <div
                    ref={containerRef}
                    className="overflow-hidden border-t-2 border-ink relative"
                    style={{ backgroundColor: '#0A0A0A', minHeight: 380 }}
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
                        <div className="absolute top-3 left-3 flex items-center gap-1.5 bg-red px-2 py-1 pointer-events-none">
                            <span className="w-1.5 h-1.5 bg-white animate-pulse" />
                            <span className="text-[10px] font-mono font-bold text-white uppercase">P-06 Triggered</span>
                        </div>
                    )}

                    {/* Shell count badge */}
                    {shellCount > 0 && (
                        <div className="absolute top-3 right-3 flex items-center gap-1.5 bg-gold px-2 py-1 pointer-events-none">
                            <Building2 size={10} className="text-white" />
                            <span className="text-[10px] font-mono font-bold text-white uppercase">
                                {shellCount} Shell{shellCount > 1 ? 's' : ''}
                            </span>
                        </div>
                    )}
                </div>
            </div>

            {/* ── RELATIONSHIP FLAGS ── */}
            {flags.length > 0 && (
                <div className="border-[3px] border-ink bg-paper p-6 relative">
                    <div className="absolute -top-3 left-4 bg-paper px-2 font-display font-black text-ink uppercase tracking-wider text-sm flex items-center gap-2">
                        <div className="w-2 h-2 bg-ink" />
                        RELATIONSHIP FLAGS
                    </div>

                    <div className="grid gap-3 mt-2">
                        {flags.map((flag, i) => {
                            const Icon = FLAG_ICONS[flag.flag_type] || AlertTriangle
                            const isCritical = flag.severity === 'CRITICAL'
                            const isHigh = flag.severity === 'HIGH'
                            return (
                                <div
                                    key={i}
                                    className={`border-2 p-3 ${
                                        isCritical ? 'border-red bg-red-light' :
                                        isHigh ? 'border-gold bg-paper' :
                                        'border-border bg-paper'
                                    }`}
                                >
                                    <div className="flex items-center gap-2 mb-1">
                                        <Icon size={13} className={isCritical ? 'text-red' : isHigh ? 'text-gold' : 'text-ink-muted'} />
                                        <span className={`text-[10px] font-mono font-bold uppercase tracking-wide ${
                                            isCritical ? 'text-red' : isHigh ? 'text-gold' : 'text-ink'
                                        }`}>
                                            {flag.flag_type.replace(/_/g, ' ')}
                                        </span>
                                        <span className={`text-[10px] font-mono font-bold px-1.5 py-0.5 ${
                                            isCritical ? 'bg-red text-white' :
                                            isHigh ? 'bg-gold text-white' :
                                            'bg-paper-raised text-ink-muted border border-border'
                                        }`}>
                                            {flag.severity}
                                        </span>
                                    </div>
                                    <p className="text-xs text-ink font-serif">{flag.evidence}</p>
                                    <p className="text-[10px] text-ink-muted font-mono mt-1">
                                        {flag.entity_a} &harr; {flag.entity_b}
                                    </p>
                                </div>
                            )
                        })}
                    </div>
                </div>
            )}

            {/* ── P-06 ALERT ── */}
            {detected && (
                <div className="border-[3px] border-red bg-red-light p-6 relative animate-fade-in">
                    <div className="absolute -top-3 left-4 bg-red px-2 py-0.5 font-mono font-bold text-white uppercase tracking-wider text-[10px] flex items-center gap-2">
                        <AlertTriangle size={10} />
                        RULE P-06
                    </div>
                    <p className="text-sm font-display font-bold text-red mt-1">
                        Circular Trading Network Detected
                    </p>
                    {findings.map((f, i) => (
                        <p key={i} className="text-xs text-ink font-serif mt-1">{f}</p>
                    ))}
                    <div className="border-t-2 border-red/30 mt-3 pt-2">
                        <p className="text-[10px] font-mono font-bold text-ink-muted uppercase">
                            Penalty: <span className="text-red">+200 bps rate, -30% credit limit</span>
                            &nbsp;&middot;&nbsp;Requires manual review
                        </p>
                    </div>
                </div>
            )}

            {/* ── COUNTERPARTY PROFILES ── */}
            {profiles.length > 0 && (
                <div className="border-[3px] border-ink bg-paper p-6 relative">
                    <div className="absolute -top-3 left-4 bg-paper px-2 font-display font-black text-ink uppercase tracking-wider text-sm flex items-center gap-2">
                        <div className="w-2 h-2 bg-ink" />
                        COUNTERPARTY PROFILES
                    </div>

                    <div className="overflow-x-auto mt-2">
                        <table className="w-full text-xs">
                            <thead>
                                <tr className="border-b-2 border-ink text-left">
                                    <th className="py-2 pr-3 font-mono font-bold text-[10px] text-ink-muted uppercase">Counterparty</th>
                                    <th className="py-2 pr-3 font-mono font-bold text-[10px] text-ink-muted uppercase text-right">Volume</th>
                                    <th className="py-2 pr-3 font-mono font-bold text-[10px] text-ink-muted uppercase">MCA Status</th>
                                    <th className="py-2 pr-3 font-mono font-bold text-[10px] text-ink-muted uppercase text-right">Paid-up Capital</th>
                                    <th className="py-2 font-mono font-bold text-[10px] text-ink-muted uppercase">Flags</th>
                                </tr>
                            </thead>
                            <tbody>
                                {profiles.map((p, i) => (
                                    <tr key={i} className={`border-b border-border ${p.is_shell_suspect ? 'bg-red-light' : ''}`}>
                                        <td className="py-2 pr-3">
                                            <span className="font-mono font-bold text-ink text-xs">{p.name}</span>
                                            {p.cin && <span className="text-ink-muted ml-1 text-[10px] font-mono">({p.cin})</span>}
                                        </td>
                                        <td className="py-2 pr-3 text-right font-mono font-bold text-ink">
                                            ₹{(p.total_volume / 100000).toFixed(1)}L
                                        </td>
                                        <td className="py-2 pr-3 font-mono text-xs">
                                            {p.mca_found ? (
                                                <span className={p.company_status?.toLowerCase().includes('active') ? 'text-ink font-bold' : 'text-red font-bold'}>
                                                    {p.company_status}
                                                </span>
                                            ) : (
                                                <span className="text-ink-muted italic font-serif">Not found</span>
                                            )}
                                        </td>
                                        <td className="py-2 pr-3 text-right font-mono text-ink">
                                            {p.mca_found ? `₹${(p.paid_up_capital / 100000).toFixed(1)}L` : '—'}
                                        </td>
                                        <td className="py-2">
                                            {p.is_shell_suspect && (
                                                <span className="inline-block px-1.5 py-0.5 bg-red text-white text-[10px] font-mono font-bold uppercase">SHELL</span>
                                            )}
                                            {p.shell_reasons?.map((r, j) => (
                                                <p key={j} className="text-ink-muted text-[10px] font-serif mt-0.5">{r}</p>
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
