/**
 * NetworkAnalysis.jsx – Counterparty Intelligence
 * =================================================
 * Replaces the force graph with a readable relationship map.
 * Shows: applicant → counterparties with flags, shell detection,
 * and circular flow alerts. All on the brutalist cream theme.
 */
import { useState } from 'react'
import { AlertTriangle, Shield, Users, MapPin, Building2, ChevronDown, Zap } from 'lucide-react'

const SEVERITY_STYLE = {
    CRITICAL: { text: 'text-red', bg: 'bg-red/10', border: 'border-red', badge: 'bg-red text-white' },
    HIGH: { text: 'text-red', bg: 'bg-paper', border: 'border-red', badge: 'bg-red text-white' },
    MEDIUM: { text: 'text-yellow', bg: 'bg-yellow/5', border: 'border-yellow', badge: 'bg-yellow text-white' },
    LOW: { text: 'text-muted', bg: 'bg-paper', border: 'border-border', badge: 'bg-paper-raised text-ink border border-border' },
}

const FLAG_ICONS = {
    shared_director: Users,
    same_address: MapPin,
    shell_indicator: Building2,
    family_name: Users,
    circular_loop: AlertTriangle,
}

function CounterpartyCard({ profile, flags, isExpanded, onToggle, isCircular }) {
    const isShell = profile.is_shell_suspect
    const relatedFlags = flags.filter(f =>
        f.entity_a === profile.name || f.entity_b === profile.name
    )
    const worstSeverity = relatedFlags.reduce((worst, f) => {
        const order = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 }
        return (order[f.severity] || 3) < (order[worst] || 3) ? f.severity : worst
    }, 'LOW')
    const style = SEVERITY_STYLE[worstSeverity] || SEVERITY_STYLE.LOW

    return (
        <div className={`border-2 ${isShell ? 'border-red' : style.border} ${isShell ? 'bg-red/5' : 'bg-paper'} transition-colors duration-200`}>
            <button
                onClick={onToggle}
                className="w-full flex items-center justify-between p-3 cursor-pointer hover:bg-paper-raised text-left"
            >
                <div className="flex items-center gap-3 min-w-0 flex-1">
                    {/* Risk indicator */}
                    <div className={`w-1.5 self-stretch flex-shrink-0 ${isShell ? 'bg-red' : worstSeverity === 'CRITICAL' || worstSeverity === 'HIGH' ? 'bg-red' : worstSeverity === 'MEDIUM' ? 'bg-yellow' : 'bg-border'}`} />

                    <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-mono text-sm font-bold text-ink truncate tracking-tight">{profile.name}</span>
                            {isCircular && (
                                <span className="px-1.5 py-0.5 bg-red text-white text-[9px] font-mono font-bold uppercase tracking-widest border border-red">CIRCULAR</span>
                            )}
                            {isShell && (
                                <span className="px-1.5 py-0.5 bg-red text-white text-[9px] font-mono font-bold uppercase tracking-widest border border-red shadow-[2px_2px_0px_rgba(0,0,0,1)]">SHELL</span>
                            )}
                            {profile.mca_found && (
                                <span className={`px-1.5 py-0.5 text-[9px] font-mono font-bold uppercase border-2 shadow-[2px_2px_0px_rgba(0,0,0,0.1)] ${profile.company_status?.toLowerCase().includes('active')
                                        ? 'border-green text-green bg-green/5'
                                        : 'border-red text-red bg-red/5'
                                    }`}>
                                    {profile.company_status || 'MCA FOUND'}
                                </span>
                            )}
                            {!profile.mca_found && (
                                <span className="px-1.5 py-0.5 text-[9px] font-mono font-bold text-muted border-2 border-dashed border-border uppercase tracking-wider">UNVERIFIED</span>
                            )}
                        </div>
                        <div className="flex items-center gap-3 mt-0.5 text-[10px] font-mono text-muted uppercase font-bold tracking-tight">
                            {profile.cin && <span>CIN: {profile.cin}</span>}
                            <span>Vol: ₹{(profile.total_volume / 100000).toFixed(1)}L</span>
                            {profile.mca_found && <span>Cap: ₹{(profile.paid_up_capital / 100000).toFixed(1)}L</span>}
                        </div>
                    </div>
                </div>

                <div className="flex items-center gap-2 flex-shrink-0 ml-2">
                    {relatedFlags.length > 0 && (
                        <span className={`px-1.5 py-0.5 text-[9px] font-mono font-bold border-2 ${style.border} ${style.badge}`}>
                            {relatedFlags.length} FLAG{relatedFlags.length > 1 ? 'S' : ''}
                        </span>
                    )}
                    <ChevronDown size={14} className={`text-muted transition-transform duration-300 ${isExpanded ? 'rotate-180' : ''}`} />
                </div>
            </button>

            {isExpanded && (
                <div className="border-t-2 border-border px-3 pb-3 bg-paper-raised">
                    {/* Shell reasons */}
                    {profile.shell_reasons?.length > 0 && (
                        <div className="mt-3 p-3 bg-red/5 border-2 border-red shadow-[4px_4px_0px_rgba(239,68,68,0.1)]">
                            <div className="text-[10px] font-mono font-bold text-red uppercase tracking-widest mb-1.5 flex items-center gap-2">
                                <AlertTriangle size={12} />
                                Shell Indicators detected
                            </div>
                            {profile.shell_reasons.map((r, j) => (
                                <p key={j} className="text-xs font-serif text-ink leading-relaxed mb-1">• {r}</p>
                            ))}
                        </div>
                    )}

                    {/* Related flags */}
                    {relatedFlags.length > 0 && (
                        <div className="mt-3 flex flex-col gap-2">
                            {relatedFlags.map((flag, i) => {
                                const Icon = FLAG_ICONS[flag.flag_type] || AlertTriangle
                                const fs = SEVERITY_STYLE[flag.severity] || SEVERITY_STYLE.LOW
                                return (
                                    <div key={i} className={`flex items-start gap-3 p-3 border-2 ${fs.border} ${fs.bg} relative overflow-hidden`}>
                                        <div className={`absolute top-0 left-0 w-1 h-full ${fs.badge.split(' ')[0]}`} />
                                        <Icon size={14} className={`${fs.text} mt-0.5 flex-shrink-0`} />
                                        <div className="min-w-0">
                                            <div className="flex items-center gap-2">
                                                <span className={`text-[10px] font-mono font-bold uppercase tracking-wider ${fs.text}`}>
                                                    {flag.flag_type.replace(/_/g, ' ')}
                                                </span>
                                                <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 ${fs.badge}`}>
                                                    {flag.severity}
                                                </span>
                                            </div>
                                            <p className="text-xs font-serif text-ink mt-1 italic">"{flag.evidence}"</p>
                                            <div className="flex items-center gap-2 mt-1.5">
                                                <div className="h-[1px] w-4 bg-border" />
                                                <p className="text-[9px] font-mono text-muted uppercase font-bold">
                                                    {flag.entity_a} ⟷ {flag.entity_b}
                                                </p>
                                            </div>
                                        </div>
                                    </div>
                                )
                            })}
                        </div>
                    )}

                    {relatedFlags.length === 0 && !profile.shell_reasons?.length && (
                        <p className="mt-3 text-[10px] font-mono text-muted uppercase tracking-widest text-center py-2 italic font-bold">No specific risk flags</p>
                    )}
                </div>
            )}
        </div>
    )
}

function CircularFlowSVG({ loop }) {
    const details = loop.details || {}
    const debitAmt = details.debit_amount ? `₹${(details.debit_amount / 100000).toFixed(1)}L` : 'OUT'
    const creditAmt = details.credit_amount ? `₹${(details.credit_amount / 100000).toFixed(1)}L` : 'BACK'
    const gap = details.days_gap
    const ratio = details.amount_ratio

    return (
        <div className="relative p-3 border-2 border-red/40 bg-paper-raised group overflow-hidden">
            <div className="relative z-10 flex items-center gap-3">
                {/* Source Node */}
                <div className="flex flex-col items-center gap-1 flex-shrink-0">
                    <div className="w-9 h-9 bg-ink flex items-center justify-center border-2 border-ink">
                        <Building2 size={14} className="text-paper" />
                    </div>
                    <span className="text-[8px] font-mono font-black text-ink uppercase text-center max-w-[60px] leading-tight truncate">
                        {loop.entity_a.split(' ')[0]}
                    </span>
                </div>

                {/* Animated Flow Track — compact */}
                <div className="flex-1 h-16 relative flex items-center min-w-0">
                    <svg className="w-full h-full overflow-visible" viewBox="0 0 200 60" preserveAspectRatio="none">
                        <path d="M 10 18 Q 100 -8 190 18" fill="none" stroke="#ef4444" strokeWidth="2" strokeDasharray="4 4" className="animate-flow-dash" />
                        <text x="100" y="8" textAnchor="middle" className="fill-red font-mono" style={{ fontSize: '9px', fontWeight: 700 }}>{debitAmt}</text>
                        <path d="M 190 42 Q 100 68 10 42" fill="none" stroke="#ef4444" strokeWidth="2" className="opacity-50" />
                        <text x="100" y="58" textAnchor="middle" className="fill-red font-mono" style={{ fontSize: '9px', fontWeight: 700 }}>{creditAmt}</text>
                        <circle r="2.5" fill="#ef4444"><animateMotion dur="2s" repeatCount="indefinite" path="M 10 18 Q 100 -8 190 18" /></circle>
                        <circle r="2.5" fill="#ef4444"><animateMotion dur="2.5s" repeatCount="indefinite" path="M 190 42 Q 100 68 10 42" /></circle>
                    </svg>
                </div>

                {/* Counterparty Node */}
                <div className="flex flex-col items-center gap-1 flex-shrink-0">
                    <div className="w-9 h-9 bg-red/10 flex items-center justify-center border-2 border-red">
                        <Building2 size={14} className="text-red" />
                    </div>
                    <span className="text-[8px] font-mono font-black text-red uppercase text-center max-w-[60px] leading-tight truncate">
                        {loop.entity_b.split(' ')[0]}
                    </span>
                </div>
            </div>

            {/* Metadata — inline row */}
            <div className="flex items-center justify-center gap-3 mt-2 pt-2 border-t border-red/20">
                <span className={`px-1.5 py-0.5 border font-mono text-[9px] font-black ${gap <= 7 ? 'bg-red text-white border-red' : 'border-border text-ink'}`}>
                    {gap}d
                </span>
                <span className={`px-1.5 py-0.5 border font-mono text-[9px] font-black ${ratio > 0.8 ? 'bg-red text-white border-red' : 'border-border text-ink'}`}>
                    {(ratio * 100).toFixed(0)}%
                </span>
                <span className="px-1.5 py-0.5 border border-red text-red font-mono text-[9px] font-black uppercase">
                    ROUND-TRIP
                </span>
            </div>
        </div>
    )
}

export default function NetworkAnalysis({ data }) {
    const [expandedIdx, setExpandedIdx] = useState(null)

    const detected = data?.circular_trading_detected || false
    const flags = data?.relationship_flags || []
    const profiles = data?.counterparty_profiles || []
    const findings = data?.findings || []

    /* ── No data state ── */
    if (!data || (!profiles.length && !flags.length)) {
        return (
            <div className="flex flex-col items-center justify-center p-12 bg-paper border-[3px] border-ink shadow-[8px_8px_0px_rgba(0,0,0,0.05)]">
                <div className="w-16 h-16 bg-muted/10 flex items-center justify-center border-2 border-dashed border-muted mb-6">
                    <Shield size={32} className="text-muted opacity-50" />
                </div>
                <p className="text-lg font-display font-black text-ink uppercase tracking-widest">Inert Data Stream</p>
                <p className="text-xs text-muted mt-3 max-w-sm text-center font-serif italic leading-relaxed">
                    Upload a bank statement CSV to initialize counterparty intelligence.
                    The engine will map transaction linkages and flag high-risk registered entities.
                </p>
            </div>
        )
    }

    const shellCount = profiles.filter(p => p.is_shell_suspect).length
    const mcaMatches = profiles.filter(p => p.mca_found).length
    const applicantName = data?.nodes?.find(n => n.type === 'applicant')?.label?.split('\n')[0] || 'Applicant'

    const circularLoops = flags.filter(f => f.flag_type === 'circular_loop')

    return (
        <div className="flex flex-col gap-5 animate-fade-in max-w-4xl mx-auto">
            {/* ── SUMMARY DASH ── */}
            <div className="border-[3px] border-ink bg-paper p-4 relative shadow-[6px_6px_0px_rgba(0,0,0,1)]">
                <div className="absolute -top-3 left-4 bg-ink px-3 py-0.5 font-display font-black text-paper uppercase tracking-widest text-xs flex items-center gap-2">
                    <Zap size={10} fill="currentColor" />
                    Forensic Intelligence Summary
                </div>

                <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mt-2">
                    <div className="group">
                        <div className="text-[9px] font-mono font-black text-muted uppercase tracking-wider mb-1">Entities</div>
                        <div className="text-2xl font-mono font-black text-ink">{profiles.length}</div>
                    </div>
                    <div className="group">
                        <div className="text-[9px] font-mono font-black text-muted uppercase tracking-wider mb-1">MCA Verified</div>
                        <div className="text-2xl font-mono font-black text-ink">{mcaMatches}</div>
                    </div>
                    <div className="group">
                        <div className="text-[9px] font-mono font-black text-muted uppercase tracking-wider mb-1">Shell Suspects</div>
                        <div className={`text-2xl font-mono font-black ${shellCount > 0 ? 'text-red animate-pulse' : 'text-green opacity-40'}`}>{shellCount}</div>
                    </div>
                    <div className="group">
                        <div className="text-[9px] font-mono font-black text-muted uppercase tracking-wider mb-1">Risk Flags</div>
                        <div className={`text-2xl font-mono font-black ${flags.length > 0 ? 'text-yellow' : 'text-green opacity-40'}`}>{flags.length}</div>
                    </div>
                    <div className="group">
                        <div className="text-[9px] font-mono font-black text-muted uppercase tracking-wider mb-1">Round-trips</div>
                        <div className={`text-2xl font-mono font-black ${circularLoops.length > 0 ? 'text-red' : 'text-green opacity-40'}`}>{circularLoops.length}</div>
                    </div>
                </div>

                {detected && (
                    <div className="mt-4 p-3 border-2 border-red bg-red/5 flex items-center gap-3 border-l-[6px]">
                        <div className="w-8 h-8 bg-red flex items-center justify-center flex-shrink-0">
                            <AlertTriangle size={16} className="text-white" />
                        </div>
                        <div className="flex-1">
                            <span className="text-[10px] font-mono font-black text-red uppercase tracking-widest block leading-none mb-0.5">
                                P-06: CIRCULAR TRADING DETECTED
                            </span>
                            <span className="text-[9px] font-mono font-bold text-red/80 uppercase tracking-tight">
                                +200bps RATE · -30% LIMIT · HIGH RISK
                            </span>
                        </div>
                    </div>
                )}
            </div>

            {/* ── P-06 CIRCULAR FLOWS (grid, before entity list) ── */}
            {circularLoops.length > 0 && (
                <div className="border-[3px] border-red bg-paper p-4 relative">
                    <div className="absolute -top-3 left-4 bg-red px-2 py-0.5 font-mono font-black text-white uppercase tracking-tighter text-[10px] flex items-center gap-2">
                        <AlertTriangle size={10} />
                        P-06 ROUND-TRIP FLOWS
                    </div>

                    <div className={`grid gap-3 mt-2 ${circularLoops.length === 1 ? 'grid-cols-1 max-w-md' : circularLoops.length === 2 ? 'grid-cols-2' : 'grid-cols-2 lg:grid-cols-3'}`}>
                        {circularLoops.map((loop, i) => (
                            <CircularFlowSVG key={i} loop={loop} />
                        ))}
                    </div>

                    {findings.length > 0 && (
                        <div className="border-t-2 border-red/20 pt-3 mt-3 flex flex-col gap-1.5">
                            <div className="text-[9px] font-mono font-black text-red uppercase tracking-widest">Auditor Narrative</div>
                            {findings.map((f, i) => (
                                <div key={i} className="flex items-start gap-2">
                                    <div className="w-1 h-1 bg-red mt-1.5 flex-shrink-0" />
                                    <p className="text-[10px] font-serif text-ink italic leading-relaxed opacity-90">{f}</p>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* ── ENTITY LINKAGE MAP ── */}
            <div className="border-[3px] border-ink bg-paper p-4 relative">
                <div className="absolute -top-3 left-4 bg-paper border-2 border-ink px-3 py-0.5 font-display font-black text-ink uppercase tracking-widest text-xs">
                    Entity Linkage Map
                </div>

                {/* Applicant Hub */}
                <div className="flex items-center gap-3 mb-4 p-3 border-[3px] border-ink bg-ink text-paper group overflow-hidden relative">
                    <div className="absolute top-0 right-0 p-1 opacity-10 group-hover:opacity-30 transition-opacity">
                        <Shield size={48} />
                    </div>
                    <div className="w-10 h-10 bg-paper flex items-center justify-center border-2 border-ink">
                        <Building2 size={16} className="text-ink" />
                    </div>
                    <div>
                        <div className="text-sm font-mono font-black uppercase tracking-tight leading-none mb-0.5">{applicantName}</div>
                        <div className="text-[9px] font-mono font-bold text-paper/60 uppercase tracking-widest italic">Primary Subject</div>
                    </div>
                </div>

                <div className="flex flex-col gap-2">
                    {profiles
                        .sort((a, b) => {
                            // Circular parties first
                            const aCirc = flags.some(f => f.flag_type === 'circular_loop' && (f.entity_a === a.name || f.entity_b === a.name))
                            const bCirc = flags.some(f => f.flag_type === 'circular_loop' && (f.entity_a === b.name || f.entity_b === b.name))
                            if (aCirc && !bCirc) return -1
                            if (!aCirc && bCirc) return 1
                            if (a.is_shell_suspect && !b.is_shell_suspect) return -1
                            if (!a.is_shell_suspect && b.is_shell_suspect) return 1
                            const aFlags = flags.filter(f => f.entity_a === a.name || f.entity_b === a.name).length
                            const bFlags = flags.filter(f => f.entity_a === b.name || f.entity_b === b.name).length
                            return bFlags - aFlags
                        })
                        .map((profile, i) => {
                            const isCircularParty = flags.some(f => f.flag_type === 'circular_loop' && (f.entity_a === profile.name || f.entity_b === profile.name))
                            return (
                                <div key={i} className="flex items-start">
                                    {/* Connector */}
                                    <div className="w-8 flex-shrink-0 flex flex-col items-center pt-4">
                                        <div className={`w-2.5 h-2.5 border-2 ${isCircularParty ? 'border-red bg-red' : profile.is_shell_suspect ? 'border-red bg-red' : 'border-ink'} rotate-45 mb-1`} />
                                        <div className={`w-[2px] h-6 border-l-2 border-dashed ${isCircularParty ? 'border-red/60' : profile.is_shell_suspect ? 'border-red/40' : 'border-border'}`} />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <CounterpartyCard
                                            profile={profile}
                                            flags={flags}
                                            isExpanded={expandedIdx === i}
                                            onToggle={() => setExpandedIdx(expandedIdx === i ? null : i)}
                                            isCircular={isCircularParty}
                                        />
                                    </div>
                                </div>
                            )
                        })
                    }
                </div>
            </div>

            {/* Methodology — compact */}
            <div className="border border-border bg-paper px-4 py-2 opacity-50 hover:opacity-80 transition-opacity">
                <p className="text-[8px] font-mono text-ink tracking-tight uppercase font-bold">
                    MCA v3 cross-ref · Shell threshold: &lt;1L cap + &lt;2yr lifecycle · Deterministic · <span className="underline underline-offset-2">No LLM</span>
                </p>
            </div>

            <style dangerouslySetInnerHTML={{
                __html: `
                @keyframes flow-dash {
                    to { stroke-dashoffset: -20; }
                }
                .animate-flow-dash {
                    stroke-dasharray: 5 5;
                    animation: flow-dash 1s linear infinite;
                }
            `}} />
        </div>
    )
}
