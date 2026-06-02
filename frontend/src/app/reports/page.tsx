import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { FileText, Trash2 } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { format } from 'date-fns'
import { reportsApi } from '../../services/api'
import type { ResearchReport } from '../../types'
import toast from 'react-hot-toast'

export default function ReportsPage() {
  const { id } = useParams<{ id?: string }>()
  const [reports, setReports] = useState<ResearchReport[]>([])
  const [selectedReport, setSelectedReport] = useState<ResearchReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    loadReports()
    setSelected(new Set())
  }, [id])

  const loadReports = async () => {
    setLoading(true)
    try {
      const data = await reportsApi.list({ page: 1, page_size: 30 })
      setReports(data.reports)

      if (id) {
        setSelectedReport(await reportsApi.get(parseInt(id)))
      } else {
        setSelectedReport(data.reports[0] || null)
      }
    } catch (error) {
      console.error('Failed to load reports:', error)
    } finally {
      setLoading(false)
    }
  }

  const formatDate = (value: string | null) => {
    if (!value) return '-'
    return format(new Date(value), 'MMM d, HH:mm')
  }

  const toggleSelect = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleSelectAll = () => {
    if (selected.size === reports.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(reports.map((r) => r.id)))
    }
  }

  const handleDelete = async (report: ResearchReport) => {
    if (!confirm(`Delete "${report.title}"?`)) return
    try {
      await reportsApi.delete(report.id)
      setReports((prev) => prev.filter((r) => r.id !== report.id))
      if (selectedReport?.id === report.id) {
        setSelectedReport(reports.find((r) => r.id !== report.id) || null)
      }
      toast.success('Report deleted')
    } catch (error) {
      toast.error('Failed to delete report')
    }
  }

  const handleBatchDelete = async () => {
    if (selected.size === 0) return
    if (!confirm(`Delete ${selected.size} selected reports?`)) return

    setDeleting(true)
    try {
      const result = await reportsApi.batchDelete(Array.from(selected))
      setReports((prev) => prev.filter((r) => !selected.has(r.id)))
      if (selectedReport && selected.has(selectedReport.id)) {
        setSelectedReport(null)
      }
      setSelected(new Set())
      toast.success(`Deleted ${result.deleted} reports`)
    } catch (error) {
      toast.error('Failed to delete reports')
    } finally {
      setDeleting(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-sm text-white/60">Loading...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between fade-in stagger-1">
        <div>
          <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Outfit, sans-serif' }}>
            Research Reports
          </h1>
          <p className="text-sm text-white/60 mt-1">A report is generated after every manual or scheduled fetch.</p>
        </div>
        {selected.size > 0 && (
          <button
            onClick={handleBatchDelete}
            disabled={deleting}
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-red-500/80 text-white text-sm font-medium rounded-2xl hover:bg-red-500 disabled:opacity-50 transition-all duration-300 backdrop-blur-sm border border-red-400/30"
          >
            <Trash2 className="w-4 h-4" />
            {deleting ? 'Deleting...' : `Delete ${selected.size} selected`}
          </button>
        )}
      </div>

      {reports.length === 0 ? (
        <div className="glass-card px-6 py-10 text-center fade-in stagger-2">
          <FileText className="w-8 h-8 mx-auto text-white/30" />
          <p className="text-sm text-white/60 mt-3">No reports yet</p>
          <p className="text-xs text-white/40 mt-1">Run a fetch to generate the first research report</p>
        </div>
      ) : (
        <div className="grid grid-cols-[280px_1fr] gap-6">
          <div className="glass-card overflow-hidden fade-in stagger-2">
            <div className="px-4 py-3 flex items-center justify-between">
              <span className="text-xs font-medium text-white/60 uppercase">History</span>
              <input
                type="checkbox"
                checked={reports.length > 0 && selected.size === reports.length}
                onChange={toggleSelectAll}
                className="rounded"
              />
            </div>
            <div className="max-h-[calc(100vh-180px)] overflow-auto">
              {reports.map((report, index) => (
                <div
                  key={report.id}
                  className={`px-4 py-3 transition-colors duration-300 fade-in ${
                    selectedReport?.id === report.id ? 'bg-white/10' : 'hover:bg-white/5'
                  }`}
                  style={{ animationDelay: `${(index + 2) * 50}ms` }}
                >
                  <div className="flex items-start gap-2">
                    <input
                      type="checkbox"
                      checked={selected.has(report.id)}
                      onChange={() => toggleSelect(report.id)}
                      className="rounded mt-1"
                    />
                    <Link
                      to={`/reports/${report.id}`}
                      className="flex-1 min-w-0"
                    >
                      <div className="flex items-center gap-2">
                        <span className={`text-[10px] px-2 py-0.5 rounded-lg ${
                          report.source === 'auto'
                            ? 'bg-blue-500/30 text-blue-200'
                            : 'bg-white/10 text-white/60'
                        }`}>
                          {report.source === 'auto' ? 'Auto' : 'Manual'}
                        </span>
                        <span className="text-xs text-white/40">{formatDate(report.created_at)}</span>
                      </div>
                      <p className="text-sm font-medium text-white mt-1 line-clamp-2">{report.title}</p>
                      <p className="text-xs text-white/50 mt-1 line-clamp-2">
                        {report.summary || report.status}
                      </p>
                    </Link>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDelete(report) }}
                      className="p-1 hover:bg-white/10 rounded-lg text-white/40 hover:text-white/70 shrink-0 transition-colors duration-300"
                      title="Delete"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="glass-card overflow-hidden fade-in stagger-3">
            {selectedReport ? (
              <>
                <div className="px-6 py-5">
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`text-[10px] px-2 py-0.5 rounded-lg ${
                      selectedReport.status === 'generated'
                        ? 'bg-green-500/30 text-green-200'
                        : selectedReport.status === 'empty'
                          ? 'bg-white/10 text-white/60'
                          : 'bg-red-500/30 text-red-200'
                    }`}>
                      {selectedReport.status}
                    </span>
                    <span className="text-xs text-white/40">{formatDate(selectedReport.created_at)}</span>
                  </div>
                  <h2 className="text-lg font-bold text-white" style={{ fontFamily: 'Outfit, sans-serif' }}>
                    {selectedReport.title}
                  </h2>
                  <div className="flex gap-4 mt-3 text-xs text-white/50">
                    <span>Found {selectedReport.stats.papers_found || 0}</span>
                    <span>Relevant {selectedReport.stats.papers_relevant || 0}</span>
                    <span>Saved {selectedReport.stats.papers_saved || 0}</span>
                  </div>
                </div>

                <div className="px-6 pb-6">
                  <ReactMarkdown className="prose prose-sm max-w-none prose-invert">
                    {selectedReport.content_md}
                  </ReactMarkdown>

                  {selectedReport.papers.length > 0 && (
                    <div className="mt-6 pt-4">
                      <h3 className="text-xs font-medium text-white/60 uppercase mb-2">Papers in this report</h3>
                      <div className="space-y-2">
                        {selectedReport.papers.map((paper) => (
                          <Link
                            key={paper.id}
                            to={`/papers/${paper.id}`}
                            className="block text-sm text-white/80 hover:text-white transition-colors duration-300"
                          >
                            {paper.title}
                          </Link>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="px-6 py-10 text-center text-sm text-white/60">
                Select a report
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
