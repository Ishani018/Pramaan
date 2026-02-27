import React from 'react';
import { ShieldCheck, AlertTriangle, TrendingDown, AlignLeft, Calendar } from 'lucide-react';

export default function RestatementAnalysis({ restatementData, pdfResult }) {
    if (!restatementData) {
        // Fallback for single file upload or if analysis hasn't run
        return (
            <div className="flex flex-col items-center justify-center p-10 h-full text-center space-y-4 text-muted">
                <Calendar size={48} className="text-surface border border-border rounded-full p-2 mb-2 bg-void" />
                <h3 className="text-lg font-semibold text-text">Insufficient History</h3>
                <p className="max-w-md text-sm">
                    Upload multiple years (e.g., FY22, FY23, FY24) to enable automated year-over-year comparative analysis and detect silent financial restatements.
                </p>
            </div>
        );
    }

    const { restatements_detected, restatements, auditor_changed, auditor_history } = restatementData;

    return (
        <div className="flex flex-col gap-6 h-full pb-10">
            {/* ── Banner ───────────────────────────────────────────────────────── */}
            <div className={`flex items-center gap-3 p-4 rounded-xl border ${restatements_detected
                ? 'bg-danger/10 border-danger/30 text-danger'
                : 'bg-success/10 border-success/30 text-success'
                }`}>
                {restatements_detected ? (
                    <AlertTriangle size={24} className="flex-shrink-0 animate-pulse" />
                ) : (
                    <ShieldCheck size={24} className="flex-shrink-0" />
                )}
                <div>
                    <h2 className="text-sm font-bold uppercase tracking-widest">
                        {restatements_detected ? 'RESTATEMENT DETECTED [P-09]' : 'CLEAN COMPARATIVES'}
                    </h2>
                    <p className="text-xs mt-1 opacity-90">
                        {restatements_detected
                            ? `${restatements.length} figures flagged for >2% variance across YoY comparative columns.`
                            : 'All multi-year comparative columns tie exactly to previous filings.'}
                    </p>
                </div>
            </div>

            {/* ── Auditor Timeline ─────────────────────────────────────────────── */}
            <div className="glass p-5 rounded-xl border border-border">
                <div className="flex items-center justify-between mb-4">
                    <h3 className="font-semibold text-text flex items-center gap-2 text-sm">
                        <AlignLeft size={16} className="text-accent" />
                        Statutory Auditor Continuity
                    </h3>
                    {auditor_changed && (
                        <span className="badge bg-accent/20 text-accent font-bold text-xs ring-1 ring-accent/30">
                            ROTATION FLAG [P-10]
                        </span>
                    )}
                </div>

                <div className="flex items-center gap-2 overflow-x-auto pb-2">
                    {Object.entries(auditor_history || {}).sort((a, b) => a[0].localeCompare(b[0])).map(([year, auditor], idx, arr) => {
                        const isChanged = idx > 0 && auditor !== arr[idx - 1][1];
                        return (
                            <React.Fragment key={year}>
                                <div className={`flex flex-col gap-1 p-3 rounded-lg border min-w-[140px] flex-shrink-0 ${isChanged ? 'bg-accent/10 border-accent/30' : 'bg-surface/50 border-border'}`}>
                                    <span className="text-xs font-mono text-muted">{year}</span>
                                    <span className={`text-sm truncate font-medium ${isChanged ? 'text-accent' : 'text-text'}`} title={auditor}>
                                        {auditor}
                                    </span>
                                </div>
                                {idx < arr.length - 1 && (
                                    <div className="w-8 h-[2px] bg-border flex-shrink-0" />
                                )}
                            </React.Fragment>
                        );
                    })}
                </div>
            </div>

            {/* ── Restatement Table ────────────────────────────────────────────── */}
            {restatements && restatements.length > 0 && (
                <div className="glass p-5 rounded-xl border border-border">
                    <h3 className="font-semibold text-text flex items-center gap-2 text-sm mb-4">
                        <TrendingDown size={16} className="text-danger" />
                        Flagged Variances (&gt;2%)
                    </h3>

                    <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm whitespace-nowrap">
                            <thead className="bg-surface/50 text-muted uppercase text-xs border-b border-border">
                                <tr>
                                    <th className="px-4 py-3 font-semibold rounded-tl-lg">Figure</th>
                                    <th className="px-4 py-3 font-semibold">Target FY</th>
                                    <th className="px-4 py-3 font-semibold text-right">Original Value</th>
                                    <th className="px-4 py-3 font-semibold text-right">Restated Value</th>
                                    <th className="px-4 py-3 font-semibold text-right">Variance</th>
                                    <th className="px-4 py-3 font-semibold text-center rounded-tr-lg">Flag</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-border/50 text-text/90 bg-void/30">
                                {restatements.map((r, i) => (
                                    <tr key={i} className="hover:bg-surface/20 transition-colors">
                                        <td className="px-4 py-3 font-medium">{r.figure}</td>
                                        <td className="px-4 py-3 font-mono text-muted">{r.year_restated}</td>
                                        <td className="px-4 py-3 text-right font-mono">{r.original_value.toLocaleString()}</td>
                                        <td className="px-4 py-3 text-right font-mono">{r.restated_value.toLocaleString()}</td>
                                        <td className="px-4 py-3 text-right font-mono font-bold text-danger">
                                            {r.change_pct > 0 ? '+' : ''}{r.change_pct}%
                                        </td>
                                        <td className="px-4 py-3 text-center">
                                            <span className={`badge text-xs px-2 py-0.5 ${r.severity === 'CRITICAL'
                                                ? 'bg-danger/20 text-danger border border-danger/30'
                                                : 'bg-accent/20 text-accent border border-accent/30'
                                                }`}>
                                                {r.severity}
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    );
}
