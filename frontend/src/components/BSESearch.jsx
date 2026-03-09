/**
 * BSESearch – Annual Report Surfer
 * ==================================
 * Search BSE-listed companies by name, browse their annual reports,
 * and fetch PDFs directly into the upload queue.
 */
import { useState, useRef, useCallback } from 'react'
import { Search, Building2, FileText, Download, X, Loader, ChevronDown, ArrowLeft } from 'lucide-react'
import axios from 'axios'

export default function BSESearch({ onPdfFetched }) {
    const [query, setQuery] = useState('')
    const [suggestions, setSuggestions] = useState([])
    const [selectedCompany, setSelectedCompany] = useState(null)
    const [reports, setReports] = useState([])
    const [searching, setSearching] = useState(false)
    const [loadingReports, setLoadingReports] = useState(false)
    const [downloading, setDownloading] = useState(null)
    const [expanded, setExpanded] = useState(false)
    const debounceRef = useRef(null)

    const handleSearch = useCallback((value) => {
        setQuery(value)
        setSuggestions([])

        if (debounceRef.current) clearTimeout(debounceRef.current)

        if (value.length < 2) return

        debounceRef.current = setTimeout(async () => {
            setSearching(true)
            try {
                const resp = await axios.get('/api/v1/bse/search', {
                    params: { q: value },
                    timeout: 10000,
                })
                setSuggestions(resp.data.results || [])
            } catch {
                setSuggestions([])
            } finally {
                setSearching(false)
            }
        }, 300)
    }, [])

    const handleSelectCompany = async (company) => {
        setSelectedCompany(company)
        setSuggestions([])
        setQuery('')
        setLoadingReports(true)
        try {
            const resp = await axios.get('/api/v1/bse/annual-reports', {
                params: { scrip_code: company.scrip_code },
                timeout: 15000,
            })
            setReports(resp.data.reports || [])
        } catch {
            setReports([])
        } finally {
            setLoadingReports(false)
        }
    }

    const handleFetchPdf = async (report) => {
        setDownloading(report.pdf_url)
        try {
            const resp = await axios.get('/api/v1/bse/download-pdf', {
                params: { url: report.pdf_url },
                responseType: 'blob',
                timeout: 60000,
            })

            const filename = `${selectedCompany.company_name}_AR_${report.year || 'latest'}.pdf`
            const file = new File([resp.data], filename, { type: 'application/pdf' })

            if (onPdfFetched) {
                onPdfFetched(file, report.year ? `FY${report.year.slice(-2)}` : 'FY24')
            }
        } catch (err) {
            console.error('BSE PDF download failed:', err)
        } finally {
            setDownloading(null)
        }
    }

    const handleBack = () => {
        setSelectedCompany(null)
        setReports([])
    }

    return (
        <div className="border-[3px] border-ink bg-paper relative">
            {/* Header */}
            <button
                onClick={() => setExpanded(e => !e)}
                className="w-full flex items-center justify-between p-4 cursor-pointer hover:bg-paper-raised"
            >
                <div className="flex items-center gap-2 font-display font-black text-ink uppercase tracking-wider text-sm">
                    <Building2 size={14} className="text-ink" />
                    BSE ANNUAL REPORT SURFER
                </div>
                <ChevronDown size={16} className={`text-ink transition-transform ${expanded ? 'rotate-180' : ''}`} />
            </button>

            {expanded && (
                <div className="border-t-2 border-border p-4">
                    {!selectedCompany ? (
                        /* ── SEARCH STATE ────────────────────────── */
                        <div className="flex flex-col gap-3">
                            <div className="relative">
                                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
                                <input
                                    type="text"
                                    value={query}
                                    onChange={(e) => handleSearch(e.target.value)}
                                    placeholder="Search BSE company (e.g. Reliance, Tata Steel)..."
                                    className="w-full pl-9 pr-3 py-2.5 border-2 border-ink font-mono text-sm bg-paper text-ink placeholder:text-muted focus:outline-none focus:border-red"
                                />
                                {searching && (
                                    <Loader size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted animate-spin" />
                                )}
                            </div>

                            {/* Suggestion dropdown */}
                            {suggestions.length > 0 && (
                                <div className="border-2 border-border divide-y divide-border max-h-60 overflow-y-auto">
                                    {suggestions.map((c) => (
                                        <button
                                            key={c.scrip_code}
                                            onClick={() => handleSelectCompany(c)}
                                            className="w-full text-left p-3 hover:bg-ink hover:text-paper transition-none flex items-center justify-between gap-2"
                                        >
                                            <div className="min-w-0">
                                                <div className="font-mono text-sm font-bold truncate">
                                                    {c.company_name}
                                                </div>
                                                <div className="text-[10px] font-mono text-muted uppercase">
                                                    {c.scrip_code} {c.group && `• ${c.group}`} {c.industry && `• ${c.industry}`}
                                                </div>
                                            </div>
                                            <FileText size={14} className="flex-shrink-0 text-muted" />
                                        </button>
                                    ))}
                                </div>
                            )}

                            {query.length >= 2 && !searching && suggestions.length === 0 && (
                                <p className="text-xs font-mono text-muted text-center py-2">
                                    No companies found. Try a different search term.
                                </p>
                            )}

                            <p className="text-[10px] font-mono text-muted uppercase tracking-widest">
                                Source: BSE India [LIVE]
                            </p>
                        </div>
                    ) : (
                        /* ── REPORTS STATE ───────────────────────── */
                        <div className="flex flex-col gap-3">
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={handleBack}
                                    className="p-1.5 border-2 border-border hover:bg-ink hover:text-paper transition-none"
                                >
                                    <ArrowLeft size={12} />
                                </button>
                                <div className="min-w-0 flex-1">
                                    <div className="font-mono text-sm font-bold text-ink truncate">
                                        {selectedCompany.company_name}
                                    </div>
                                    <div className="text-[10px] font-mono text-muted uppercase">
                                        BSE: {selectedCompany.scrip_code}
                                    </div>
                                </div>
                            </div>

                            {loadingReports ? (
                                <div className="flex items-center justify-center py-6 gap-2">
                                    <Loader size={14} className="text-muted animate-spin" />
                                    <span className="text-xs font-mono text-muted">Fetching annual reports...</span>
                                </div>
                            ) : reports.length === 0 ? (
                                <p className="text-xs font-mono text-muted text-center py-4">
                                    No annual reports found on BSE for this company.
                                </p>
                            ) : (
                                <div className="border-2 border-border divide-y divide-border max-h-60 overflow-y-auto">
                                    {reports.map((r, i) => (
                                        <div
                                            key={i}
                                            className="flex items-center justify-between p-3 gap-3"
                                        >
                                            <div className="min-w-0 flex-1">
                                                <div className="font-mono text-xs font-bold text-ink truncate">
                                                    {r.title}
                                                </div>
                                                <div className="text-[10px] font-mono text-muted">
                                                    {r.date} {r.year && `• ${r.year}`}
                                                </div>
                                            </div>
                                            <button
                                                onClick={() => handleFetchPdf(r)}
                                                disabled={downloading === r.pdf_url}
                                                className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 border-2 border-ink font-mono text-[10px] font-bold uppercase hover:bg-ink hover:text-paper disabled:opacity-40 transition-none"
                                            >
                                                {downloading === r.pdf_url ? (
                                                    <Loader size={10} className="animate-spin" />
                                                ) : (
                                                    <Download size={10} />
                                                )}
                                                {downloading === r.pdf_url ? 'Fetching...' : 'Fetch'}
                                            </button>
                                        </div>
                                    ))}
                                </div>
                            )}

                            <p className="text-[10px] font-mono text-muted uppercase tracking-widest">
                                Source: BSE India [LIVE] • Click FETCH to add to upload queue
                            </p>
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}
