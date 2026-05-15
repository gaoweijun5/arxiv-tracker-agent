import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Bookmark, BookmarkCheck, ExternalLink, MessageSquare, Send, Loader2, Download, Trash2 } from 'lucide-react'
import { papersApi, conversationsApi } from '../../../services/api'
import type { Paper, Conversation } from '../../../types'
import { format } from 'date-fns'
import ReactMarkdown from 'react-markdown'
import toast from 'react-hot-toast'

export default function PaperDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [paper, setPaper] = useState<Paper | null>(null)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [loading, setLoading] = useState(true)
  const [question, setQuestion] = useState('')
  const [asking, setAsking] = useState(false)
  const [showChat, setShowChat] = useState(false)

  useEffect(() => {
    if (id) {
      loadPaper(parseInt(id))
    }
  }, [id])

  const loadPaper = async (paperId: number) => {
    try {
      const [paperData, convData] = await Promise.all([
        papersApi.get(paperId),
        conversationsApi.list(paperId),
      ])
      setPaper(paperData)
      setConversations(convData)

      if (!paperData.is_read) {
        await papersApi.markRead(paperId)
      }
    } catch (error) {
      console.error('Failed to load paper:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleAskQuestion = async () => {
    if (!question.trim() || !paper) return

    setAsking(true)
    try {
      const history = conversations.map((c) => [
        { role: 'user', content: c.user_message },
        { role: 'assistant', content: c.ai_response },
      ]).flat()

      const response = await conversationsApi.ask({
        paper_id: paper.id,
        question: question.trim(),
        conversation_history: history,
      })

      const newConv: Conversation = {
        id: Date.now(),
        paper_id: paper.id,
        user_message: question.trim(),
        ai_response: response.response,
        created_at: new Date().toISOString(),
      }

      setConversations((prev) => [...prev, newConv])
      setQuestion('')
    } catch (error) {
      console.error('Failed to ask question:', error)
    } finally {
      setAsking(false)
    }
  }

  const handleClearChat = async () => {
    if (!paper) return
    try {
      await conversationsApi.clearByPaper(paper.id)
      setConversations([])
      toast.success('Chat history cleared')
    } catch (error) {
      console.error('Failed to clear chat:', error)
      toast.error('Failed to clear chat history')
    }
  }

  const handleToggleBookmark = async () => {
    if (!paper) return
    try {
      const result = await papersApi.toggleBookmark(paper.id)
      setPaper((prev) =>
        prev ? { ...prev, is_bookmarked: result.is_bookmarked } : null
      )
    } catch (error) {
      console.error('Failed to toggle bookmark:', error)
    }
  }

  const [downloading, setDownloading] = useState(false)

  const handleDownloadPdf = async () => {
    if (!paper) return
    setDownloading(true)
    try {
      const result = await papersApi.downloadPdf(paper.id)
      setPaper((prev) =>
        prev ? { ...prev, is_downloaded: true, local_pdf_path: 'downloaded' } : null
      )
      toast.success(`PDF processed: ${result.chunks} chunks created`)
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to download PDF')
    } finally {
      setDownloading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-sm text-gray-500">Loading...</div>
      </div>
    )
  }

  if (!paper) {
    return (
      <div className="text-center py-12">
        <p className="text-sm text-gray-500">Paper not found</p>
        <Link to="/papers" className="text-sm text-gray-600 hover:text-gray-900 mt-2 inline-block">
          Back to papers
        </Link>
      </div>
    )
  }

  return (
    <div className="flex gap-6 h-[calc(100vh-4rem)]">
      {/* Main content */}
      <div className={`flex-1 overflow-auto ${showChat ? 'w-1/2' : 'w-full'}`}>
        <div className="space-y-4">
          {/* Back button */}
          <Link
            to="/papers"
            className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-900"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Back
          </Link>

          {/* Paper header */}
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <h1 className="text-lg font-semibold text-gray-900">{paper.title}</h1>
                <p className="text-sm text-gray-600 mt-1">{paper.authors.join(', ')}</p>
                <div className="flex items-center gap-2 mt-2">
                  {paper.categories?.map((cat) => (
                    <span key={cat} className="text-[10px] px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded">
                      {cat}
                    </span>
                  ))}
                  {paper.published_date && (
                    <span className="text-xs text-gray-400">
                      {format(new Date(paper.published_date), 'MMM d, yyyy')}
                    </span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={handleToggleBookmark}
                  className="p-1.5 hover:bg-gray-100 rounded"
                >
                  {paper.is_bookmarked ? (
                    <BookmarkCheck className="w-4 h-4 text-gray-900" />
                  ) : (
                    <Bookmark className="w-4 h-4 text-gray-400" />
                  )}
                </button>
                {paper.pdf_url && (
                  <a
                    href={paper.pdf_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="p-1.5 hover:bg-gray-100 rounded"
                    title="View PDF"
                  >
                    <ExternalLink className="w-4 h-4 text-gray-400" />
                  </a>
                )}
                {!paper.is_downloaded && paper.pdf_url && (
                  <button
                    onClick={handleDownloadPdf}
                    disabled={downloading}
                    className="p-1.5 hover:bg-gray-100 rounded disabled:opacity-50"
                    title="Download PDF for AI Q&A"
                  >
                    {downloading ? (
                      <Loader2 className="w-4 h-4 text-gray-400 animate-spin" />
                    ) : (
                      <Download className="w-4 h-4 text-gray-400" />
                    )}
                  </button>
                )}
                {paper.is_downloaded && (
                  <span className="text-[10px] text-green-600 px-1.5 py-0.5 bg-green-50 rounded">
                    PDF Ready
                  </span>
                )}
                <button
                  onClick={() => setShowChat(!showChat)}
                  className={`px-2 py-1 text-xs font-medium rounded ${
                    showChat
                      ? 'bg-gray-900 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  <MessageSquare className="w-3.5 h-3.5 inline mr-1" />
                  Chat
                </button>
              </div>
            </div>
          </div>

          {/* AI Summary */}
          {paper.ai_summary && (
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <h2 className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Summary</h2>
              <p className="text-sm text-gray-700 leading-relaxed">{paper.ai_summary}</p>
              {paper.ai_summary_zh && (
                <p className="text-sm text-gray-500 mt-2">{paper.ai_summary_zh}</p>
              )}
            </div>
          )}

          {/* Key Findings */}
          {paper.key_findings && paper.key_findings.length > 0 && (
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <h2 className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Key Findings</h2>
              <ul className="space-y-1.5">
                {paper.key_findings.map((finding, index) => (
                  <li key={index} className="text-sm text-gray-700 flex gap-2">
                    <span className="text-gray-400">{index + 1}.</span>
                    {finding}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Abstract */}
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <h2 className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Abstract</h2>
            <p className="text-sm text-gray-700 leading-relaxed">{paper.abstract}</p>
          </div>
        </div>
      </div>

      {/* Chat sidebar */}
      {showChat && (
        <div className="w-1/2 bg-white border border-gray-200 rounded-lg flex flex-col">
          <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
            <h2 className="text-sm font-medium text-gray-900">Ask about this paper</h2>
            {conversations.length > 0 && (
              <button
                onClick={handleClearChat}
                className="p-1 hover:bg-gray-100 rounded text-gray-400 hover:text-gray-600"
                title="Clear chat history"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-auto p-4 space-y-4">
            {conversations.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-sm text-gray-500">No questions yet</p>
                <p className="text-xs text-gray-400 mt-1">Ask anything about this paper</p>
              </div>
            ) : (
              conversations.map((conv) => (
                <div key={conv.id} className="space-y-3">
                  <div className="flex justify-end">
                    <div className="bg-gray-100 text-gray-900 px-3 py-2 rounded-lg max-w-[80%] text-sm">
                      {conv.user_message}
                    </div>
                  </div>
                  <div className="flex justify-start">
                    <div className="bg-gray-50 text-gray-700 px-3 py-2 rounded-lg max-w-[80%] text-sm">
                      <ReactMarkdown className="prose prose-sm max-w-none">
                        {conv.ai_response}
                      </ReactMarkdown>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Input */}
          <div className="p-3 border-t border-gray-200">
            <div className="flex gap-2">
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAskQuestion()}
                placeholder="Ask a question..."
                className="flex-1 px-3 py-1.5 text-sm border border-gray-200 rounded focus:outline-none focus:border-gray-400"
                disabled={asking}
              />
              <button
                onClick={handleAskQuestion}
                disabled={!question.trim() || asking}
                className="px-3 py-1.5 bg-gray-900 text-white text-sm rounded hover:bg-gray-800 disabled:opacity-40"
              >
                {asking ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
