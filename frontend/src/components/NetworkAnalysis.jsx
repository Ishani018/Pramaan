/**
 * NetworkAnalysis.jsx – Counterparty Intelligence
 * =================================================
 * Bloomberg-style SVG network graph showing money flows between
 * applicant and counterparties. Nodes sized by volume, colored
 * directional arrows, shell/circular highlighting.
 */
import { useState, useMemo } from 'react'
import { AlertTriangle, Shield, ChevronDown, Zap, RefreshCw } from 'lucide-react'

/* ── Palette (matches CSS vars) ── */
const C = {
    ink: '#0A0A0A',
    paper: '#FFFFF0',
    red: '#CC0000',
    green: '#167A3E',
    gold: '#D4A017',
    muted: '#444444',
    border: '#D4D0C8',
    yellow: '#B8860B',
}

/** Check if a profile is involved in any circular_loop flag */
function isCircularParty(name, flags) {
    return flags.some(f => f.flag_type === 'circular_loop' &&
        (f.entity_a === name || f.entity_b === name))
}

/** Format amount as ₹XL or ₹XCr */
function fmtAmt(v) {
    if (!v || v <= 0) return ''
    if (v >= 10000000) return `₹${(v / 10000000).toFixed(1)}Cr`
    if (v >= 100000) return `₹${(v / 100000).toFixed(1)}L`
    return `₹${(v / 1000).toFixed(0)}K`
}

/** Truncate label for node display */
function truncLabel(name, maxLen = 18) {
    if (!name) return ''
    // Try to shorten common suffixes
    let short = name
        .replace(/ PVT LTD$/i, '')
        .replace(/ PRIVATE LIMITED$/i, '')
        .replace(/ LIMITED$/i, '')
        .replace(/ LTD$/i, '')
        .replace(/ LLP$/i, '')
        .replace(/ CORP$/i, '')
        .replace(/ INDIA$/i, '')
    if (short.length > maxLen) short = short.slice(0, maxLen - 1) + '…'
    return short
}

/** Compute a curved SVG path between two points, offset from center line */
function curvedPath(x1, y1, r1, x2, y2, r2, bend = 0.15) {
    const dx = x2 - x1, dy = y2 - y1
    const dist = Math.sqrt(dx * dx + dy * dy)
    if (dist < 1) return ''
    const ux = dx / dist, uy = dy / dist
    // Start/end at circle edges
    const sx = x1 + ux * (r1 + 2), sy = y1 + uy * (r1 + 2)
    const ex = x2 - ux * (r2 + 6), ey = y2 - uy * (r2 + 6) // 6px gap for arrowhead
    // Control point perpendicular
    const mx = (sx + ex) / 2, my = (sy + ey) / 2
    const nx = -uy * dist * bend, ny = ux * dist * bend
    return `M${sx},${sy} Q${mx + nx},${my + ny} ${ex},${ey}`
}

/* ── SVG Network Graph ── */
function NetworkGraph({ profiles, flags, applicantName }) {
    const [hovered, setHovered] = useState(null)

    const { nodes, arrows, W, H } = useMemo(() => {
        const n = profiles.length
        if (n === 0) return { nodes: [], arrows: [], W: 600, H: 300 }

        const W = 780, H = Math.max(420, n > 6 ? 520 : 420)
        const cx = W / 2, cy = H / 2

        // Applicant node
        const appNode = { id: '__app', name: applicantName, x: cx, y: cy, r: 38, isApp: true }

        // Place counterparties in ellipse around applicant
        const rx = W * 0.36, ry = H * 0.36
        const maxVol = Math.max(...profiles.map(p => p.total_volume), 1)
        const cpNodes = profiles.map((p, i) => {
            const angle = (2 * Math.PI * i) / n - Math.PI / 2
            return {
                id: `cp_${i}`,
                name: p.name,
                x: cx + rx * Math.cos(angle),
                y: cy + ry * Math.sin(angle),
                r: 16 + 22 * Math.sqrt(p.total_volume / maxVol),
                isShell: p.is_shell_suspect,
                isCircular: isCircularParty(p.name, flags),
                profile: p,
            }
        })

        const allNodes = [appNode, ...cpNodes]

        // Build arrows
        const arrowList = []
        cpNodes.forEach(cp => {
            const p = cp.profile
            // Outflow: applicant → counterparty (debit)
            if (p.debit_volume > 0) {
                arrowList.push({
                    from: appNode, to: cp,
                    amount: p.debit_volume,
                    color: C.ink,
                    type: 'outflow',
                    bend: 0.18,
                })
            }
            // Inflow: counterparty → applicant (credit)
            if (p.credit_volume > 0) {
                arrowList.push({
                    from: cp, to: appNode,
                    amount: p.credit_volume,
                    color: C.green,
                    type: 'inflow',
                    bend: p.debit_volume > 0 ? 0.18 : 0.05, // offset if bidirectional
                })
            }
        })

        // Override colors for circular flows
        const circularNames = new Set(
            flags.filter(f => f.flag_type === 'circular_loop').flatMap(f => [f.entity_a, f.entity_b])
        )
        arrowList.forEach(a => {
            if (circularNames.has(a.from.name) || circularNames.has(a.to.name)) {
                if (a.from.isApp || a.to.isApp) {
                    // Keep outflow dark, make inflow red for circular
                    if (a.type === 'inflow') a.color = C.red
                }
            }
        })

        return { nodes: allNodes, arrows: arrowList, W, H }
    }, [profiles, flags, applicantName])

    if (nodes.length === 0) return null

    const maxArrowAmt = Math.max(...arrows.map(a => a.amount), 1)

    return (
        <svg
            viewBox={`0 0 ${W} ${H}`}
            className="w-full"
            style={{ fontFamily: "'IBM Plex Mono', monospace" }}
        >
            {/* Defs: arrowheads */}
            <defs>
                <marker id="ah-ink" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
                    <polygon points="0 0, 8 3, 0 6" fill={C.ink} />
                </marker>
                <marker id="ah-green" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
                    <polygon points="0 0, 8 3, 0 6" fill={C.green} />
                </marker>
                <marker id="ah-red" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
                    <polygon points="0 0, 8 3, 0 6" fill={C.red} />
                </marker>
            </defs>

            {/* Arrows */}
            {arrows.map((a, i) => {
                const path = curvedPath(a.from.x, a.from.y, a.from.r, a.to.x, a.to.y, a.to.r, a.bend)
                const sw = 1.2 + 2.5 * (a.amount / maxArrowAmt)
                const markerId = a.color === C.red ? 'ah-red' : a.color === C.green ? 'ah-green' : 'ah-ink'
                const isHighlighted = hovered && (a.from.id === hovered || a.to.id === hovered)
                const isDimmed = hovered && !isHighlighted

                return (
                    <g key={i}>
                        <path
                            d={path}
                            fill="none"
                            stroke={a.color}
                            strokeWidth={isHighlighted ? sw + 1.5 : sw}
                            strokeOpacity={isDimmed ? 0.12 : isHighlighted ? 1 : 0.55}
                            markerEnd={`url(#${markerId})`}
                            strokeDasharray={a.color === C.red ? '6 3' : 'none'}
                        />
                    </g>
                )
            })}

            {/* Arrow amount labels (shown on hover) */}
            {hovered && arrows.filter(a => a.from.id === hovered || a.to.id === hovered).map((a, i) => {
                const path = curvedPath(a.from.x, a.from.y, a.from.r, a.to.x, a.to.y, a.to.r, a.bend)
                // Approximate midpoint of quadratic bezier
                const mx = (a.from.x + a.to.x) / 2
                const my = (a.from.y + a.to.y) / 2
                const dx = a.to.x - a.from.x, dy = a.to.y - a.from.y
                const dist = Math.sqrt(dx * dx + dy * dy)
                const nx = -(dy / dist) * dist * a.bend
                const ny = (dx / dist) * dist * a.bend
                const lx = mx + nx * 0.6, ly = my + ny * 0.6

                return (
                    <g key={`lbl-${i}`}>
                        <rect x={lx - 28} y={ly - 8} width={56} height={16} rx={2} fill={C.paper} stroke={a.color} strokeWidth={1} opacity={0.95} />
                        <text x={lx} y={ly + 4} textAnchor="middle" fontSize={9} fontWeight={700} fill={a.color}>
                            {fmtAmt(a.amount)}
                        </text>
                    </g>
                )
            })}

            {/* Nodes */}
            {nodes.map((node) => {
                const isHighlighted = hovered === node.id
                const isDimmed = hovered && !isHighlighted &&
                    !arrows.some(a => (a.from.id === hovered && a.to.id === node.id) || (a.to.id === hovered && a.from.id === node.id))

                let fill = C.paper, stroke = C.border, strokeW = 1.5, textColor = C.ink
                if (node.isApp) {
                    fill = C.ink; stroke = C.ink; strokeW = 2; textColor = C.paper
                } else if (node.isCircular) {
                    fill = '#FFF0F0'; stroke = C.red; strokeW = 2.5
                } else if (node.isShell) {
                    fill = '#FFF0F0'; stroke = C.red; strokeW = 2
                }

                return (
                    <g
                        key={node.id}
                        onMouseEnter={() => setHovered(node.id)}
                        onMouseLeave={() => setHovered(null)}
                        style={{ cursor: 'pointer' }}
                        opacity={isDimmed ? 0.25 : 1}
                    >
                        {/* Glow ring for circular/shell */}
                        {(node.isCircular || node.isShell) && !node.isApp && (
                            <circle cx={node.x} cy={node.y} r={node.r + 4} fill="none" stroke={C.red} strokeWidth={1} strokeDasharray="4 2" opacity={0.4} />
                        )}

                        {/* Main circle */}
                        <circle
                            cx={node.x} cy={node.y} r={node.r}
                            fill={fill} stroke={stroke} strokeWidth={isHighlighted ? strokeW + 1 : strokeW}
                        />

                        {/* Label inside for applicant, outside for counterparties */}
                        {node.isApp ? (
                            <>
                                <text x={node.x} y={node.y - 4} textAnchor="middle" fontSize={9} fontWeight={800} fill={textColor} style={{ textTransform: 'uppercase' }}>
                                    {truncLabel(node.name, 14)}
                                </text>
                                <text x={node.x} y={node.y + 8} textAnchor="middle" fontSize={7} fill={`${textColor}99`}>
                                    APPLICANT
                                </text>
                            </>
                        ) : (
                            <>
                                {/* Name below circle */}
                                <text x={node.x} y={node.y + node.r + 12} textAnchor="middle" fontSize={8} fontWeight={700} fill={C.ink}>
                                    {truncLabel(node.name, 20)}
                                </text>
                                {/* Volume inside circle */}
                                <text x={node.x} y={node.y + 3} textAnchor="middle" fontSize={8} fontWeight={700} fill={node.isCircular || node.isShell ? C.red : C.muted}>
                                    {fmtAmt(node.profile?.total_volume)}
                                </text>
                                {/* Badges */}
                                {node.isCircular && (
                                    <>
                                        <rect x={node.x - 22} y={node.y - node.r - 14} width={44} height={12} rx={2} fill={C.red} />
                                        <text x={node.x} y={node.y - node.r - 5} textAnchor="middle" fontSize={7} fontWeight={800} fill="white">
                                            CIRCULAR
                                        </text>
                                    </>
                                )}
                                {node.isShell && !node.isCircular && (
                                    <>
                                        <rect x={node.x - 15} y={node.y - node.r - 14} width={30} height={12} rx={2} fill={C.red} />
                                        <text x={node.x} y={node.y - node.r - 5} textAnchor="middle" fontSize={7} fontWeight={800} fill="white">
                                            SHELL
                                        </text>
                                    </>
                                )}
                            </>
                        )}
                    </g>
                )
            })}
        </svg>
    )
}

/* ── Legend bar ── */
function GraphLegend() {
    const items = [
        { color: C.ink, label: 'Outflow (Debit)', dash: false },
        { color: C.green, label: 'Inflow (Credit)', dash: false },
        { color: C.red, label: 'Circular / Round-trip', dash: true },
    ]
    return (
        <div className="flex items-center gap-5 flex-wrap">
            {items.map((it, i) => (
                <div key={i} className="flex items-center gap-2">
                    <svg width={24} height={8}>
                        <line x1={0} y1={4} x2={18} y2={4}
                            stroke={it.color} strokeWidth={2}
                            strokeDasharray={it.dash ? '4 2' : 'none'} />
                        <polygon points="18,1 24,4 18,7" fill={it.color} />
                    </svg>
                    <span className="text-[10px] font-mono text-muted uppercase">{it.label}</span>
                </div>
            ))}
            <div className="flex items-center gap-1.5">
                <div className="w-3 h-3 rounded-full border-2 border-red bg-red/10" />
                <span className="text-[10px] font-mono text-muted uppercase">Shell / Circular Entity</span>
            </div>
            <div className="flex items-center gap-1.5">
                <span className="text-[10px] font-mono text-muted">Circles sized by transaction volume</span>
            </div>
        </div>
    )
}

/* ── Detail Card (expandable) ── */
function DetailCard({ profile, flags, isExpanded, onToggle }) {
    const isShell = profile.is_shell_suspect
    const isCircular = isCircularParty(profile.name, flags)
    const relatedFlags = flags.filter(f =>
        f.entity_a === profile.name || f.entity_b === profile.name
    )
    const hasCritical = isShell || isCircular

    return (
        <div className={`border-2 ${hasCritical ? 'border-red bg-red/5' : 'border-border bg-paper'}`}>
            <button
                onClick={onToggle}
                className="w-full flex items-center justify-between p-2.5 cursor-pointer hover:bg-paper-raised text-left"
            >
                <div className="flex items-center gap-2 min-w-0 flex-1">
                    <div className={`w-1 self-stretch flex-shrink-0 ${hasCritical ? 'bg-red' : 'bg-border'}`} />
                    <span className="font-mono text-xs font-bold text-ink truncate">{profile.name}</span>
                    {isCircular && (
                        <span className="px-1 py-0.5 bg-red text-white text-[8px] font-mono font-bold uppercase flex items-center gap-0.5">
                            <RefreshCw size={7} />CIRCULAR
                        </span>
                    )}
                    {isShell && (
                        <span className="px-1 py-0.5 bg-red text-white text-[8px] font-mono font-bold uppercase">SHELL</span>
                    )}
                    {profile.mca_found && (
                        <span className={`px-1 py-0.5 text-[8px] font-mono font-bold uppercase border ${
                            profile.company_status?.toLowerCase().includes('active') ? 'border-green text-green' : 'border-red text-red'
                        }`}>
                            {profile.company_status || 'MCA'}
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-2 flex-shrink-0 ml-2">
                    <span className="text-[10px] font-mono text-muted">{fmtAmt(profile.total_volume)}</span>
                    {relatedFlags.length > 0 && (
                        <span className="px-1 py-0.5 text-[8px] font-mono font-bold bg-red text-white">
                            {relatedFlags.length} FLAG{relatedFlags.length > 1 ? 'S' : ''}
                        </span>
                    )}
                    <ChevronDown size={12} className={`text-muted transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                </div>
            </button>

            {isExpanded && (
                <div className="border-t border-border px-3 pb-3">
                    {/* MCA details */}
                    <div className="mt-2 flex flex-wrap gap-3 text-[10px] font-mono text-muted">
                        {profile.cin && <span>CIN: {profile.cin}</span>}
                        <span>Debit: {fmtAmt(profile.debit_volume)}</span>
                        <span>Credit: {fmtAmt(profile.credit_volume)}</span>
                        <span>Txns: {profile.txn_count}</span>
                        {profile.mca_found && <span>Capital: {fmtAmt(profile.paid_up_capital)}</span>}
                    </div>

                    {/* Shell reasons */}
                    {profile.shell_reasons?.length > 0 && (
                        <div className="mt-2 p-2 bg-red/5 border border-red">
                            <div className="text-[10px] font-mono font-bold text-red uppercase mb-1">Shell Indicators</div>
                            {profile.shell_reasons.map((r, j) => (
                                <p key={j} className="text-xs font-serif text-ink leading-relaxed">• {r}</p>
                            ))}
                        </div>
                    )}

                    {/* Flags */}
                    {relatedFlags.map((flag, i) => (
                        <div key={i} className={`mt-1.5 flex items-start gap-2 p-2 border ${
                            flag.severity === 'CRITICAL' ? 'border-red bg-red/10' : flag.severity === 'HIGH' ? 'border-red' : 'border-border'
                        }`}>
                            <AlertTriangle size={10} className="text-red mt-0.5 flex-shrink-0" />
                            <div className="min-w-0">
                                <span className="text-[9px] font-mono font-bold text-red uppercase">
                                    {flag.flag_type.replace(/_/g, ' ')} — {flag.severity}
                                </span>
                                <p className="text-xs font-serif text-ink mt-0.5">{flag.evidence}</p>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}

/* ══════════════════════════════════════════════════════════════
   MAIN COMPONENT
   ══════════════════════════════════════════════════════════════ */
export default function NetworkAnalysis({ data }) {
    const [expandedIdx, setExpandedIdx] = useState(null)

    const detected = data?.circular_trading_detected || false
    const flags = data?.relationship_flags || []
    const profiles = data?.counterparty_profiles || []
    const findings = data?.findings || []
    const loopFlags = flags.filter(f => f.flag_type === 'circular_loop')
    const roundTripCount = loopFlags.length

    if (!data || (!profiles.length && !flags.length)) {
        return (
            <div className="flex flex-col items-center justify-center p-10 bg-paper border-[3px] border-ink">
                <Shield size={36} className="text-muted mb-4" />
                <p className="text-sm font-display font-bold text-ink uppercase tracking-wide">No Counterparty Risk Detected</p>
                <p className="text-xs text-muted mt-2 max-w-sm text-center font-serif">
                    Upload a bank statement CSV to enable counterparty intelligence.
                    The system will look up transaction partners on MCA and detect
                    shared directors, shell entities, and circular flows.
                </p>
            </div>
        )
    }

    const shellCount = profiles.filter(p => p.is_shell_suspect).length
    const mcaMatches = profiles.filter(p => p.mca_found).length
    const applicantName = data?.nodes?.find(n => n.type === 'applicant')?.label?.split('\n')[0] || 'Applicant'

    /* Sort: circular first → shell → by flag count */
    const sortedProfiles = [...profiles].sort((a, b) => {
        const ac = isCircularParty(a.name, flags), bc = isCircularParty(b.name, flags)
        if (ac && !bc) return -1
        if (!ac && bc) return 1
        if (a.is_shell_suspect && !b.is_shell_suspect) return -1
        if (!a.is_shell_suspect && b.is_shell_suspect) return 1
        return (b.total_volume || 0) - (a.total_volume || 0)
    })

    return (
        <div className="flex flex-col gap-6 animate-fade-in">
            {/* ── SUMMARY BAR ── */}
            <div className="border-[3px] border-ink bg-paper p-5 relative">
                <div className="absolute -top-3 left-4 bg-paper px-2 font-display font-black text-ink uppercase tracking-wider text-sm flex items-center gap-2">
                    <div className="w-2 h-2 bg-ink" />
                    COUNTERPARTY INTELLIGENCE
                </div>

                <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mt-2">
                    <div className="border-2 border-border p-3">
                        <div className="text-[10px] font-mono font-bold text-muted uppercase mb-1">Counterparties</div>
                        <div className="text-2xl font-mono font-bold text-ink">{profiles.length}</div>
                    </div>
                    <div className="border-2 border-border p-3">
                        <div className="text-[10px] font-mono font-bold text-muted uppercase mb-1">MCA Matches</div>
                        <div className="text-2xl font-mono font-bold text-ink">{mcaMatches}</div>
                    </div>
                    <div className={`border-2 p-3 ${shellCount > 0 ? 'border-red' : 'border-border'}`}>
                        <div className="text-[10px] font-mono font-bold text-muted uppercase mb-1">Shell Suspects</div>
                        <div className={`text-2xl font-mono font-bold ${shellCount > 0 ? 'text-red' : 'text-green'}`}>{shellCount}</div>
                    </div>
                    <div className={`border-2 p-3 ${roundTripCount > 0 ? 'border-red' : 'border-border'}`}>
                        <div className="text-[10px] font-mono font-bold text-muted uppercase mb-1">Round-trips</div>
                        <div className={`text-2xl font-mono font-bold ${roundTripCount > 0 ? 'text-red' : 'text-green'}`}>{roundTripCount}</div>
                    </div>
                    <div className={`border-2 p-3 ${flags.length > 0 ? 'border-yellow' : 'border-border'}`}>
                        <div className="text-[10px] font-mono font-bold text-muted uppercase mb-1">Risk Flags</div>
                        <div className={`text-2xl font-mono font-bold ${flags.length > 0 ? 'text-yellow' : 'text-green'}`}>{flags.length}</div>
                    </div>
                </div>

                {detected && (
                    <div className="mt-4 p-3 border-2 border-red bg-red/5 flex items-center gap-2">
                        <Zap size={14} className="text-red" />
                        <span className="text-xs font-mono font-bold text-red uppercase">
                            Circular Trading Detected — P-06 Triggered (+200bps, −30% limit)
                        </span>
                    </div>
                )}
            </div>

            {/* ── P-06 CIRCULAR FLOW ALERT ── */}
            {detected && (
                <div className="border-[3px] border-red bg-red/5 p-6 relative">
                    <div className="absolute -top-3 left-4 bg-red px-2 py-0.5 font-mono font-bold text-white uppercase tracking-wider text-[10px] flex items-center gap-2">
                        <AlertTriangle size={10} />
                        RULE P-06 — CIRCULAR TRADING
                    </div>

                    {loopFlags.length > 0 && (
                        <div className="mt-2 flex flex-col gap-4">
                            {loopFlags.map((loop, i) => {
                                const d = loop.details || {}
                                const debitAmt = d.debit_amount ? fmtAmt(d.debit_amount) : null
                                const creditAmt = d.credit_amount ? fmtAmt(d.credit_amount) : null

                                return (
                                    <div key={i} className="border-2 border-red/40 bg-paper p-4">
                                        <div className="flex items-center gap-0 overflow-x-auto pb-2">
                                            <div className="flex-shrink-0 px-3 py-2 bg-ink text-paper border-2 border-ink">
                                                <div className="text-[10px] font-mono font-bold uppercase">{truncLabel(loop.entity_a, 22)}</div>
                                            </div>
                                            <div className="flex-shrink-0 flex flex-col items-center px-1">
                                                <div className="text-[9px] font-mono font-bold text-red mb-0.5">{debitAmt || 'OUT'}</div>
                                                <div className="flex items-center">
                                                    <div className="w-6 h-0.5 bg-red" />
                                                    <div className="w-0 h-0 border-t-[4px] border-t-transparent border-b-[4px] border-b-transparent border-l-[6px] border-l-red" />
                                                </div>
                                            </div>
                                            <div className="flex-shrink-0 px-3 py-2 bg-red/10 border-2 border-red">
                                                <div className="text-[10px] font-mono font-bold text-red uppercase">{truncLabel(loop.entity_b, 22)}</div>
                                                {d.via && <div className="text-[8px] font-mono text-muted uppercase">{d.via}</div>}
                                            </div>
                                            <div className="flex-shrink-0 flex flex-col items-center px-1">
                                                <div className="text-[9px] font-mono font-bold text-red mb-0.5">{creditAmt || 'BACK'}</div>
                                                <div className="flex items-center">
                                                    <div className="w-6 h-0.5 bg-red" />
                                                    <div className="w-0 h-0 border-t-[4px] border-t-transparent border-b-[4px] border-b-transparent border-l-[6px] border-l-red" />
                                                </div>
                                            </div>
                                            <div className="flex-shrink-0 px-3 py-2 bg-ink text-paper border-2 border-ink">
                                                <div className="text-[10px] font-mono font-bold uppercase">{truncLabel(loop.entity_a, 22)}</div>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-4 mt-2 text-[10px] font-mono text-muted">
                                            {d.days_gap != null && (
                                                <span className={d.days_gap <= 7 ? 'text-red font-bold' : ''}>{d.days_gap} day gap</span>
                                            )}
                                            {d.amount_ratio != null && (
                                                <span className={d.amount_ratio > 0.8 ? 'text-red font-bold' : ''}>
                                                    Amount match: {(d.amount_ratio * 100).toFixed(0)}%
                                                </span>
                                            )}
                                            <span className="text-red font-bold uppercase">Round-trip</span>
                                        </div>
                                    </div>
                                )
                            })}
                        </div>
                    )}

                    {findings.length > 0 && (
                        <div className="mt-3 flex flex-col gap-1.5">
                            {findings.map((f, i) => (
                                <div key={i} className="flex items-start gap-2">
                                    <div className="w-1 h-1 bg-red mt-1.5 flex-shrink-0" />
                                    <p className="text-xs font-serif text-ink leading-relaxed">{f}</p>
                                </div>
                            ))}
                        </div>
                    )}

                    <div className="border-t-2 border-red/30 mt-3 pt-2">
                        <p className="text-[10px] font-mono font-bold text-muted uppercase">
                            Penalty: <span className="text-red">+200 bps rate, −30% credit limit</span> · Requires manual review
                        </p>
                    </div>
                </div>
            )}

            {/* ── NETWORK GRAPH ── */}
            <div className="border-[3px] border-ink bg-paper p-5 relative">
                <div className="absolute -top-3 left-4 bg-paper px-2 font-display font-black text-ink uppercase tracking-wider text-sm flex items-center gap-2">
                    <div className="w-2 h-2 bg-ink" />
                    NETWORK MAP
                </div>

                <div className="mt-3 mb-3">
                    <GraphLegend />
                </div>

                <NetworkGraph
                    profiles={sortedProfiles}
                    flags={flags}
                    applicantName={applicantName}
                />

                <p className="text-[10px] font-mono text-muted text-center mt-2">
                    Hover over nodes to highlight connections
                </p>
            </div>

            {/* ── COUNTERPARTY DETAILS ── */}
            <div className="border-[3px] border-ink bg-paper p-5 relative">
                <div className="absolute -top-3 left-4 bg-paper px-2 font-display font-black text-ink uppercase tracking-wider text-sm flex items-center gap-2">
                    <div className="w-2 h-2 bg-ink" />
                    COUNTERPARTY DETAILS
                </div>

                <div className="flex flex-col gap-1.5 mt-2">
                    {sortedProfiles.map((profile, i) => (
                        <DetailCard
                            key={i}
                            profile={profile}
                            flags={flags}
                            isExpanded={expandedIdx === i}
                            onToggle={() => setExpandedIdx(expandedIdx === i ? null : i)}
                        />
                    ))}
                </div>
            </div>

            {/* ── METHODOLOGY ── */}
            <div className="border-2 border-border bg-paper p-4">
                <p className="text-[10px] font-mono text-muted uppercase leading-relaxed">
                    Counterparty intelligence is deterministic — bank statement counterparties are matched against MCA21 registry.
                    Shell detection uses: low paid-up capital (&lt;₹1L), recent incorporation (&lt;2 years), and shared director/address patterns.
                    Circles sized by transaction volume. No LLM calls are made.
                </p>
            </div>
        </div>
    )
}
