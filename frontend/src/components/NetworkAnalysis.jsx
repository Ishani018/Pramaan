/**
 * NetworkAnalysis.jsx – Circular Trading Fraud Network Graph
 * ===========================================================
 * Fetches GET /api/v1/mock/network-graph on mount and renders an
 * interactive, physics-based 2D force graph.
 *
 * Visual conventions:
 *   • Applicant node  → vivid blue   (#3B82F6)
 *   • Shell companies → vivid red    (#EF4444)
 *   • Edges           → directional particles (flowing dots) to make
 *                        the circular money loop physically visible.
 */
import { useEffect, useRef, useState, useCallback } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import axios from 'axios'
import { AlertTriangle, RefreshCw, Activity } from 'lucide-react'

const NODE_COLORS = {
    applicant: '#3B82F6',
    shell: '#EF4444',
}
const LINK_COLOR = 'rgba(239,68,68,0.55)'
const PARTICLE_COLOR = '#F97316'

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
    ctx.fillStyle = '#F8FAFC'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(label1, node.x, node.y + r + fontSize * 0.9)

    // Label line 2 (italic, smaller, dimmed)
    if (label2) {
        ctx.font = `italic ${fontSize * 0.85}px Inter, sans-serif`
        ctx.fillStyle = 'rgba(248,250,252,0.55)'
        ctx.fillText(label2, node.x, node.y + r + fontSize * 2.0)
    }
}

/* Paint edge amount label at the midpoint */
function drawLink(link, ctx) {
    if (!link.label) return
    const mx = (link.source.x + link.target.x) / 2
    const my = (link.source.y + link.target.y) / 2
    ctx.font = 'bold 8px Inter, sans-serif'
    ctx.fillStyle = '#F97316'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(link.label, mx, my - 8)
}

export default function NetworkAnalysis() {
    const [graphData, setGraphData] = useState(null)
    const [detected, setDetected] = useState(false)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const graphRef = useRef()
    const containerRef = useRef()
    const [dims, setDims] = useState({ w: 600, h: 420 })

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

    /* Fetch */
    useEffect(() => {
        setLoading(true)
        axios.get('/api/v1/mock/network-graph', { timeout: 5000 })
            .then(({ data }) => {
                setDetected(!!data.circular_trading_detected)
                // Deep-copy nodes/links so force-graph can mutate freely
                setGraphData({
                    nodes: data.nodes.map(n => ({ ...n })),
                    links: data.links.map(l => ({ ...l })),
                })
            })
            .catch(err => setError(err.message || 'Fetch failed'))
            .finally(() => setLoading(false))
    }, [])

    /* Auto-fit on data load */
    const handleEngineStop = useCallback(() => {
        graphRef.current?.zoomToFit(400, 60)
    }, [])

    /* ── Loading & error states ── */
    if (loading) return (
        <div className="space-y-4 animate-fade-in">
            <div className="shimmer h-8 w-48 rounded-lg" />
            <div className="shimmer rounded-2xl" style={{ height: 380 }} />
        </div>
    )

    if (error) return (
        <div className="glass p-6 flex flex-col items-center gap-3 text-center">
            <AlertTriangle size={28} className="text-danger" />
            <p className="text-sm font-semibold text-danger">Network graph fetch failed</p>
            <p className="text-xs text-muted">{error}</p>
        </div>
    )

    return (
        <div className="space-y-4 animate-fade-in">
            {/* ── Header ── */}
            <div className="flex items-start justify-between">
                <div>
                    <h3 className="font-semibold text-text flex items-center gap-2">
                        <Activity size={15} className="text-accent" />
                        Network Transaction Graph
                        <span className="badge bg-success/15 text-success text-xs">Live</span>
                    </h3>
                    <p className="text-xs text-muted mt-0.5">Physics-based force graph — flowing dots show money direction</p>
                </div>
                {detected && (
                    <div className="flex items-center gap-2 bg-danger/10 border border-danger/30 rounded-lg px-3 py-1.5">
                        <AlertTriangle size={13} className="text-danger flex-shrink-0" />
                        <span className="text-xs font-bold text-danger">Circular Trading Detected</span>
                    </div>
                )}
            </div>

            {/* ── Legend ── */}
            <div className="flex flex-wrap gap-4 text-xs">
                {[
                    { color: '#3B82F6', label: 'Applicant' },
                    { color: '#EF4444', label: 'Shell Company' },
                    { color: '#F97316', label: 'Transaction Flow' },
                ].map(({ color, label }) => (
                    <span key={label} className="flex items-center gap-1.5">
                        <span className="w-3 h-3 rounded-full inline-block" style={{ background: color }} />
                        <span className="text-muted">{label}</span>
                    </span>
                ))}
            </div>

            {/* ── Graph canvas ── */}
            <div
                ref={containerRef}
                className="rounded-2xl overflow-hidden border border-border relative"
                style={{ background: 'radial-gradient(ellipse at 50% 60%, #0d1a2d 0%, #060d18 100%)', minHeight: 380 }}
            >
                {graphData && (
                    <ForceGraph2D
                        ref={graphRef}
                        width={dims.w}
                        height={dims.h}
                        graphData={graphData}
                        /* Physics */
                        d3AlphaDecay={0.015}
                        d3VelocityDecay={0.3}
                        cooldownTicks={120}
                        onEngineStop={handleEngineStop}
                        /* Nodes */
                        nodeCanvasObject={drawNode}
                        nodeCanvasObjectMode={() => 'replace'}
                        nodePointerAreaPaint={(node, color, ctx) => {
                            ctx.fillStyle = color
                            ctx.beginPath()
                            ctx.arc(node.x, node.y, 20, 0, 2 * Math.PI, false)
                            ctx.fill()
                        }}
                        /* Links */
                        linkColor={() => LINK_COLOR}
                        linkWidth={2.5}
                        linkDirectionalArrowLength={10}
                        linkDirectionalArrowRelPos={1}
                        linkCurvature={0.25}
                        linkCanvasObjectMode={() => 'after'}
                        linkCanvasObject={drawLink}
                        /* Particles (flowing dots = money movement) */
                        linkDirectionalParticles={4}
                        linkDirectionalParticleWidth={3}
                        linkDirectionalParticleSpeed={0.006}
                        linkDirectionalParticleColor={() => PARTICLE_COLOR}
                        /* Background */
                        backgroundColor="transparent"
                    />
                )}

                {/* Detected watermark */}
                {detected && (
                    <div className="absolute top-3 left-3 flex items-center gap-1.5 bg-danger/20 border border-danger/40 rounded-full px-2.5 py-1 pointer-events-none">
                        <span className="w-1.5 h-1.5 rounded-full bg-danger animate-pulse" />
                        <span className="text-xs font-semibold text-danger">P-06 Triggered</span>
                    </div>
                )}
            </div>

            {/* ── Detected details card ── */}
            {detected && (
                <div className="glass border-danger/30 bg-danger/5 p-4 space-y-2 animate-fade-in">
                    <p className="text-xs font-bold text-danger flex items-center gap-2">
                        <AlertTriangle size={13} />
                        Rule P-06 — Circular Fraud Detected
                    </p>
                    <div className="grid grid-cols-3 gap-3 mt-2">
                        {(graphData?.links || []).map((l, i) => (
                            <div key={i} className="text-center glass p-2">
                                <p className="text-xs text-muted">{l.source?.id ?? l.source} → {l.target?.id ?? l.target}</p>
                                <p className="font-mono font-bold text-danger text-sm">{l.label}</p>
                            </div>
                        ))}
                    </div>
                    <p className="text-xs text-muted">
                        Penalty: <span className="text-danger font-semibold">−50% credit limit</span>
                        &nbsp;·&nbsp;Loop value: <span className="text-warn font-mono">₹5.0 Cr</span>
                    </p>
                </div>
            )}
        </div>
    )
}
