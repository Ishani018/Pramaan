import { AlertTriangle, Link2, ShieldCheck } from 'lucide-react'

function bandClasses(band) {
    if (band === 'High') return 'text-red border-red'
    if (band === 'Moderate') return 'text-[#B45A09] border-[#B45A09]'
    return 'text-green border-green'
}

export default function SupplyChainRiskPanel({ data }) {
    if (!data || Object.keys(data).length === 0) {
        return (
            <div className="border-[3px] border-ink bg-paper p-6">
                <div className="flex items-center gap-2 font-display font-bold uppercase tracking-wide text-ink text-sm mb-2">
                    <Link2 size={16} />
                    Supply Chain Risk
                </div>
                <p className="text-sm font-mono text-muted">No supply-chain disclosure extracted from the report text.</p>
            </div>
        )
    }

    const overallBand = data.overall_supply_chain_risk_band || 'Low'
    const overallScore = data.overall_supply_chain_risk_score ?? 0

    return (
        <div className="border-[3px] border-ink bg-paper p-6 relative">
            <div className="absolute -top-3 left-4 bg-paper px-2 font-display font-black text-ink uppercase tracking-wider text-sm flex items-center gap-2">
                <div className="w-2 h-2 bg-ink" />
                Supply Chain Risk
            </div>

            <div className="mt-2 grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="border-2 border-border p-3">
                    <div className="text-xs font-mono font-bold text-muted uppercase">Overall Risk</div>
                    <div className="mt-1 flex items-center gap-2">
                        <span className={`px-2 py-0.5 border-2 font-mono font-bold text-xs uppercase ${bandClasses(overallBand)}`}>
                            {overallBand}
                        </span>
                        <span className="font-mono font-bold text-ink">Score: {overallScore}</span>
                    </div>
                </div>

                <div className="border-2 border-border p-3">
                    <div className="text-xs font-mono font-bold text-muted uppercase">Supplier Side</div>
                    <div className="mt-1 font-mono text-sm text-ink">
                        {data.supplier_risk_band} ({data.supplier_risk_score})
                    </div>
                </div>

                <div className="border-2 border-border p-3">
                    <div className="text-xs font-mono font-bold text-muted uppercase">Buyer Side</div>
                    <div className="mt-1 font-mono text-sm text-ink">
                        {data.buyer_risk_band} ({data.buyer_risk_score})
                    </div>
                </div>
            </div>

            <div className="mt-4 border-2 border-border p-4 bg-[#F8F9FA]">
                <div className="flex items-start gap-2">
                    <AlertTriangle size={16} className="text-red mt-0.5" />
                    <div>
                        <div className="font-display font-bold text-ink uppercase tracking-wide text-xs">Weakest Link</div>
                        <div className="font-serif text-sm text-ink mt-1">{data.weakest_link}</div>
                    </div>
                </div>
                <p className="mt-3 text-sm font-serif text-ink leading-relaxed">{data.dashboard_summary}</p>
            </div>

            {(data.reasons || []).length > 0 && (
                <div className="mt-4">
                    <div className="font-display font-bold text-ink uppercase tracking-wide text-xs mb-2 flex items-center gap-2">
                        <ShieldCheck size={14} />
                        Key Reasons
                    </div>
                    <div className="space-y-2">
                        {data.reasons.slice(0, 5).map((reason, idx) => (
                            <div key={idx} className="border-l-2 border-border pl-3 text-sm font-serif text-ink">
                                {reason}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {data.cam_paragraph && (
                <div className="mt-4 border-t border-border pt-3">
                    <div className="text-xs font-mono font-bold text-muted uppercase mb-1">CAM Narrative</div>
                    <p className="text-sm font-serif text-ink leading-relaxed">{data.cam_paragraph}</p>
                </div>
            )}
        </div>
    )
}
