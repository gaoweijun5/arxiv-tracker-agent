import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { X, Search, Loader2, FileText } from 'lucide-react'
import { systemApi } from '../services/api'
import toast from 'react-hot-toast'

interface Interest {
  id: number
  topic: string
  keywords: string[]
}

interface FetchProgress {
  step: string
  progress: number
  message: string
}

interface FetchModalProps {
  isOpen: boolean
  onClose: () => void
  onComplete: () => void
}

export default function FetchModal({ isOpen, onClose, onComplete }: FetchModalProps) {
  const [interests, setInterests] = useState<Interest[]>([])
  const [selectedInterests, setSelectedInterests] = useState<number[]>([])
  const [daysBack, setDaysBack] = useState(7)
  const [maxResults, setMaxResults] = useState(30)
  const [loading, setLoading] = useState(false)
  const [fetching, setFetching] = useState(false)
  const [progress, setProgress] = useState<FetchProgress | null>(null)
  const [result, setResult] = useState<any>(null)
  const [taskId, setTaskId] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (isOpen) {
      loadInterests()
      setProgress(null)
      setResult(null)
    }
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [isOpen])

  const loadInterests = async () => {
    setLoading(true)
    try {
      const data = await systemApi.getInterests()
      setInterests(data)
      setSelectedInterests([])
    } catch (error) {
      console.error('Failed to load interests:', error)
    } finally {
      setLoading(false)
    }
  }

  const connectWebSocket = (taskId: string) => {
    const ws = new WebSocket(`ws://localhost:8000/ws/progress/${taskId}`)

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === 'progress') {
        setProgress({ step: data.step, progress: data.progress, message: data.message })
      } else if (data.type === 'complete') {
        setResult(data.result)
        setFetching(false)
        if (data.result.status === 'failed') {
          toast.error('Fetch failed')
        } else {
          toast.success(`Found ${data.result.papers_found} papers`)
          onComplete()
        }
      } else if (data.type === 'error') {
        setResult({ status: 'failed', error: data.error })
        setFetching(false)
        toast.error('Fetch failed')
      }
    }

    wsRef.current = ws
  }

  const handleFetch = async () => {
    if (selectedInterests.length === 0) {
      toast.error('Select at least one interest')
      return
    }

    setFetching(true)
    setProgress({ step: 'start', progress: 0, message: 'Starting...' })

    try {
      const response = await systemApi.triggerFetchWithOptions({
        interest_ids: selectedInterests,
        days_back: daysBack,
        max_results: maxResults,
      })
      if (response.task_id) {
        setTaskId(response.task_id)
        connectWebSocket(response.task_id)
      }
    } catch (error) {
      toast.error('Failed to start fetch')
      setFetching(false)
    }
  }

  const handleCancel = async () => {
    if (taskId) {
      try {
        await systemApi.cancelFetch(taskId)
      } catch (error) {
        // Ignore errors - task may have already completed
      }
    }
    if (wsRef.current) {
      wsRef.current.close()
    }
    setFetching(false)
    setTaskId(null)
    onClose()
  }

  const toggleInterest = (id: number) => {
    setSelectedInterests((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    )
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="glass-card w-full max-w-md mx-4 fade-in" style={{ background: 'rgba(255, 255, 255, 0.15)' }}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4">
          <h2 className="text-sm font-semibold text-white/90" style={{ fontFamily: 'Outfit, sans-serif' }}>
            Fetch Papers
          </h2>
          <button onClick={onClose} className="p-1 hover:bg-white/10 rounded-lg transition-colors duration-300" disabled={fetching}>
            <X className="w-4 h-4 text-white/50" />
          </button>
        </div>

        {/* Content */}
        <div className="px-6 pb-6 space-y-4">
          {/* Interests */}
          <div>
            <label className="block text-xs font-medium text-white/70 mb-2">Topics</label>
            {loading ? (
              <div className="text-sm text-white/50 py-2">Loading...</div>
            ) : interests.length === 0 ? (
              <div className="text-sm text-white/50 py-2">No interests configured</div>
            ) : (
              <div className="space-y-1 max-h-40 overflow-y-auto">
                {interests.map((interest) => (
                  <label
                    key={interest.id}
                    className="flex items-center gap-2 px-3 py-2 rounded-xl hover:bg-white/10 cursor-pointer transition-colors duration-300"
                  >
                    <input
                      type="checkbox"
                      checked={selectedInterests.includes(interest.id)}
                      onChange={() => toggleInterest(interest.id)}
                      className="rounded"
                    />
                    <span className="text-sm text-white/80">{interest.topic}</span>
                  </label>
                ))}
              </div>
            )}
          </div>

          {/* Days Back */}
          <div>
            <label className="block text-xs font-medium text-white/70 mb-1">Search Period</label>
            <select
              value={daysBack}
              onChange={(e) => setDaysBack(parseInt(e.target.value))}
              className="w-full px-4 py-2.5 text-sm bg-white/10 border border-white/20 rounded-xl focus:outline-none focus:border-white/40 text-white transition-all duration-300"
              disabled={fetching}
            >
              <option value={1} className="bg-gray-800">Last 1 day</option>
              <option value={3} className="bg-gray-800">Last 3 days</option>
              <option value={7} className="bg-gray-800">Last 7 days</option>
              <option value={14} className="bg-gray-800">Last 14 days</option>
              <option value={30} className="bg-gray-800">Last 30 days</option>
            </select>
          </div>

          {/* Max Results */}
          <div>
            <label className="block text-xs font-medium text-white/70 mb-1">Max Results</label>
            <select
              value={maxResults}
              onChange={(e) => setMaxResults(parseInt(e.target.value))}
              className="w-full px-4 py-2.5 text-sm bg-white/10 border border-white/20 rounded-xl focus:outline-none focus:border-white/40 text-white transition-all duration-300"
              disabled={fetching}
            >
              <option value={10} className="bg-gray-800">10 papers</option>
              <option value={20} className="bg-gray-800">20 papers</option>
              <option value={30} className="bg-gray-800">30 papers</option>
              <option value={50} className="bg-gray-800">50 papers</option>
            </select>
          </div>

          {/* Progress */}
          {fetching && progress && (
            <div className="bg-white/10 rounded-xl p-4 backdrop-blur-sm">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-white/60">{progress.message}</span>
                <span className="text-xs font-medium text-white/80">{progress.progress}%</span>
              </div>
              <div className="w-full bg-white/10 rounded-full h-1.5">
                <div
                  className="bg-white/60 h-1.5 rounded-full transition-all duration-300"
                  style={{ width: `${progress.progress}%` }}
                />
              </div>
            </div>
          )}

          {/* Result */}
          {result && (
            <div className={`rounded-xl p-4 text-sm backdrop-blur-sm ${
              result.status === 'success' ? 'bg-green-500/30 text-green-200' : 'bg-red-500/30 text-red-200'
            }`}>
              <div>
                {result.status === 'success'
                  ? `Found ${result.papers_found} papers, ${result.papers_relevant} relevant, ${result.papers_saved || 0} saved`
                  : `Failed: ${result.error}`}
              </div>
              {result.report_id && (
                <Link
                  to={`/reports/${result.report_id}`}
                  onClick={onClose}
                  className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-green-200 hover:text-green-100 transition-colors duration-300"
                >
                  <FileText className="w-3.5 h-3.5" />
                  View research report
                </Link>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 px-6 py-4">
          <button
            onClick={result ? onClose : handleCancel}
            className="px-4 py-2.5 text-sm text-white/70 hover:bg-white/10 rounded-xl transition-all duration-300"
          >
            {result ? 'Close' : 'Cancel'}
          </button>
          {!result && (
            <button
              onClick={handleFetch}
              disabled={fetching || selectedInterests.length === 0}
              className="inline-flex items-center gap-2 px-4 py-2.5 bg-white/20 text-white text-sm font-medium rounded-xl hover:bg-white/30 disabled:opacity-40 backdrop-blur-sm border border-white/20 transition-all duration-300"
            >
              {fetching ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Fetching...
                </>
              ) : (
                <>
                  <Search className="w-4 h-4" />
                  Start Fetch
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
