import { ShieldAlert, ShieldCheck, AlertCircle, FileSearch, ChevronDown, ChevronUp } from 'lucide-react'
import { useState } from 'react'

function FlagCard({ label, found, ruleId, description }) {
    return (
        <div className={`p-5 flex items-start gap-4 border-b-2 ${found ? 'border-red bg-red-light' : 'border-border bg-paper'}`}>
            <div className={`w-10 h-10 flex items-center justify-center flex-shrink-0 border-2 ${found ? 'border-red bg-red text-white' : 'border-ink bg-paper text-ink'}`}>
                {found
                    ? <ShieldAlert size={20} />
                    : <ShieldCheck size={20} />
                }
            </div>
            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-3 mb-1">
                    <h2 className={`font-display font-black text-xl md:text-2xl tracking-wide uppercase ${found ? 'text-red' : 'text-ink'}`}>
                        {label}
                    </h2>
                    {found && ruleId && (
                        <span className="px-2 py-0.5 border-2 border-red bg-red text-white text-xs font-mono font-bold uppercase tracking-wider">
                            {ruleId} TRIGGERED
                        </span>
                    )}
                </div>
                <p className="text-sm font-serif text-ink leading-relaxed">{description}</p>
            </div>
        </div>
    )
}

function FindingList({ title, findings, color }) {
    const [expanded, setExpanded] = useState(false)
    if (!findings?.length) return null
    return (
        <div className="border-b-2 border-border">
            <button
                onClick={() => setExpanded(e => !e)}
                className="w-full flex items-center justify-between p-4 cursor-pointer hover:bg-paper-raised transition-none"
            >
                <span className="font-display font-bold uppercase text-ink tracking-widest text-sm">
                    {title} [{findings.length}]
                </span>
                {expanded ? <ChevronUp size={16} className="text-ink" /> : <ChevronDown size={16} className="text-ink" />}
            </button>
            {expanded && (
                <div className="px-4 pb-6 space-y-4">
                    {findings.map((f, i) => (
                        <div key={i} className="pl-4 border-l-4 border-red py-1">
                            <div className="flex items-center gap-2 mb-2">
                                <span className="text-xs font-mono font-bold uppercase tracking-wider text-red border border-red px-2 py-0.5" style={{ borderColor: color, color: color }}>
                                    {f.pattern}
                                </span>
                            </div>
                            <blockquote className="text-sm font-serif italic text-ink leading-relaxed whitespace-pre-wrap">
                                “{f.snippet}”
                            </blockquote>
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}

function SectionBadge({ label, info }) {
    if (!info) return null
    return (
        <div className="flex items-center justify-between py-2 border-b-2 border-border last:border-0">
            <span className="text-sm font-serif text-ink font-bold">{label}</span>
            <span className="text-xs text-ink font-mono font-bold bg-paper-raised px-2 py-1 border border-border">
                p.{info.start_page}–{info.end_page}
                <span className="text-ink ml-2">({info.page_count} pages)</span>
            </span>
        </div>
    )
}

export default function CompliancePanel({ result, loading }) {
    if (loading) {
        return (
            <div className="space-y-4">
                {[100, 80, 120, 60].map((w, i) => (
                    <div key={i} className="shimmer h-20 border-2 border-border w-full" />
                ))}
            </div>
        )
    }

    if (!result) {
        return (
            <div className="border-2 border-border bg-paper p-10 flex flex-col items-center justify-center text-center py-16">
                <FileSearch size={48} className="text-ink mb-4" />
                <h2 className="font-display font-black text-2xl uppercase text-ink">No Analysis Yet</h2>
                <p className="text-sm font-serif text-ink mt-2">Upload an annual report PDF and run the credit committee</p>
            </div>
        )
    }

    if (result.status === 'section_not_found') {
        return (
            <div className="border-[3px] border-red bg-red-light p-6">
                <div className="flex items-center gap-3 text-red mb-3">
                    <AlertCircle size={24} />
                    <h2 className="font-display font-black text-2xl uppercase">Section Not Found</h2>
                </div>
                <p className="text-sm font-serif text-ink">{result.message}</p>
            </div>
        )
    }

    const totalIssues = (result.total_caro_matches || 0) + (result.total_qualification_matches || 0)

    return (
        <div className="border-[3px] border-border bg-paper flex flex-col">
            {/* Summary header */}
            <div className={`p-6 flex items-center gap-4 border-b-[3px] ${totalIssues > 0 ? 'border-red bg-red-light' : 'border-border bg-paper'}`}>
                <div className={`w-14 h-14 flex items-center justify-center border-2 border-ink flex-shrink-0
                         ${totalIssues > 0 ? 'bg-red text-white' : 'bg-paper text-ink'}`}>
                    {totalIssues > 0
                        ? <ShieldAlert size={28} />
                        : <ShieldCheck size={28} />
                    }
                </div>
                <div>
                    <h1 className={`font-display font-black text-3xl uppercase tracking-tight ${totalIssues > 0 ? 'text-red' : 'text-ink'}`}>
                        {totalIssues > 0 ? `${totalIssues} Compliance Issue${totalIssues > 1 ? 's' : ''} Found` : 'Clean Report — No Issues Found'}
                    </h1>
                    <p className="font-mono text-xs font-bold text-ink uppercase mt-2">Source file: {result.file_name}</p>
                </div>
            </div>

            {/* Boolean flags */}
            <div className="flex flex-col">
                <FlagCard
                    label="CARO 2020 Statutory Default"
                    found={result.caro_default_found}
                    ruleId="P-03"
                    description={
                        result.caro_default_found
                            ? `${result.total_caro_matches} match(es) found — statutory dues not deposited under Clause (vii)`
                            : 'No statutory default mentioned under CARO 2020 Clause (vii)'
                    }
                />
                <FlagCard
                    label="Auditor Qualification"
                    found={result.adverse_opinion_found}
                    ruleId="P-03"
                    description={
                        result.adverse_opinion_found
                            ? `${result.total_qualification_matches} qualification(s) detected — "Except for", "Adverse", or "Qualified" opinion`
                            : 'Auditor issued an unqualified (clean) opinion'
                    }
                />
                {result.emphasis_of_matter_found && (
                    <FlagCard
                        label="Emphasis of Matter / Going Concern"
                        found={true}
                        ruleId="P-04"
                        description="Auditor flagged going concern or material uncertainty — requires manual credit committee review"
                    />
                )}
            </div>

            {/* Section detected */}
            <div className="p-6 border-b-2 border-border bg-paper-raised">
                <h3 className="font-display font-bold uppercase tracking-wider text-sm mb-4 border-b-2 border-border pb-2 inline-block">
                    Sections Scanned
                </h3>
                <div className="bg-paper border-2 border-border p-4">
                    <SectionBadge label="Independent Auditor's Report" info={result.sections_detected?.auditors_report} />
                    <SectionBadge label="Annexure to Auditor's Report (CARO)" info={result.sections_detected?.auditors_annexure} />
                </div>
            </div>

            {/* Evidence drawers */}
            <div className="border-t-[3px] border-border">
                <FindingList
                    title="CARO 2020 Findings"
                    findings={result.caro_findings}
                    color="var(--red)"
                />
                <FindingList
                    title="Auditor Qualification Findings"
                    findings={result.auditor_qualification_findings}
                    color="var(--red)"
                />
                {result.emphasis_of_matter_found && (
                    <FindingList
                        title="Emphasis of Matter Findings"
                        findings={result.emphasis_findings}
                        color="var(--gold)"
                    />
                )}
            </div>

            {/* Methodology note */}
            <div className="flex gap-3 bg-ink p-4 text-paper">
                <AlertCircle size={14} className="flex-shrink-0 mt-0.5" />
                <p className="text-xs font-mono uppercase tracking-wide leading-relaxed">{result.methodology}</p>
            </div>
        </div>
    )
}
