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
        <div className="text-sm text-white/60">Loading...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between fade-in stagger-1">
        <div>
          <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Outfit, sans-serif' }}>
            Dashboard
          </h1>
          <p className="text-sm text-white/60 mt-1">
            {stats?.last_fetch
              ? `Last fetch: ${format(new Date(stats.last_fetch), 'MMM d, HH:mm')}`
              : 'No fetches yet'}
          </p>
        </div>
        <button
          onClick={() => setShowFetchModal(true)}
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-white/20 text-white text-sm font-medium rounded-2xl hover:bg-white/30 backdrop-blur-sm border border-white/20 transition-all duration-300 hover:scale-105"
        >
          <Search className="w-4 h-4" />
          Fetch Papers
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-5">
        <Link
          to="/papers"
          className="glass-card glass-hover glass-glow p-6 fade-in stagger-2"
        >
          <p className="text-3xl font-bold text-white" style={{ fontFamily: 'Outfit, sans-serif' }}>
            {stats?.total_papers || 0}
          </p>
          <p className="text-sm text-white/60 mt-2">Total Papers</p>
        </Link>
        <Link
          to="/papers?unread=true"
          className="glass-card glass-hover glass-glow p-6 fade-in stagger-3"
        >
          <p className="text-3xl font-bold text-white" style={{ fontFamily: 'Outfit, sans-serif' }}>
            {stats?.unread_papers || 0}
          </p>
          <p className="text-sm text-white/60 mt-2">Unread</p>
        </Link>
        <Link
          to="/recommendations"
          className="glass-card glass-hover glass-glow p-6 fade-in stagger-4"
        >
          <p className="text-3xl font-bold text-white" style={{ fontFamily: 'Outfit, sans-serif' }}>
            {todayRecs.length}
          </p>
          <p className="text-sm text-white/60 mt-2">Today's Picks</p>
        </Link>
        <Link
          to="/interests"
          className="glass-card glass-hover glass-glow p-6 fade-in stagger-5"
        >
          <p className="text-3xl font-bold text-white" style={{ fontFamily: 'Outfit, sans-serif' }}>
            {stats?.total_interests || 0}
          </p>
          <p className="text-sm text-white/60 mt-2">Interests</p>
        </Link>
      </div>

      {/* Latest Research Report */}
      <div className="glass-card fade-in stagger-4">
        <div className="flex items-center justify-between px-6 py-4">
          <h2 className="text-sm font-semibold text-white/90" style={{ fontFamily: 'Outfit, sans-serif' }}>
            Latest Research Report
          </h2>
          <Link
            to="/reports"
            className="text-xs text-white/60 hover:text-white flex items-center gap-1 transition-colors duration-300"
          >
            View all <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
        {latestReport ? (
          <Link
            to={`/reports/${latestReport.id}`}
            className="block px-6 py-4 hover:bg-white/5 transition-colors duration-300 rounded-b-[20px]"
          >
            <div className="flex items-start gap-3">
              <FileText className="w-4 h-4 text-white/50 mt-0.5" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-white">{latestReport.title}</p>
                <p className="text-xs text-white/60 mt-1 line-clamp-2">
                  {latestReport.summary || latestReport.status}
                </p>
                <div className="flex gap-3 text-xs text-white/40 mt-2">
                  <span>{latestReport.source === 'auto' ? 'Auto' : 'Manual'}</span>
                  <span>Found {latestReport.stats.papers_found || 0}</span>
                  <span>Saved {latestReport.stats.papers_saved || 0}</span>
                </div>
              </div>
            </div>
          </Link>
        ) : (
          <div className="px-6 py-8 text-center">
            <p className="text-sm text-white/60">No reports yet</p>
            <p className="text-xs text-white/40 mt-1">Fetch papers to generate a research report</p>
          </div>
        )}
      </div>

      {/* Today's Recommendations */}
      <div className="glass-card fade-in stagger-5">
        <div className="flex items-center justify-between px-6 py-4">
          <h2 className="text-sm font-semibold text-white/90" style={{ fontFamily: 'Outfit, sans-serif' }}>
            Today's Recommendations
          </h2>
          <Link
            to="/recommendations"
            className="text-xs text-white/60 hover:text-white flex items-center gap-1 transition-colors duration-300"
          >
            View all <ArrowRight className="w-3 h-3" />
          </Link>
        </div>

        {todayRecs.length === 0 ? (
          <div className="px-6 py-8 text-center">
            <p className="text-sm text-white/60">No recommendations yet</p>
            <p className="text-xs text-white/40 mt-1">Fetch papers to get started</p>
          </div>
        ) : (
          <div>
            {todayRecs.slice(0, 8).map((rec, index) => (
              <Link
                key={rec.id}
                to={`/papers/${rec.paper.id}`}
                className="flex items-start gap-3 px-6 py-4 hover:bg-white/5 transition-colors duration-300"
                style={{ animationDelay: `${(index + 5) * 100}ms` }}
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-white truncate">
                    {rec.paper.title}
                  </p>
                  <p className="text-xs text-white/60 mt-0.5">
                    {rec.paper.authors.slice(0, 2).join(', ')}
                    {rec.paper.authors.length > 2 && ' et al.'}
                  </p>
                  {rec.reason && (
                    <p className="text-xs text-white/50 mt-1 line-clamp-1">{rec.reason}</p>
                  )}
                </div>
                <span className="text-xs font-medium text-white/60 flex-shrink-0">
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
