import { BarChart, AlertTriangle, CheckCircle, TrendingDown } from 'lucide-react'

export default function SectorBenchmarkPanel({ benchmarkData }) {
    if (!benchmarkData || !benchmarkData.findings || benchmarkData.findings.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center p-10 bg-paper border-[3px] border-ink">
                <BarChart size={48} className="text-muted mb-4" />
                <p className="text-sm font-serif text-muted">No sector benchmark data available for comparison.</p>
            </div>
        )
    }

    const { sector_used, summary, findings, triggered_rules } = benchmarkData

    return (
        <div className="flex flex-col gap-6">
            <div className="border-[3px] border-ink bg-paper p-6 relative">
                <div className="absolute -top-3 left-4 bg-paper px-2 font-display font-black text-ink uppercase tracking-wider text-sm flex items-center gap-2">
                    <div className="w-2 h-2 bg-ink" />
                    SECTOR BENCHMARK — {sector_used}
                </div>

                <div className="flex items-start gap-4 mb-6 mt-2">
                    <div className={`p-3 border-2 ${triggered_rules?.includes('P-30') ? 'border-red bg-red/10 text-red' : 'border-green bg-green/10 text-green'}`}>
                        {triggered_rules?.includes('P-30') ? <AlertTriangle size={24} /> : <CheckCircle size={24} />}
                    </div>
                    <div>
                        <h3 className="font-mono font-bold text-ink uppercase mb-1">
                            {triggered_rules?.includes('P-30') ? 'UNDERPERFORMING SECTOR' : 'SECTOR ALIGNED'}
                        </h3>
                        <p className="text-sm font-serif text-ink">{summary}</p>
                        {triggered_rules?.includes('P-30') && (
                            <div className="inline-block mt-2 px-2 py-0.5 bg-red text-white text-[10px] font-bold font-mono uppercase">
                                P-30 TRIGGERED: SECTOR UNDERPERFORMANCE
                            </div>
                        )}
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {findings.map((f, idx) => (
                        <div key={idx} className={`border-2 p-4 ${f.status === 'CRITICAL' ? 'border-red' : f.status === 'BELOW' ? 'border-[#D4A017]' : 'border-green'}`}>
                            <div className="flex justify-between items-center mb-4">
                                <span className="font-mono text-xs font-bold text-ink uppercase">{f.metric}</span>
                                <span className={`text-[10px] font-bold uppercase px-2 py-0.5 ${f.status === 'CRITICAL' ? 'bg-red text-white' : f.status === 'BELOW' ? 'bg-[#D4A017] text-white' : 'bg-green text-white'}`}>
                                    {f.status}
                                </span>
                            </div>

                            <div className="flex justify-between items-end">
                                <div>
                                    <div className="text-[10px] font-mono text-muted uppercase">Company</div>
                                    <div className={`text-xl font-mono font-bold ${f.status === 'CRITICAL' ? 'text-red' : f.status === 'BELOW' ? 'text-[#D4A017]' : 'text-green'}`}>
                                        {f.company_value}%
                                    </div>
                                </div>
                                <div className="text-right">
                                    <div className="text-[10px] font-mono text-muted uppercase">Benchmark</div>
                                    <div className="text-xl font-mono font-bold text-ink">
                                        {f.benchmark_value}%
                                    </div>
                                </div>
                            </div>

                            <div className="mt-4 pt-3 border-t border-border flex items-center justify-between">
                                <span className="text-[10px] font-mono text-muted uppercase">Deviation</span>
                                <span className={`flex items-center gap-1 text-[11px] font-mono font-bold ${f.deviation_pct < 0 ? 'text-red' : 'text-green'}`}>
                                    {f.deviation_pct < 0 && <TrendingDown size={12} />}
                                    {f.deviation_pct > 0 ? '+' : ''}{f.deviation_pct}%
                                </span>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    )
}
