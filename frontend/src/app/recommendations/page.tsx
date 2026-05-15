import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { RefreshCw, X } from 'lucide-react'
import { recommendationsApi } from '../../services/api'
import type { Recommendation } from '../../types'
import { format } from 'date-fns'
import toast from 'react-hot-toast'

export default function RecommendationsPage() {
  const [recommendations, setRecommendations] = useState<Recommendation[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  useEffect(() => {
    loadRecommendations()
  }, [])

  const loadRecommendations = async () => {
    try {
      const data = await recommendationsApi.list({
        page: 1,
        page_size: 50,
        dismissed: false,
      })
      setRecommendations(data.recommendations)
    } catch (error) {
      console.error('Failed to load recommendations:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      await recommendationsApi.refresh()
      toast.success('Refresh started')
      setTimeout(() => loadRecommendations(), 5000)
    } catch (error) {
      toast.error('Failed to refresh')
    } finally {
      setRefreshing(false)
    }
  }

  const handleDismiss = async (rec: Recommendation) => {
    try {
      await recommendationsApi.dismiss(rec.id)
      setRecommendations((prev) => prev.filter((r) => r.id !== rec.id))
    } catch (error) {
      toast.error('Failed to dismiss')
    }
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Recommendations</h1>
          <p className="text-sm text-gray-500">Papers matched to your interests</p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gray-900 text-white text-sm font-medium rounded-md hover:bg-gray-800 disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Recommendations Table */}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        {loading ? (
          <div className="px-4 py-8 text-center text-sm text-gray-500">Loading...</div>
        ) : recommendations.length === 0 ? (
          <div className="px-4 py-8 text-center">
            <p className="text-sm text-gray-500">No recommendations</p>
            <p className="text-xs text-gray-400 mt-1">Configure interests and fetch papers first</p>
          </div>
        ) : (
          <table>
            <thead>
              <tr className="bg-gray-50">
                <th>Paper</th>
                <th className="w-16">Score</th>
                <th className="w-48">Reason</th>
                <th className="w-16">Actions</th>
              </tr>
            </thead>
            <tbody>
              {recommendations.map((rec) => (
                <tr key={rec.id}>
                  <td>
                    <Link
                      to={`/papers/${rec.paper.id}`}
                      className="text-sm font-medium text-gray-900 hover:text-gray-600"
                    >
                      {rec.paper.title}
                    </Link>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {rec.paper.authors.slice(0, 2).join(', ')}
                      {rec.paper.authors.length > 2 && ' et al.'}
                      {rec.paper.published_date && (
                        <span className="ml-2">
                          {format(new Date(rec.paper.published_date), 'MMM d')}
                        </span>
                      )}
                    </p>
                  </td>
                  <td>
                    <span className="text-xs font-medium text-gray-700">
                      {Math.round(rec.score * 100)}%
                    </span>
                  </td>
                  <td>
                    <p className="text-xs text-gray-600 line-clamp-2">{rec.reason}</p>
                  </td>
                  <td>
                    <button
                      onClick={() => handleDismiss(rec)}
                      className="p-1 hover:bg-gray-100 rounded"
                      title="Dismiss"
                    >
                      <X className="w-3.5 h-3.5 text-gray-400" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
