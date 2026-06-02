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
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg w-full max-w-md mx-4 shadow-[0_8px_24px_rgba(0,0,0,0.12)] fade-in">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4">
          <h2 className="text-sm font-medium text-[#1A1A1A]">Fetch Papers</h2>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded-lg transition-colors duration-300" disabled={fetching}>
            <X className="w-4 h-4 text-gray-400" />
          </button>
        </div>

        {/* Content */}
        <div className="px-6 pb-6 space-y-4">
          {/* Interests */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-2">Topics</label>
            {loading ? (
              <div className="text-sm text-gray-500 py-2">Loading...</div>
            ) : interests.length === 0 ? (
              <div className="text-sm text-gray-500 py-2">No interests configured</div>
            ) : (
              <div className="space-y-1 max-h-40 overflow-y-auto">
                {interests.map((interest) => (
                  <label
                    key={interest.id}
                    className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-gray-50 cursor-pointer transition-colors duration-300"
                  >
                    <input
                      type="checkbox"
                      checked={selectedInterests.includes(interest.id)}
                      onChange={() => toggleInterest(interest.id)}
                      className="rounded border-gray-300"
                    />
                    <span className="text-sm text-gray-700">{interest.topic}</span>
                  </label>
                ))}
              </div>
            )}
          </div>

          {/* Days Back */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Search Period</label>
            <select
              value={daysBack}
              onChange={(e) => setDaysBack(parseInt(e.target.value))}
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-gray-400 transition-colors duration-300"
              disabled={fetching}
            >
              <option value={1}>Last 1 day</option>
              <option value={3}>Last 3 days</option>
              <option value={7}>Last 7 days</option>
              <option value={14}>Last 14 days</option>
              <option value={30}>Last 30 days</option>
            </select>
          </div>

          {/* Max Results */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Max Results</label>
            <select
              value={maxResults}
              onChange={(e) => setMaxResults(parseInt(e.target.value))}
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-gray-400 transition-colors duration-300"
              disabled={fetching}
            >
              <option value={10}>10 papers</option>
              <option value={20}>20 papers</option>
              <option value={30}>30 papers</option>
              <option value={50}>50 papers</option>
            </select>
          </div>

          {/* Progress */}
          {fetching && progress && (
            <div className="bg-gray-50 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-gray-600">{progress.message}</span>
                <span className="text-xs font-medium text-[#1A1A1A]">{progress.progress}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-1.5">
                <div
                  className="bg-[#3B82F6] h-1.5 rounded-full transition-all duration-300"
                  style={{ width: `${progress.progress}%` }}
                />
              </div>
            </div>
          )}

          {/* Result */}
          {result && (
            <div className={`rounded-lg p-4 text-sm ${
              result.status === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
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
                  className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-green-800 hover:text-green-950 transition-colors duration-300"
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
            className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-all duration-300"
          >
            {result ? 'Close' : 'Cancel'}
          </button>
          {!result && (
            <button
              onClick={handleFetch}
              disabled={fetching || selectedInterests.length === 0}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-[#1A1A1A] text-white text-sm font-medium rounded-lg hover:bg-[#3B82F6] disabled:opacity-40 transition-all duration-300"
            >
              {fetching ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Fetching...
                </>
              ) : (
                <>
                  <Search className="w-3.5 h-3.5" />
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
