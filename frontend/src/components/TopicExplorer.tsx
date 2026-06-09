import { useState, useRef, useEffect } from 'react'
import { Search, Loader2, Sparkles, ExternalLink, Bookmark, X, ChevronDown, ChevronUp } from 'lucide-react'
import { exploreApi } from '../services/api'
import type { ExplorePaper, ExploreResult } from '../types'
import toast from 'react-hot-toast'

interface TopicExplorerProps {
  onPaperSaved?: () => void
}

export default function TopicExplorer({ onPaperSaved }: TopicExplorerProps) {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ExploreResult | null>(null)
  const [taskId, setTaskId] = useState<string | null>(null)
  const [progress, setProgress] = useState<{ step: string; message: string } | null>(null)
  const [expandedPapers, setExpandedPapers] = useState<Set<string>>(new Set())
  const [savingPapers, setSavingPapers] = useState<Set<string>>(new Set())
  const [savedPapers, setSavedPapers] = useState<Set<string>>(new Set())
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [])

  const connectWebSocket = (taskId: string) => {
    const ws = new WebSocket(`ws://localhost:8000/ws/progress/${taskId}`)

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === 'progress') {
        setProgress({ step: data.step, message: data.message })
      } else if (data.type === 'complete') {
        if (data.result?.type === 'explore_result') {
          setResult(data.result.result)
          toast.success(`Found ${data.result.result.papers.length} relevant papers`)
        }
        setLoading(false)
        setTaskId(null)
        setProgress(null)
      } else if (data.type === 'error') {
        toast.error(data.error || 'Exploration failed')
        setLoading(false)
        setTaskId(null)
        setProgress(null)
      }
    }

    ws.onerror = () => {
      toast.error('WebSocket connection error')
      setLoading(false)
      setTaskId(null)
      setProgress(null)
    }

    wsRef.current = ws
  }

  const handleExplore = async () => {
    if (!query.trim()) {
      toast.error('Please enter a topic to explore')
      return
    }

    setLoading(true)
    setResult(null)
    setSavedPapers(new Set())
    setProgress({ step: 'start', message: 'Starting exploration...' })

    try {
      const response = await exploreApi.start(query.trim())
      if (response.task_id) {
        setTaskId(response.task_id)
        connectWebSocket(response.task_id)
      }
    } catch (error) {
      toast.error('Failed to start exploration')
      setLoading(false)
      setProgress(null)
    }
  }

  const handleCancel = async () => {
    if (taskId) {
      try {
        await exploreApi.cancel(taskId)
      } catch (error) {
        // Ignore errors
      }
    }
    if (wsRef.current) {
      wsRef.current.close()
    }
    setLoading(false)
    setTaskId(null)
    setProgress(null)
  }

  const handleSavePaper = async (paper: ExplorePaper) => {
    if (savingPapers.has(paper.arxiv_id) || savedPapers.has(paper.arxiv_id)) {
      return
    }

    setSavingPapers(prev => new Set(prev).add(paper.arxiv_id))

    try {
      const response = await exploreApi.savePaper(paper)
      if (response.status === 'exists') {
        toast('Paper already in your collection', { icon: 'ℹ️' })
      } else {
        toast.success('Paper saved to your collection')
        setSavedPapers(prev => new Set(prev).add(paper.arxiv_id))
        onPaperSaved?.()
      }
    } catch (error) {
      toast.error('Failed to save paper')
    } finally {
      setSavingPapers(prev => {
        const next = new Set(prev)
        next.delete(paper.arxiv_id)
        return next
      })
    }
  }

  const togglePaperExpand = (arxivId: string) => {
    setExpandedPapers(prev => {
      const next = new Set(prev)
      if (next.has(arxivId)) {
        next.delete(arxivId)
      } else {
        next.add(arxivId)
      }
      return next
    })
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleExplore()
    }
  }

  return (
    <div className="space-y-4">
      {/* Input Area */}
      <div className="flex gap-3">
        <div className="flex-1 relative">
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about a research topic... (e.g., 'What are the latest advances in math reasoning benchmarks?')"
            className="w-full px-4 py-3 bg-white/80 border border-gray-200 rounded-xl resize-none focus:outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-200 transition-all duration-300 text-sm"
            rows={2}
            disabled={loading}
          />
        </div>
        <div className="flex flex-col gap-2">
          <button
            onClick={loading ? handleCancel : handleExplore}
            disabled={!loading && !query.trim()}
            className={`inline-flex items-center gap-2 px-5 py-3 text-sm font-medium rounded-xl transition-all duration-300 ${
              loading
                ? 'bg-red-500 hover:bg-red-600 text-white'
                : 'bg-gradient-to-r from-indigo-500 to-purple-500 hover:from-indigo-600 hover:to-purple-600 text-white shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed'
            }`}
          >
            {loading ? (
              <>
                <X className="w-4 h-4" />
                Cancel
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                Explore
              </>
            )}
          </button>
        </div>
      </div>

      {/* Progress */}
      {loading && progress && (
        <div className="glass-card p-4 fade-in">
          <div className="flex items-center gap-3">
            <Loader2 className="w-5 h-5 text-indigo-500 animate-spin" />
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-700">{progress.message}</p>
              <div className="mt-2 w-full bg-gray-200 rounded-full h-1.5">
                <div
                  className="bg-gradient-to-r from-indigo-500 to-purple-500 h-1.5 rounded-full transition-all duration-500"
                  style={{
                    width: progress.step === 'understand' ? '25%' :
                           progress.step === 'search' ? '50%' :
                           progress.step === 'analyze' ? '75%' :
                           progress.step === 'complete' ? '100%' : '10%'
                  }}
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-4 fade-in">
          {/* Topic Understanding */}
          <div className="glass-card p-4">
            <div className="flex items-start gap-3">
              <Sparkles className="w-5 h-5 text-indigo-500 mt-0.5" />
              <div>
                <h3 className="text-sm font-semibold text-gray-700">Topic Understanding</h3>
                <p className="text-sm text-gray-600 mt-1">{result.topic_understanding}</p>
                <div className="flex flex-wrap gap-2 mt-2">
                  {result.keywords.map((kw, i) => (
                    <span key={i} className="px-2 py-1 bg-indigo-100 text-indigo-700 rounded-lg text-xs">
                      {kw}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Results Summary */}
          <div className="flex items-center justify-between px-2">
            <p className="text-sm text-gray-600">
              Found <span className="font-semibold text-indigo-600">{result.papers.length}</span> relevant papers
              {result.total_found > 0 && (
                <span className="text-gray-400"> (from {result.total_found} total)</span>
              )}
            </p>
          </div>

          {/* Paper List */}
          {result.papers.length > 0 ? (
            <div className="space-y-3">
              {result.papers.map((paper, index) => (
                <div
                  key={paper.arxiv_id}
                  className="glass-card p-4 hover:shadow-lg transition-all duration-300"
                  style={{ animationDelay: `${index * 50}ms` }}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded text-xs font-medium">
                          {Math.round(paper.relevance_score * 100)}% match
                        </span>
                        <span className="text-xs text-gray-400">
                          {paper.categories.slice(0, 2).join(', ')}
                        </span>
                      </div>
                      <h4 className="text-sm font-semibold text-gray-800 line-clamp-2">
                        {paper.title}
                      </h4>
                      <p className="text-xs text-gray-500 mt-1">
                        {paper.authors.slice(0, 3).join(', ')}
                        {paper.authors.length > 3 && ' et al.'}
                      </p>

                      {/* Summary */}
                      <p className="text-sm text-gray-600 mt-2 line-clamp-3">
                        {paper.summary || paper.abstract}
                      </p>

                      {/* Relevance Reason */}
                      {paper.relevance_reason && (
                        <p className="text-xs text-indigo-600 mt-2 italic">
                          Why relevant: {paper.relevance_reason}
                        </p>
                      )}

                      {/* Expanded Abstract */}
                      {expandedPapers.has(paper.arxiv_id) && (
                        <div className="mt-3 pt-3 border-t border-gray-100">
                          <p className="text-xs text-gray-500 font-medium mb-1">Full Abstract:</p>
                          <p className="text-sm text-gray-600">{paper.abstract}</p>
                        </div>
                      )}
                    </div>

                    {/* Actions */}
                    <div className="flex flex-col gap-2">
                      <button
                        onClick={() => handleSavePaper(paper)}
                        disabled={savingPapers.has(paper.arxiv_id) || savedPapers.has(paper.arxiv_id)}
                        className={`p-2 rounded-lg transition-all duration-300 ${
                          savedPapers.has(paper.arxiv_id)
                            ? 'bg-green-100 text-green-600'
                            : savingPapers.has(paper.arxiv_id)
                            ? 'bg-gray-100 text-gray-400'
                            : 'bg-indigo-100 text-indigo-600 hover:bg-indigo-200'
                        }`}
                        title={savedPapers.has(paper.arxiv_id) ? 'Saved' : 'Save to collection'}
                      >
                        {savedPapers.has(paper.arxiv_id) ? (
                          <Bookmark className="w-4 h-4" />
                        ) : savingPapers.has(paper.arxiv_id) ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Bookmark className="w-4 h-4" />
                        )}
                      </button>
                      {paper.pdf_url && (
                        <a
                          href={paper.pdf_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="p-2 bg-gray-100 text-gray-600 rounded-lg hover:bg-gray-200 transition-all duration-300"
                          title="View PDF"
                        >
                          <ExternalLink className="w-4 h-4" />
                        </a>
                      )}
                      <button
                        onClick={() => togglePaperExpand(paper.arxiv_id)}
                        className="p-2 bg-gray-100 text-gray-600 rounded-lg hover:bg-gray-200 transition-all duration-300"
                        title={expandedPapers.has(paper.arxiv_id) ? 'Collapse' : 'Expand'}
                      >
                        {expandedPapers.has(paper.arxiv_id) ? (
                          <ChevronUp className="w-4 h-4" />
                        ) : (
                          <ChevronDown className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="glass-card p-8 text-center">
              <Search className="w-8 h-8 text-gray-300 mx-auto mb-2" />
              <p className="text-sm text-gray-500">No papers found for this topic</p>
              <p className="text-xs text-gray-400 mt-1">Try different keywords or a broader query</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
