/**
 * ScorePanel – Exploration vs Exploitation animated radial gauges
 * Displays the CEO ambidexterity scores returned by the backend.
 */
import { useEffect, useState } from 'react'
import { Zap, Search, Scale, BookOpen, FileSearch } from 'lucide-react'

const RADIUS = 40
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

function RadialGauge({ label, score, color, icon: Icon, delay = 0 }) {
    const [animated, setAnimated] = useState(0)

    useEffect(() => {
        const t = setTimeout(() => setAnimated(score), delay)
        return () => clearTimeout(t)
    }, [score, delay])

    const offset = CIRCUMFERENCE - (animated / 0.02) * CIRCUMFERENCE * 0.01
    // score is typically 0.000–0.020 range; normalise to 0–100%
    const pct = Math.min((score / 0.015) * 100, 100)
    const displayOffset = CIRCUMFERENCE * (1 - pct / 100)

    return (
        <div className="flex flex-col items-center gap-2">
            <div className="relative w-24 h-24">
                <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
                    {/* Track */}
                    <circle cx="50" cy="50" r={RADIUS} fill="none" stroke="#1E2D4A" strokeWidth="8" />
                    {/* Value */}
                    <circle
                        cx="50" cy="50" r={RADIUS}
                        fill="none"
                        stroke={color}
                        strokeWidth="8"
                        strokeDasharray={CIRCUMFERENCE}
                        strokeDashoffset={displayOffset}
                        strokeLinecap="round"
                        className="score-ring"
                    />
                </svg>
                {/* Centre icon */}
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <Icon size={14} style={{ color }} />
                    <span className="text-xs font-mono font-bold text-text mt-0.5">
                        {(score * 100).toFixed(3)}
                    </span>
                </div>
            </div>
            <p className="text-xs text-muted text-center font-medium leading-tight">{label}</p>
        </div>
    )
}

function KeywordList({ title, keywords, color }) {
    if (!keywords || Object.keys(keywords).length === 0) return null
    return (
        <div>
            <p className="label mb-2">{title}</p>
            <div className="flex flex-wrap gap-1.5">
                {Object.entries(keywords).map(([kw, count]) => (
                    <span
                        key={kw}
                        className="text-xs px-2 py-0.5 rounded-full border font-mono"
                        style={{ color, borderColor: `${color}40`, background: `${color}10` }}
                    >
                        {kw} <span className="opacity-70">×{count}</span>
                    </span>
                ))}
            </div>
        </div>
    )
}

function StatRow({ label, value, mono = false }) {
    return (
        <div className="flex items-center justify-between py-1.5 border-b border-border last:border-0">
            <span className="text-xs text-muted">{label}</span>
            <span className={`text-xs text-text font-medium ${mono ? 'font-mono' : ''}`}>{value ?? '—'}</span>
        </div>
    )
}

export default function ScorePanel({ result, loading }) {
    if (loading) {
        return (
            <div className="glass p-5 animate-fade-in">
                <h3 className="font-semibold text-text mb-4 flex items-center gap-2">
                    <Scale size={15} className="text-accent" /> Ambidexterity Analysis
                </h3>
                <div className="space-y-3">
                    {[120, 80, 60, 100, 60].map((w, i) => (
                        <div key={i} className={`shimmer h-4 rounded-lg`} style={{ width: `${w}px` }} />
                    ))}
                </div>
            </div>
        )
    }

    if (!result) {
        return (
            <div className="glass p-5 animate-fade-in flex flex-col items-center justify-center text-center py-10">
                <FileSearch size={32} className="text-muted mb-3" />
                <p className="font-medium text-text text-sm">No analysis yet</p>
                <p className="text-xs text-muted mt-1">Upload a PDF and click Analyse Report</p>
            </div>
        )
    }

    if (!result.section_found) {
        return (
            <div className="glass p-5 animate-fade-in">
                <div className="flex items-center gap-2 text-warn mb-3">
                    <Search size={15} />
                    <p className="font-semibold text-sm">MD&A Section Not Found</p>
                </div>
                <p className="text-xs text-muted leading-relaxed">{result.message}</p>
            </div>
        )
    }

    return (
        <div className="glass p-5 animate-slide-up space-y-5">
            {/* Header */}
            <div className="flex items-center justify-between">
                <h3 className="font-semibold text-text flex items-center gap-2">
                    <Scale size={15} className="text-accent" /> Ambidexterity Analysis
                </h3>
                <span className="badge bg-success/15 text-success">MD&A Found</span>
            </div>

            {/* Gauges */}
            <div className="flex items-center justify-around py-2">
                <RadialGauge
                    label="Exploration"
                    score={result.exploration_score}
                    color="#3B82F6"
                    icon={Search}
                    delay={100}
                />
                <div className="text-center">
                    <p className="text-xs text-muted">Ratio</p>
                    <p className="font-mono font-bold text-text text-lg">
                        {typeof result.exploration_exploitation_ratio === 'number'
                            ? result.exploration_exploitation_ratio.toFixed(2)
                            : result.exploration_exploitation_ratio}
                    </p>
                    <p className="text-xs text-muted mt-0.5">E/E</p>
                </div>
                <RadialGauge
                    label="Exploitation"
                    score={result.exploitation_score}
                    color="#F59E0B"
                    icon={Zap}
                    delay={200}
                />
            </div>

            {/* Stats */}
            <div className="bg-void rounded-lg px-3 py-1">
                <StatRow label="MD&A Pages" value={`${result.mdna_pages?.start} – ${result.mdna_pages?.end}`} />
                <StatRow label="Page Count" value={result.mdna_pages?.page_count} />
                <StatRow label="Total Words" value={result.mdna_word_count?.toLocaleString()} mono />
                <StatRow label="Detection Conf." value={`${(result.detection_confidence * 100).toFixed(1)}%`} />
                <StatRow label="Headings Found" value={result.hierarchy_summary?.heading_count} />
                <StatRow label="Ambidexterity" value={result.ambidexterity_score?.toFixed(6)} mono />
            </div>

            {/* Detected heading */}
            {result.detected_heading && (
                <div className="bg-accent/10 border border-accent/20 rounded-lg px-3 py-2">
                    <p className="text-xs text-muted mb-0.5">Detected MD&A Heading</p>
                    <p className="text-sm font-medium text-accent">"{result.detected_heading}"</p>
                </div>
            )}

            {/* Top sub-headings */}
            {result.hierarchy_summary?.top_headings?.length > 0 && (
                <div>
                    <p className="label mb-2">MD&A Sub-sections</p>
                    <div className="space-y-1">
                        {result.hierarchy_summary.top_headings.map((h, i) => (
                            <div key={i} className="flex items-center gap-2 text-xs text-muted">
                                <span className="w-1.5 h-1.5 rounded-full bg-accent/50 flex-shrink-0" />
                                {h}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Top keywords */}
            <KeywordList
                title="Top Exploration Keywords"
                keywords={result.top_exploration_keywords}
                color="#3B82F6"
            />
            <KeywordList
                title="Top Exploitation Keywords"
                keywords={result.top_exploitation_keywords}
                color="#F59E0B"
            />

            {/* Methodology note */}
            <div className="flex gap-2 bg-void/60 rounded-lg p-2.5">
                <BookOpen size={13} className="text-muted flex-shrink-0 mt-0.5" />
                <p className="text-xs text-muted leading-relaxed">{result.methodology}</p>
            </div>
        </div>
    )
}
