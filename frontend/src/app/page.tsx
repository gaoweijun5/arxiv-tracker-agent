import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search, ArrowRight, FileText } from 'lucide-react'
import { systemApi, recommendationsApi, reportsApi } from '../services/api'
import type { SystemStats, Recommendation, ResearchReport } from '../types'
import FetchModal from '../components/FetchModal'
import { format } from 'date-fns'

export default function HomePage() {
  const [stats, setStats] = useState<SystemStats | null>(null)
  const [todayRecs, setTodayRecs] = useState<Recommendation[]>([])
  const [latestReport, setLatestReport] = useState<ResearchReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [showFetchModal, setShowFetchModal] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [statsData, recsData, reportData] = await Promise.all([
        systemApi.getStats(),
        recommendationsApi.getToday(),
        reportsApi.latest(),
      ])
      setStats(statsData)
      setTodayRecs(recsData.recommendations)
      setLatestReport(reportData)
    } catch (error) {
      console.error('Failed to load dashboard data:', error)
    } finally {
      setLoading(false)
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
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-xl font-semibold text-[#1A1A1A]">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {stats?.last_fetch
              ? `Last fetch: ${format(new Date(stats.last_fetch), 'MMM d, HH:mm')}`
              : 'No fetches yet'}
          </p>
        </div>
        <button
          onClick={() => setShowFetchModal(true)}
          className="inline-flex items-center gap-1.5 px-4 py-2 bg-[#1A1A1A] text-white text-sm font-medium rounded-lg hover:bg-[#3B82F6] transition-all duration-300"
        >
          <Search className="w-3.5 h-3.5" />
          Fetch Papers
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-6 mb-8">
        <Link to="/papers" className="bg-white shadow-[0_4px_12px_rgba(0,0,0,0.08)] rounded-lg p-6 hover:shadow-[0_8px_24px_rgba(0,0,0,0.12)] transition-all duration-300">
          <p className="text-2xl font-semibold text-[#1A1A1A]">{stats?.total_papers || 0}</p>
          <p className="text-xs text-gray-500 mt-1">Total Papers</p>
        </Link>
        <Link to="/papers?unread=true" className="bg-white shadow-[0_4px_12px_rgba(0,0,0,0.08)] rounded-lg p-6 hover:shadow-[0_8px_24px_rgba(0,0,0,0.12)] transition-all duration-300">
          <p className="text-2xl font-semibold text-[#1A1A1A]">{stats?.unread_papers || 0}</p>
          <p className="text-xs text-gray-500 mt-1">Unread</p>
        </Link>
        <Link to="/recommendations" className="bg-white shadow-[0_4px_12px_rgba(0,0,0,0.08)] rounded-lg p-6 hover:shadow-[0_8px_24px_rgba(0,0,0,0.12)] transition-all duration-300">
          <p className="text-2xl font-semibold text-[#1A1A1A]">{todayRecs.length}</p>
          <p className="text-xs text-gray-500 mt-1">Today's Picks</p>
        </Link>
        <Link to="/interests" className="bg-white shadow-[0_4px_12px_rgba(0,0,0,0.08)] rounded-lg p-6 hover:shadow-[0_8px_24px_rgba(0,0,0,0.12)] transition-all duration-300">
          <p className="text-2xl font-semibold text-[#1A1A1A]">{stats?.total_interests || 0}</p>
          <p className="text-xs text-gray-500 mt-1">Interests</p>
        </Link>
      </div>

      {/* Latest Research Report */}
      <div className="bg-white shadow-[0_4px_12px_rgba(0,0,0,0.08)] rounded-lg mb-8">
        <div className="flex items-center justify-between px-6 py-4">
          <h2 className="text-sm font-medium text-[#1A1A1A]">Latest Research Report</h2>
          <Link
            to="/reports"
            className="text-xs text-gray-500 hover:text-[#3B82F6] flex items-center gap-1 transition-colors duration-300"
          >
            View all <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
        {latestReport ? (
          <Link to={`/reports/${latestReport.id}`} className="block px-6 py-4 hover:bg-gray-50 transition-colors duration-300">
            <div className="flex items-start gap-3">
              <FileText className="w-4 h-4 text-gray-400 mt-0.5" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-[#1A1A1A]">{latestReport.title}</p>
                <p className="text-xs text-gray-500 mt-1 line-clamp-2">
                  {latestReport.summary || latestReport.status}
                </p>
                <div className="flex gap-3 text-xs text-gray-400 mt-2">
                  <span>{latestReport.source === 'auto' ? 'Auto' : 'Manual'}</span>
                  <span>Found {latestReport.stats.papers_found || 0}</span>
                  <span>Saved {latestReport.stats.papers_saved || 0}</span>
                </div>
              </div>
            </div>
          </Link>
        ) : (
          <div className="px-6 py-8 text-center">
            <p className="text-sm text-gray-500">No reports yet</p>
            <p className="text-xs text-gray-400 mt-1">Fetch papers to generate a research report</p>
          </div>
        )}
      </div>

      {/* Today's Recommendations */}
      <div className="bg-white shadow-[0_4px_12px_rgba(0,0,0,0.08)] rounded-lg">
        <div className="flex items-center justify-between px-6 py-4">
          <h2 className="text-sm font-medium text-[#1A1A1A]">Today's Recommendations</h2>
          <Link
            to="/recommendations"
            className="text-xs text-gray-500 hover:text-[#3B82F6] flex items-center gap-1 transition-colors duration-300"
          >
            View all <ArrowRight className="w-3 h-3" />
          </Link>
        </div>

        {todayRecs.length === 0 ? (
          <div className="px-6 py-8 text-center">
            <p className="text-sm text-gray-500">No recommendations yet</p>
            <p className="text-xs text-gray-400 mt-1">Fetch papers to get started</p>
          </div>
        ) : (
          <div>
            {todayRecs.slice(0, 8).map((rec) => (
              <Link
                key={rec.id}
                to={`/papers/${rec.paper.id}`}
                className="flex items-start gap-3 px-6 py-4 hover:bg-gray-50 transition-colors duration-300"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-[#1A1A1A] truncate">
                    {rec.paper.title}
                  </p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {rec.paper.authors.slice(0, 2).join(', ')}
                    {rec.paper.authors.length > 2 && ' et al.'}
                  </p>
                  {rec.reason && (
                    <p className="text-xs text-gray-600 mt-1 line-clamp-1">{rec.reason}</p>
                  )}
                </div>
                <span className="text-xs font-medium text-gray-500 flex-shrink-0">
                  {Math.round(rec.score * 100)}%
                </span>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Fetch Modal */}
      <FetchModal
        isOpen={showFetchModal}
        onClose={() => setShowFetchModal(false)}
        onComplete={() => {
          loadData()
        }}
      />
    </div>
  )
}
