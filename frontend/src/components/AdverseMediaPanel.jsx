import React from 'react';
import { ShieldAlert, ExternalLink, Shield } from 'lucide-react';
import { RULE_DISPLAY_NAMES } from '../App';

export default function AdverseMediaPanel({ newsData }) {
    if (!newsData || newsData.articles_found === 0) {
        return (
            <div className="flex flex-col items-center justify-center p-12 border-2 border-border h-full bg-paper">
                <Shield className="w-16 h-16 text-[#167A3E] mb-4" />
                <div className="border-[3px] border-[#167A3E] text-[#167A3E] px-4 py-2 font-mono font-bold uppercase tracking-widest transform -rotate-2">
                    NO ADVERSE MEDIA DETECTED
                </div>
                <p className="mt-4 font-mono text-xs text-muted">
                    No high-severity red flags found in recent news for {newsData?.entity || "this entity"}.
                </p>
                <div className="mt-auto font-mono text-xs font-bold text-ink border-t-2 border-border w-full text-center pt-4">
                    SOURCE: NEWSAPI.ORG — LIVE SEARCH
                </div>
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full bg-paper border-2 border-border">
            {/* Red Banner for Adverse Media Detected */}
            {newsData.adverse_media_detected && (
                <div className="bg-red text-white p-4 font-display font-black uppercase text-xl border-b-2 border-border flex items-center gap-3">
                    <ShieldAlert className="w-6 h-6" />
                    ADVERSE MEDIA DETECTED — {RULE_DISPLAY_NAMES["P-13"] || "P-13"} TRIGGERED
                </div>
            )}

            <div className="p-6 overflow-y-auto flex-1 flex flex-col gap-4">
                <div className="font-mono text-xs font-bold text-ink mb-2">
                    Found {newsData.articles_found} articles with {newsData.red_flags.length} red flags for: <span className="bg-ink text-white px-2 py-0.5">{newsData.entity}</span>
                </div>

                {newsData.red_flags.map((flag, idx) => {
                    const isHigh = flag.severity === "HIGH";
                    const severityColor = isHigh ? "bg-red text-white" : "bg-[#D4A017] text-white";

                    return (
                        <div key={idx} className="border-[3px] border-ink p-5 bg-paper relative flex flex-col gap-3">
                            {/* Top row: Severity badge + Source/Date */}
                            <div className="flex justify-between items-start">
                                <span className={`font-mono text-xs font-bold px-2 py-1 uppercase tracking-wider ${severityColor}`}>
                                    [{flag.severity}]
                                </span>
                                <div className="text-right">
                                    <div className="font-mono text-xs font-bold text-ink uppercase">{flag.source}</div>
                                    <div className="font-mono text-[10px] text-muted">{new Date(flag.published_at).toLocaleDateString()}</div>
                                </div>
                            </div>

                            {/* Headline */}
                            <h3 className="font-display font-bold text-lg text-ink leading-tight">
                                {flag.headline}
                            </h3>

                            {/* Link */}
                            {flag.url && (
                                <a
                                    href={flag.url}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="mt-2 self-start flex items-center gap-1 font-mono text-xs font-bold text-ink hover:text-red border-b-2 border-transparent hover:border-red transition-colors"
                                >
                                    VIEW SOURCE <ExternalLink size={12} />
                                </a>
                            )}
                        </div>
                    );
                })}
            </div>

            {/* Footer */}
            <div className="font-mono text-xs font-bold text-ink border-t-2 border-border p-4 text-center bg-paper-raised">
                SOURCE: NEWSAPI.ORG — LIVE SEARCH
            </div>
        </div>
    );
}
