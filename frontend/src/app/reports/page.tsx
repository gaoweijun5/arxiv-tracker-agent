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
        <div className="text-sm text-gray-500">Loading...</div>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-xl font-semibold text-[#1A1A1A]">Research Reports</h1>
          <p className="text-sm text-gray-500">A report is generated after every manual or scheduled fetch.</p>
        </div>
        {selected.size > 0 && (
          <button
            onClick={handleBatchDelete}
            disabled={deleting}
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 disabled:opacity-50 transition-all duration-300"
          >
            <Trash2 className="w-3.5 h-3.5" />
            {deleting ? 'Deleting...' : `Delete ${selected.size} selected`}
          </button>
        )}
      </div>

      {reports.length === 0 ? (
        <div className="bg-white shadow-[0_4px_12px_rgba(0,0,0,0.08)] rounded-lg px-6 py-10 text-center">
          <FileText className="w-8 h-8 mx-auto text-gray-300" />
          <p className="text-sm text-gray-500 mt-3">No reports yet</p>
          <p className="text-xs text-gray-400 mt-1">Run a fetch to generate the first research report</p>
        </div>
      ) : (
        <div className="grid grid-cols-[280px_1fr] gap-6">
          <div className="bg-white shadow-[0_4px_12px_rgba(0,0,0,0.08)] rounded-lg overflow-hidden">
            <div className="px-4 py-3 flex items-center justify-between">
              <span className="text-xs font-medium text-gray-500 uppercase">History</span>
              <input
                type="checkbox"
                checked={reports.length > 0 && selected.size === reports.length}
                onChange={toggleSelectAll}
                className="rounded border-gray-300"
              />
            </div>
            <div className="max-h-[calc(100vh-180px)] overflow-auto">
              {reports.map((report) => (
                <div
                  key={report.id}
                  className={`px-4 py-3 transition-colors duration-300 ${selectedReport?.id === report.id ? 'bg-gray-50' : ''}`}
                >
                  <div className="flex items-start gap-2">
                    <input
                      type="checkbox"
                      checked={selected.has(report.id)}
                      onChange={() => toggleSelect(report.id)}
                      className="rounded border-gray-300 mt-1"
                    />
                    <Link
                      to={`/reports/${report.id}`}
                      className="flex-1 min-w-0"
                    >
                      <div className="flex items-center gap-2">
                        <span className={`text-[10px] px-2 py-0.5 rounded-lg ${
                          report.source === 'auto'
                            ? 'bg-blue-50 text-blue-600'
                            : 'bg-gray-100 text-gray-600'
                        }`}>
                          {report.source === 'auto' ? 'Auto' : 'Manual'}
                        </span>
                        <span className="text-xs text-gray-400">{formatDate(report.created_at)}</span>
                      </div>
                      <p className="text-sm font-medium text-[#1A1A1A] mt-1 line-clamp-2">{report.title}</p>
                      <p className="text-xs text-gray-500 mt-1 line-clamp-2">
                        {report.summary || report.status}
                      </p>
                    </Link>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDelete(report) }}
                      className="p-1 hover:bg-gray-100 rounded-lg text-gray-400 hover:text-gray-600 shrink-0 transition-colors duration-300"
                      title="Delete"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white shadow-[0_4px_12px_rgba(0,0,0,0.08)] rounded-lg overflow-hidden">
            {selectedReport ? (
              <>
                <div className="px-6 py-5">
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`text-[10px] px-2 py-0.5 rounded-lg ${
                      selectedReport.status === 'generated'
                        ? 'bg-green-50 text-green-600'
                        : selectedReport.status === 'empty'
                          ? 'bg-gray-100 text-gray-600'
                          : 'bg-red-50 text-red-600'
                    }`}>
                      {selectedReport.status}
                    </span>
                    <span className="text-xs text-gray-400">{formatDate(selectedReport.created_at)}</span>
                  </div>
                  <h2 className="text-lg font-semibold text-[#1A1A1A]">{selectedReport.title}</h2>
                  <div className="flex gap-4 mt-3 text-xs text-gray-500">
                    <span>Found {selectedReport.stats.papers_found || 0}</span>
                    <span>Relevant {selectedReport.stats.papers_relevant || 0}</span>
                    <span>Saved {selectedReport.stats.papers_saved || 0}</span>
                  </div>
                </div>

                <div className="px-6 pb-6">
                  <ReactMarkdown className="prose prose-sm max-w-none">
                    {selectedReport.content_md}
                  </ReactMarkdown>

                  {selectedReport.papers.length > 0 && (
                    <div className="mt-6 pt-4">
                      <h3 className="text-xs font-medium text-gray-500 uppercase mb-2">Papers in this report</h3>
                      <div className="space-y-2">
                        {selectedReport.papers.map((paper) => (
                          <Link
                            key={paper.id}
                            to={`/papers/${paper.id}`}
                            className="block text-sm text-[#1A1A1A] hover:text-[#3B82F6] transition-colors duration-300"
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
              <div className="px-6 py-10 text-center text-sm text-gray-500">
                Select a report
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
