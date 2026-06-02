import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { X } from 'lucide-react'
import { recommendationsApi } from '../../services/api'
import type { Recommendation } from '../../types'
import { format } from 'date-fns'
import toast from 'react-hot-toast'

export default function RecommendationsPage() {
  const [recommendations, setRecommendations] = useState<Recommendation[]>([])
  const [loading, setLoading] = useState(true)

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

  const handleDismiss = async (rec: Recommendation) => {
    try {
      await recommendationsApi.dismiss(rec.id)
      setRecommendations((prev) => prev.filter((r) => r.id !== rec.id))
    } catch (error) {
      toast.error('Failed to dismiss')
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between fade-in stagger-1">
        <div>
          <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Outfit, sans-serif' }}>
            Recommendations
          </h1>
          <p className="text-sm text-white/60 mt-1">Papers matched to your interests</p>
        </div>
      </div>

      {/* Recommendations Table */}
      <div className="glass-card overflow-hidden fade-in stagger-2">
        {loading ? (
          <div className="px-6 py-8 text-center text-sm text-white/60">Loading...</div>
        ) : recommendations.length === 0 ? (
          <div className="px-6 py-8 text-center">
            <p className="text-sm text-white/60">No recommendations</p>
            <p className="text-xs text-white/40 mt-1">Configure interests and fetch papers first</p>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Paper</th>
                <th className="w-16">Score</th>
                <th className="w-48">Reason</th>
                <th className="w-16">Actions</th>
              </tr>
            </thead>
            <tbody>
              {recommendations.map((rec, index) => (
                <tr
                  key={rec.id}
                  className="fade-in"
                  style={{ animationDelay: `${(index + 2) * 50}ms` }}
                >
                  <td>
                    <Link
                      to={`/papers/${rec.paper.id}`}
                      className="text-sm font-medium text-white hover:text-white/80 transition-colors duration-300"
                    >
                      {rec.paper.title}
                    </Link>
                    <p className="text-xs text-white/50 mt-0.5">
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
                    <span className="text-xs font-medium text-white/70">
                      {Math.round(rec.score * 100)}%
                    </span>
                  </td>
                  <td>
                    <p className="text-xs text-white/60 line-clamp-2">{rec.reason}</p>
                  </td>
                  <td>
                    <button
                      onClick={() => handleDismiss(rec)}
                      className="p-1 hover:bg-white/10 rounded-lg transition-colors duration-300"
                      title="Dismiss"
                    >
                      <X className="w-3.5 h-3.5 text-white/50" />
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
