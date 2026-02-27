import React from 'react';
import { AlertCircle, CheckCircle, ExternalLink, Newspaper } from 'lucide-react';

export default function AdverseMediaPanel({ newsData }) {
    if (!newsData) return null;

    const { entity, articles_found, red_flags, adverse_media_detected } = newsData;

    if (!adverse_media_detected) {
        return (
            <div className="mt-6 border-2 border-border bg-paper p-6 relative overflow-hidden">
                <div className="absolute top-0 right-0 p-4 opacity-5 pointer-events-none">
                    <Newspaper size={120} />
                </div>
                <div className="flex items-start gap-4">
                    <div className="bg-[#167A3E]/10 p-2 border-2 border-[#167A3E]">
                        <CheckCircle className="text-[#167A3E]" size={24} />
                    </div>
                    <div>
                        <h2 className="text-xl font-display font-black uppercase tracking-tight text-ink mb-1">
                            Adverse Media Scan
                        </h2>
                        <p className="text-sm font-serif text-ink">
                            Scanned <strong>{articles_found}</strong> recent articles for <strong>{entity}</strong>.
                            No severe red flags (fraud, insolvency, regulatory action, etc.) were found in the headlines.
                        </p>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="mt-6 border-2 border-red bg-red/5 p-6 relative overflow-hidden">
            <div className="absolute top-0 right-0 p-4 opacity-10 pointer-events-none text-red">
                <Newspaper size={120} />
            </div>
            <div className="flex items-start gap-4 mb-6 relative z-10">
                <div className="bg-red flex items-center justify-center p-2">
                    <AlertCircle className="text-white" size={24} />
                </div>
                <div>
                    <h2 className="text-xl font-display font-black uppercase tracking-tight text-red mb-1">
                        Adverse Media Detected
                    </h2>
                    <p className="text-sm font-serif text-ink">
                        Scanned <strong>{articles_found}</strong> recent articles for <strong>{entity}</strong>.
                        Found <strong>{red_flags.length}</strong> red flags requiring immediate manual review.
                    </p>
                </div>
            </div>

            <div className="space-y-4 relative z-10">
                {red_flags.map((flag, idx) => (
                    <a
                        key={idx}
                        href={flag.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block border-2 border-red/30 bg-paper hover:bg-red/5 hover:border-red transition-colors p-4 group"
                    >
                        <div className="flex justify-between items-start gap-4">
                            <div>
                                <h3 className="text-base font-serif font-bold text-ink group-hover:text-red transition-colors mb-2 leading-tight">
                                    {flag.headline}
                                </h3>
                                <div className="flex items-center gap-3 text-xs font-mono text-muted uppercase">
                                    <span className="bg-red/10 text-red px-1.5 py-0.5 border border-red/20">
                                        {flag.severity} SEVERITY
                                    </span>
                                    <span>{flag.source}</span>
                                    <span>{flag.published}</span>
                                </div>
                            </div>
                            <ExternalLink size={16} className="text-muted group-hover:text-red transition-colors flex-shrink-0 mt-1" />
                        </div>
                    </a>
                ))}
            </div>
        </div>
    );
}
