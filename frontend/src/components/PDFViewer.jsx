/**
 * PDFViewer – Left-panel PDF upload and viewer
 * Drag-and-drop zone that previews the most recently uploaded PDF in an iframe.
 * Shows a row of cards for up to 4 uploaded PDFs, allowing year label edits.
 */
import { useState, useRef, useCallback } from 'react'
import { Upload, FileText, X } from 'lucide-react'

export default function PDFViewer({ onFilesChange, isAnalyzing, analyzedData }) {
    const [dragActive, setDragActive] = useState(false)
    const [files, setFiles] = useState([]) // Array of { id, file, url, yearLabel }
    const fileInputRef = useRef(null)

    const handleFiles = useCallback((incomingList) => {
        if (!incomingList || incomingList.length === 0) return

        const newFiles = Array.from(incomingList).filter(f => f.name.toLowerCase().endsWith('.pdf'))
        if (newFiles.length === 0) return

        setFiles(prev => {
            let updated = [...prev]
            for (const file of newFiles) {
                if (updated.length >= 4) break
                updated.push({
                    id: Math.random().toString(36).substr(2, 9),
                    file,
                    url: URL.createObjectURL(file),
                    yearLabel: `FY${24 - updated.length}`
                })
            }
            // Sort by year desc for display logic
            updated.sort((a, b) => b.yearLabel.localeCompare(a.yearLabel))
            onFilesChange(updated)
            return updated
        })
    }, [onFilesChange])

    const handleDrop = useCallback((e) => {
        e.preventDefault()
        setDragActive(false)
        handleFiles(e.dataTransfer.files)
    }, [handleFiles])

    const handleDragOver = (e) => { e.preventDefault(); setDragActive(true) }
    const handleDragLeave = () => setDragActive(false)

    const removeFile = (idToRemove) => {
        setFiles(prev => {
            const fileToRemove = prev.find(f => f.id === idToRemove)
            if (fileToRemove?.url) URL.revokeObjectURL(fileToRemove.url)
            const updated = prev.filter(f => f.id !== idToRemove)
            onFilesChange(updated)
            return updated
        })
    }

    const updateYearLabel = (idToUpdate, newLabel) => {
        setFiles(prev => {
            const updated = prev.map(f => f.id === idToUpdate ? { ...f, yearLabel: newLabel } : f)
            // Sort descending to keep ordering predictable
            updated.sort((a, b) => b.yearLabel.localeCompare(a.yearLabel))
            onFilesChange(updated)
            return updated
        })
    }

    const activePdf = files.length > 0 ? files[0] : null;

    return (
        <div className="flex flex-col h-full gap-4">
            {/* Header */}
            <div className="flex items-center justify-between pointer-events-none mb-2 border-b-[3px] border-border pb-2">
                <div>
                    <h2 className="font-display font-black text-ink uppercase tracking-wider text-lg flex items-center gap-2">
                        <FileText size={18} className="text-ink" />
                        Document Ingestion
                    </h2>
                    <p className="font-mono text-xs font-bold text-muted mt-1 uppercase">Upload annual reports (Max 4)</p>
                </div>
            </div>

            {/* Drop zone */}
            {files.length < 4 && (
                <div
                    className={`border-[3px] border-dashed flex flex-col items-center justify-center
                      cursor-pointer transition-none py-10
                      ${dragActive ? 'drop-zone-active border-red bg-red-light' : 'border-border hover:bg-paper-raised hover:border-ink'}`}
                    onDrop={handleDrop}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onClick={() => fileInputRef.current?.click()}
                >
                    <div className={`w-12 h-12 flex items-center justify-center mb-3 transition-none
                           ${dragActive ? 'bg-red text-white' : 'bg-ink text-paper'}`}>
                        <Upload size={24} />
                    </div>
                    <p className="font-display italic font-bold text-ink text-xl uppercase tracking-wide">
                        Drop Annual Report Here
                    </p>
                    <input
                        ref={fileInputRef}
                        type="file"
                        accept=".pdf"
                        multiple
                        className="hidden"
                        onChange={e => handleFiles(e.target.files)}
                    />
                </div>
            )}

            {/* Uploaded File Cards Row */}
            {files.length > 0 && (
                <div className="flex flex-col gap-2 relative mt-4">
                    {files.map(f => {
                        // Look up pdf_type if we have analyzedData
                        const yearData = analyzedData?.per_year_scans?.[f.yearLabel]
                        const pdfType = yearData?.pdf_type

                        return (
                            <div key={f.id} className="bg-paper p-3 flex items-center gap-4 w-full border-2 border-border group relative">
                                <div className="w-10 h-10 bg-ink flex items-center justify-center flex-shrink-0">
                                    <FileText size={18} className="text-paper" />
                                </div>
                                <div className="flex-1 min-w-0 pr-2">
                                    <div className="flex items-center gap-2">
                                        <p className="font-serif font-bold text-ink text-base truncate">{f.file.name}</p>
                                        {pdfType && (
                                            <span className={`text-[10px] font-mono font-bold uppercase tracking-wider px-1.5 py-0.5 border ${pdfType === 'text'
                                                ? 'border-green-600 text-green-700 bg-green-50'
                                                : 'border-[#D4A017] text-[#D4A017] bg-[#FFF8E7]'
                                                }`}>
                                                {pdfType === 'text' ? 'Text PDF' : 'Scanned — OCR'}
                                            </span>
                                        )}
                                    </div>
                                    <p className="font-mono text-xs text-muted tracking-wide font-bold mt-0.5">{(f.file.size / 1024 / 1024).toFixed(2)} MB</p>
                                </div>
                                <div className="flex items-center gap-3 flex-shrink-0">
                                    <input
                                        type="text"
                                        value={f.yearLabel}
                                        onChange={(e) => updateYearLabel(f.id, e.target.value)}
                                        className="bg-paper border-2 border-border text-sm font-mono font-bold text-center w-16 py-1.5 text-ink focus:outline-none focus:border-red transition-none"
                                        placeholder="FY24"
                                        maxLength={8}
                                    />
                                    <button
                                        onClick={() => removeFile(f.id)}
                                        className="text-ink hover:text-white hover:bg-red p-1.5 transition-none border-2 border-transparent hover:border-red"
                                        title="Remove file"
                                    >
                                        <X size={16} />
                                    </button>
                                </div>
                            </div>
                        )
                    })}
                </div>
            )}

        </div>
    )
}
