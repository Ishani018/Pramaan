import { Landmark, AlertCircle, TrendingUp, RefreshCw, AlertTriangle } from 'lucide-react'

export default function BankStatementPanel({ bankData }) {
    if (!bankData) {
        return (
            <div className="flex flex-col items-center justify-center p-10 bg-paper border-[3px] border-ink">
                <Landmark size={48} className="text-muted mb-4" />
                <p className="text-sm font-serif text-muted">No bank statement available for analysis.</p>
            </div>
        )
    }

    const {
        total_transactions,
        total_debits,
        total_credits,
        avg_monthly_balance,
        circular_transactions = [],
        cash_spikes = [],
        top_counterparties = [],
        triggered_rules = [],
    } = bankData

    return (
        <div className="flex flex-col gap-6">
            {/* ── HIGH LEVEL METRICS ────────────────────────────────────────── */}
            <div className="border-[3px] border-ink bg-paper p-6 relative">
                <div className="absolute -top-3 left-4 bg-paper px-2 font-display font-black text-ink uppercase tracking-wider text-sm flex items-center gap-2">
                    <div className="w-2 h-2 bg-ink" />
                    BANK STATEMENT — OVERVIEW
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-2">
                    <div className="border-2 border-border p-3">
                        <div className="text-[10px] font-mono font-bold text-muted uppercase mb-1">Total Txns</div>
                        <div className="text-xl font-mono font-bold text-ink">{total_transactions.toLocaleString()}</div>
                    </div>
                    <div className="border-2 border-border p-3">
                        <div className="text-[10px] font-mono font-bold text-muted uppercase mb-1">Avg Balance</div>
                        <div className="text-xl font-mono font-bold text-ink">₹{avg_monthly_balance.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</div>
                    </div>
                    <div className="border-2 border-border p-3">
                        <div className="text-[10px] font-mono font-bold text-muted uppercase mb-1">Total Credits</div>
                        <div className="text-xl font-mono font-bold text-green">₹{total_credits.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</div>
                    </div>
                    <div className="border-2 border-border p-3">
                        <div className="text-[10px] font-mono font-bold text-muted uppercase mb-1">Total Debits</div>
                        <div className="text-xl font-mono font-bold text-red">₹{total_debits.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</div>
                    </div>
                </div>
            </div>

            {/* ── FRAUD SIGNALS ─────────────────────────────────────────────── */}
            <div className="border-[3px] border-ink bg-paper p-6 relative">
                <div className="absolute -top-3 left-4 bg-paper px-2 font-display font-black text-ink uppercase tracking-wider text-sm flex items-center gap-2">
                    <div className="w-2 h-2 bg-ink" />
                    PATTERN RECOGNITION
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-2">
                    {/* Circular Trading */}
                    <div className={`border-2 p-4 ${circular_transactions.length > 0 ? 'border-red bg-red/5' : 'border-border'}`}>
                        <div className="flex items-center gap-2 mb-3">
                            <RefreshCw size={16} className={circular_transactions.length > 0 ? 'text-red' : 'text-muted'} />
                            <h4 className={`text-xs font-mono font-bold uppercase ${circular_transactions.length > 0 ? 'text-red' : 'text-ink'}`}>
                                Circular Transactions (7-day gap)
                            </h4>
                        </div>
                        {circular_transactions.length === 0 ? (
                            <p className="text-xs text-muted font-serif italic">No circular round-trips detected.</p>
                        ) : (
                            <div className="space-y-3">
                                {triggered_rules.includes("P-28") && (
                                    <div className="inline-block px-2 py-0.5 bg-red text-white text-[10px] font-bold font-mono uppercase mb-1">
                                        P-28 TRIGGERED
                                    </div>
                                )}
                                {circular_transactions.map((ct, idx) => (
                                    <div key={idx} className="bg-paper border border-red/30 p-2 text-xs font-mono">
                                        <div className="font-bold text-red mb-1 truncate" title={ct.party}>{ct.party}</div>
                                        <div className="flex justify-between text-[10px] text-ink">
                                            <span>OUT: ₹{ct.debit_amount.toLocaleString('en-IN')} on {ct.debit_date}</span>
                                        </div>
                                        <div className="flex justify-between text-[10px] text-ink mt-0.5">
                                            <span>IN: ₹{ct.credit_amount.toLocaleString('en-IN')} on {ct.credit_date}</span>
                                        </div>
                                        <div className="text-[10px] text-red mt-1 text-right">
                                            GAP: {ct.days_gap} day(s)
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* Cash Spikes */}
                    <div className={`border-2 p-4 ${cash_spikes.length > 0 ? 'border-[#D4A017] bg-[#D4A017]/5' : 'border-border'}`}>
                        <div className="flex items-center gap-2 mb-3">
                            <TrendingUp size={16} className={cash_spikes.length > 0 ? 'text-[#D4A017]' : 'text-muted'} />
                            <h4 className={`text-xs font-mono font-bold uppercase ${cash_spikes.length > 0 ? 'text-[#D4A017]' : 'text-ink'}`}>
                                Cash Spikes near GST Filing
                            </h4>
                        </div>
                        {cash_spikes.length === 0 ? (
                            <p className="text-xs text-muted font-serif italic">No significant cash spikes near filing dates.</p>
                        ) : (
                            <div className="space-y-3">
                                {triggered_rules.includes("P-29") && (
                                    <div className="inline-block px-2 py-0.5 bg-[#D4A017] text-white text-[10px] font-bold font-mono uppercase mb-1">
                                        P-29 TRIGGERED
                                    </div>
                                )}
                                {cash_spikes.map((cs, idx) => (
                                    <div key={idx} className="bg-paper border border-[#D4A017]/30 p-2 text-xs font-mono">
                                        <div className="font-bold text-[#D4A017] mb-1">
                                            +₹{cs.amount.toLocaleString('en-IN')} (Cash)
                                        </div>
                                        <div className="flex justify-between text-[10px] text-ink">
                                            <span>Date: {cs.date}</span>
                                        </div>
                                        <div className="text-[10px] text-[#D4A017] mt-1 text-right">
                                            {cs.days_before_filing} day(s) before {cs.nearest_filing_date}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* ── TOP COUNTERPARTIES ────────────────────────────────────────── */}
            {top_counterparties.length > 0 && (
                <div className="border-[3px] border-ink bg-paper p-6 relative flex-shrink-0">
                    <div className="absolute -top-3 left-4 bg-paper px-2 font-display font-black text-ink uppercase tracking-wider text-sm flex items-center gap-2">
                        <div className="w-2 h-2 bg-ink" />
                        TOP COUNTERPARTIES (BY VOLUME)
                    </div>
                    <div className="mt-2 text-xs font-mono">
                        {top_counterparties.map((tc, i) => (
                            <div key={i} className="flex justify-between py-2 border-b border-border/50 last:border-0">
                                <span className="font-bold text-ink truncate max-w-[70%]">{tc.party}</span>
                                <span className="text-muted">₹{tc.total_volume.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    )
}
