import { useState, useEffect, useRef } from 'react'
import { X, Search, Loader2 } from 'lucide-react'
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
      <div className="bg-white rounded-lg w-full max-w-md mx-4 border border-gray-200">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
          <h2 className="text-sm font-medium text-gray-900">Fetch Papers</h2>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded" disabled={fetching}>
            <X className="w-4 h-4 text-gray-400" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4">
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
                    className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-gray-50 cursor-pointer"
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
              className="w-full px-2 py-1.5 text-sm border border-gray-200 rounded focus:outline-none focus:border-gray-400"
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
              className="w-full px-2 py-1.5 text-sm border border-gray-200 rounded focus:outline-none focus:border-gray-400"
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
            <div className="bg-gray-50 rounded p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-gray-600">{progress.message}</span>
                <span className="text-xs font-medium text-gray-900">{progress.progress}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-1.5">
                <div
                  className="bg-gray-900 h-1.5 rounded-full transition-all duration-300"
                  style={{ width: `${progress.progress}%` }}
                />
              </div>
            </div>
          )}

          {/* Result */}
          {result && (
            <div className={`rounded p-3 text-sm ${
              result.status === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
            }`}>
              {result.status === 'success'
                ? `Found ${result.papers_found} papers, ${result.papers_relevant} relevant`
                : `Failed: ${result.error}`}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 px-4 py-3 border-t border-gray-200">
          <button
            onClick={result ? onClose : handleCancel}
            className="px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded"
          >
            {result ? 'Close' : 'Cancel'}
          </button>
          {!result && (
            <button
              onClick={handleFetch}
              disabled={fetching || selectedInterests.length === 0}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gray-900 text-white text-sm font-medium rounded hover:bg-gray-800 disabled:opacity-40"
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
