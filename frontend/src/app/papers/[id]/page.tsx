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

  const [similarPapers, setSimilarPapers] = useState<Paper[]>([])
  const [loadingSimilar, setLoadingSimilar] = useState(false)

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

      // Load similar papers
      loadSimilarPapers(paperId)
    } catch (error) {
      console.error('Failed to load paper:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadSimilarPapers = async (paperId: number) => {
    setLoadingSimilar(true)
    try {
      const data = await papersApi.getSimilar(paperId, 5)
      setSimilarPapers(data.papers)
    } catch (error) {
      console.error('Failed to load similar papers:', error)
    } finally {
      setLoadingSimilar(false)
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

      if (response.requires_download) {
        toast.error(response.response)
        return
      }

      const newConv: Conversation = {
        id: Date.now(),
        paper_id: paper.id,
        user_message: question.trim(),
        ai_response: response.response,
        created_at: new Date().toISOString(),
        retrieval_mode: response.retrieval_mode,
        source_chunks: response.source_chunks,
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
        <div className="space-y-6">
          {/* Back button */}
          <Link
            to="/papers"
            className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-[#1A1A1A] transition-colors duration-300"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Back
          </Link>

          {/* Paper header */}
          <div className="bg-white shadow-[0_4px_12px_rgba(0,0,0,0.08)] rounded-lg p-6">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <h1 className="text-lg font-semibold text-[#1A1A1A]">{paper.title}</h1>
                <p className="text-sm text-gray-600 mt-1">{paper.authors.join(', ')}</p>
                <div className="flex items-center gap-2 mt-2">
                  {paper.categories?.map((cat) => (
                    <span key={cat} className="text-[10px] px-2 py-0.5 bg-gray-100 text-gray-600 rounded-lg">
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
                  className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors duration-300"
                >
                  {paper.is_bookmarked ? (
                    <BookmarkCheck className="w-4 h-4 text-[#1A1A1A]" />
                  ) : (
                    <Bookmark className="w-4 h-4 text-gray-400" />
                  )}
                </button>
                {paper.pdf_url && (
                  <a
                    href={paper.pdf_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors duration-300"
                    title="View PDF"
                  >
                    <ExternalLink className="w-4 h-4 text-gray-400" />
                  </a>
                )}
                {!paper.is_downloaded && paper.pdf_url && (
                  <button
                    onClick={handleDownloadPdf}
                    disabled={downloading}
                    className="p-1.5 hover:bg-gray-100 rounded-lg disabled:opacity-50 transition-colors duration-300"
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
                  <span className="text-[10px] text-green-600 px-2 py-0.5 bg-green-50 rounded-lg">
                    PDF Ready
                  </span>
                )}
                <button
                  onClick={() => setShowChat(!showChat)}
                  className={`px-3 py-1 text-xs font-medium rounded-lg transition-all duration-300 ${
                    showChat
                      ? 'bg-[#1A1A1A] text-white'
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
            <div className="bg-white shadow-[0_4px_12px_rgba(0,0,0,0.08)] rounded-lg p-6">
              <h2 className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Summary</h2>
              <p className="text-sm text-gray-700 leading-relaxed">{paper.ai_summary}</p>
              {paper.ai_summary_zh && (
                <p className="text-sm text-gray-500 mt-2">{paper.ai_summary_zh}</p>
              )}
            </div>
          )}

          {/* Key Findings */}
          {paper.key_findings && paper.key_findings.length > 0 && (
            <div className="bg-white shadow-[0_4px_12px_rgba(0,0,0,0.08)] rounded-lg p-6">
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
          <div className="bg-white shadow-[0_4px_12px_rgba(0,0,0,0.08)] rounded-lg p-6">
            <h2 className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Abstract</h2>
            <p className="text-sm text-gray-700 leading-relaxed">{paper.abstract}</p>
          </div>

          {/* Similar Papers */}
          <div className="bg-white shadow-[0_4px_12px_rgba(0,0,0,0.08)] rounded-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xs font-medium text-gray-500 uppercase tracking-wide">Similar Papers</h2>
              {similarPapers.length > 0 && (
                <span className="text-xs text-gray-400">{similarPapers.length} found</span>
              )}
            </div>

            {loadingSimilar ? (
              <div className="flex items-center gap-2 py-4">
                <Loader2 className="w-4 h-4 text-gray-400 animate-spin" />
                <span className="text-sm text-gray-400">Finding similar papers...</span>
              </div>
            ) : similarPapers.length === 0 ? (
              <p className="text-sm text-gray-400 py-2">No similar papers found in database</p>
            ) : (
              <div className="space-y-3">
                {similarPapers.map((sp) => (
                  <Link
                    key={sp.id}
                    to={`/papers/${sp.id}`}
                    className="block p-4 rounded-lg hover:bg-gray-50 transition-colors duration-300"
                  >
                    <div className="flex items-start gap-3">
                      {sp.similarity_score != null && (
                        <span className="shrink-0 text-[10px] font-medium px-2 py-0.5 bg-blue-50 text-blue-600 rounded-lg mt-0.5">
                          {Math.round(sp.similarity_score * 100)}%
                        </span>
                      )}
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-[#1A1A1A] line-clamp-1">{sp.title}</p>
                        <p className="text-xs text-gray-500 mt-0.5">
                          {sp.authors.slice(0, 3).join(', ')}
                          {sp.authors.length > 3 && ' et al.'}
                          {sp.published_date && (
                            <span className="ml-2">
                              {format(new Date(sp.published_date), 'MMM yyyy')}
                            </span>
                          )}
                          {sp.is_bookmarked && (
                            <BookmarkCheck className="w-3 h-3 inline ml-1 text-[#1A1A1A]" />
                          )}
                        </p>
                        <p className="text-xs text-gray-400 mt-1 line-clamp-2">{sp.abstract}</p>
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Chat sidebar */}
      {showChat && (
        <div className="w-1/2 bg-white shadow-[0_4px_12px_rgba(0,0,0,0.08)] rounded-lg flex flex-col">
          <div className="px-6 py-4 flex items-center justify-between">
            <h2 className="text-sm font-medium text-[#1A1A1A]">Ask about this paper</h2>
            {conversations.length > 0 && (
              <button
                onClick={handleClearChat}
                className="p-1 hover:bg-gray-100 rounded-lg text-gray-400 hover:text-gray-600 transition-colors duration-300"
                title="Clear chat history"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-auto px-6 pb-6 space-y-4">
            {conversations.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-sm text-gray-500">No questions yet</p>
                <p className="text-xs text-gray-400 mt-1">Ask anything about this paper</p>
              </div>
            ) : (
              conversations.map((conv) => (
                <div key={conv.id} className="space-y-3">
                  <div className="flex justify-end">
                    <div className="bg-gray-100 text-[#1A1A1A] px-4 py-2 rounded-lg max-w-[80%] text-sm">
                      {conv.user_message}
                    </div>
                  </div>
                  <div className="flex justify-start">
                    <div className="bg-gray-50 text-gray-700 px-4 py-2 rounded-lg max-w-[80%] text-sm">
                      <ReactMarkdown className="prose prose-sm max-w-none">
                        {conv.ai_response}
                      </ReactMarkdown>
                      {conv.retrieval_mode && (
                        <div className="mt-2 pt-2">
                          {conv.retrieval_mode === 'hybrid_chunks' && conv.source_chunks?.length ? (
                            <div className="space-y-1.5">
                              <p className="text-[10px] font-medium text-gray-500 uppercase">Sources</p>
                              {conv.source_chunks.slice(0, 4).map((chunk) => (
                                <div key={chunk.id} className="text-[11px] text-gray-500">
                                  <span className="font-medium text-gray-600">
                                    Chunk {chunk.chunk_index}
                                    {chunk.page_start ? ` · p.${chunk.page_start}` : ''}
                                    {' · '}
                                    {Math.round(chunk.confidence * 100)}%
                                  </span>
                                  <span className="block line-clamp-1">{chunk.snippet}</span>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p className="text-[11px] text-gray-500">Used full paper context</p>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Input */}
          <div className="px-6 pb-4">
            <div className="flex gap-2">
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAskQuestion()}
                placeholder={paper.is_downloaded ? 'Ask a question...' : 'Download PDF before asking...'}
                className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-gray-400 transition-colors duration-300"
                disabled={asking || !paper.is_downloaded}
              />
              <button
                onClick={handleAskQuestion}
                disabled={!question.trim() || asking || !paper.is_downloaded}
                className="px-4 py-2 bg-[#1A1A1A] text-white text-sm rounded-lg hover:bg-[#3B82F6] disabled:opacity-40 transition-all duration-300"
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
