import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { FileText } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { format } from 'date-fns'
import { reportsApi } from '../../services/api'
import type { ResearchReport } from '../../types'

export default function ReportsPage() {
  const { id } = useParams<{ id?: string }>()
  const [reports, setReports] = useState<ResearchReport[]>([])
  const [selectedReport, setSelectedReport] = useState<ResearchReport | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadReports()
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

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-sm text-gray-500">Loading...</div>
      </div>
    )
  }

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-xl font-semibold text-gray-900">Research Reports</h1>
        <p className="text-sm text-gray-500">A report is generated after every manual or scheduled fetch.</p>
      </div>

      {reports.length === 0 ? (
        <div className="bg-white border border-gray-200 rounded-lg px-4 py-10 text-center">
          <FileText className="w-8 h-8 mx-auto text-gray-300" />
          <p className="text-sm text-gray-500 mt-3">No reports yet</p>
          <p className="text-xs text-gray-400 mt-1">Run a fetch to generate the first research report</p>
        </div>
      ) : (
        <div className="grid grid-cols-[280px_1fr] gap-4">
          <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
            <div className="px-3 py-2 border-b border-gray-200 text-xs font-medium text-gray-500 uppercase">
              History
            </div>
            <div className="divide-y divide-gray-100 max-h-[calc(100vh-180px)] overflow-auto">
              {reports.map((report) => (
                <Link
                  key={report.id}
                  to={`/reports/${report.id}`}
                  className={`block px-3 py-3 hover:bg-gray-50 ${
                    selectedReport?.id === report.id ? 'bg-gray-50' : ''
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                      report.source === 'auto'
                        ? 'bg-blue-50 text-blue-600'
                        : 'bg-gray-100 text-gray-600'
                    }`}>
                      {report.source === 'auto' ? 'Auto' : 'Manual'}
                    </span>
                    <span className="text-xs text-gray-400">{formatDate(report.created_at)}</span>
                  </div>
                  <p className="text-sm font-medium text-gray-900 mt-1 line-clamp-2">{report.title}</p>
                  <p className="text-xs text-gray-500 mt-1 line-clamp-2">
                    {report.summary || report.status}
                  </p>
                </Link>
              ))}
            </div>
          </div>

          <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
            {selectedReport ? (
              <>
                <div className="px-5 py-4 border-b border-gray-200">
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded ${
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
                  <h2 className="text-lg font-semibold text-gray-900">{selectedReport.title}</h2>
                  <div className="flex gap-4 mt-3 text-xs text-gray-500">
                    <span>Found {selectedReport.stats.papers_found || 0}</span>
                    <span>Relevant {selectedReport.stats.papers_relevant || 0}</span>
                    <span>Saved {selectedReport.stats.papers_saved || 0}</span>
                  </div>
                </div>

                <div className="px-5 py-5">
                  <ReactMarkdown className="prose prose-sm max-w-none">
                    {selectedReport.content_md}
                  </ReactMarkdown>

                  {selectedReport.papers.length > 0 && (
                    <div className="mt-6 pt-4 border-t border-gray-200">
                      <h3 className="text-xs font-medium text-gray-500 uppercase mb-2">Papers in this report</h3>
                      <div className="space-y-2">
                        {selectedReport.papers.map((paper) => (
                          <Link
                            key={paper.id}
                            to={`/papers/${paper.id}`}
                            className="block text-sm text-gray-900 hover:text-gray-600"
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
              <div className="px-4 py-10 text-center text-sm text-gray-500">
                Select a report
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
