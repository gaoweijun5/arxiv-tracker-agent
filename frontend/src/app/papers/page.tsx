import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Search, ChevronLeft, ChevronRight, Trash2, ExternalLink, Bookmark, BookmarkCheck, ChevronUp, ChevronDown } from 'lucide-react'
import { papersApi } from '../../services/api'
import type { Paper, PaperListResponse } from '../../types'
import { format } from 'date-fns'
import toast from 'react-hot-toast'

export default function PapersPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [papers, setPapers] = useState<Paper[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)

  const page = parseInt(searchParams.get('page') || '1')
  const pageSize = 20
  const isRead = searchParams.get('unread') === 'true' ? false : undefined
  const isBookmarked = searchParams.get('bookmarked') === 'true' ? true : undefined
  const sortBy = searchParams.get('sort_by') || 'published_date'
  const sortOrder = searchParams.get('sort_order') || 'desc'

  useEffect(() => {
    loadPapers()
  }, [page, isRead, isBookmarked, sortBy, sortOrder])

  const loadPapers = async () => {
    setLoading(true)
    try {
      const data: PaperListResponse = await papersApi.list({
        page,
        page_size: pageSize,
        is_read: isRead,
        is_bookmarked: isBookmarked,
        sort_by: sortBy,
        sort_order: sortOrder,
      })
      setPapers(data.papers)
      setTotal(data.total)
    } catch (error) {
      console.error('Failed to load papers:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSort = (field: string) => {
    const newParams = new URLSearchParams(searchParams)
    if (sortBy === field) {
      // Toggle order
      newParams.set('sort_order', sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      // New field, default to desc
      newParams.set('sort_by', field)
      newParams.set('sort_order', 'desc')
    }
    newParams.set('page', '1')
    setSearchParams(newParams)
  }

  const renderSortIcon = (field: string) => {
    if (sortBy !== field) {
      return <ChevronUp className="w-3 h-3 text-gray-300" />
    }
    return sortOrder === 'asc'
      ? <ChevronUp className="w-3 h-3 text-gray-600" />
      : <ChevronDown className="w-3 h-3 text-gray-600" />
  }

  const handleToggleBookmark = async (paper: Paper) => {
    try {
      const result = await papersApi.toggleBookmark(paper.id)
      setPapers((prev) =>
        prev.map((p) =>
          p.id === paper.id ? { ...p, is_bookmarked: result.is_bookmarked } : p
        )
      )
    } catch (error) {
      console.error('Failed to toggle bookmark:', error)
    }
  }

  const handleMarkRead = async (paper: Paper) => {
    if (paper.is_read) return
    try {
      await papersApi.markRead(paper.id)
      setPapers((prev) =>
        prev.map((p) => (p.id === paper.id ? { ...p, is_read: true } : p))
      )
    } catch (error) {
      console.error('Failed to mark as read:', error)
    }
  }

  const handleDelete = async (paper: Paper) => {
    if (!confirm(`Delete "${paper.title}"?`)) return
    try {
      await papersApi.delete(paper.id)
      setPapers((prev) => prev.filter((p) => p.id !== paper.id))
      setTotal((prev) => prev - 1)
      toast.success('Paper deleted')
    } catch (error) {
      toast.error('Failed to delete paper')
    }
  }

  const totalPages = Math.ceil(total / pageSize)

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Papers</h1>
          <p className="text-sm text-gray-500">{total} papers</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2 mb-4">
        <div className="flex items-center bg-white border border-gray-200 rounded-md overflow-hidden">
          <Link
            to={`/papers?sort_by=${sortBy}&sort_order=${sortOrder}`}
            className={`px-3 py-1.5 text-xs font-medium ${
              !isRead && !isBookmarked
                ? 'bg-gray-900 text-white'
                : 'text-gray-600 hover:bg-gray-50'
            }`}
          >
            All
          </Link>
          <Link
            to={`/papers?unread=true&sort_by=${sortBy}&sort_order=${sortOrder}`}
            className={`px-3 py-1.5 text-xs font-medium border-l border-gray-200 ${
              isRead === false
                ? 'bg-gray-900 text-white'
                : 'text-gray-600 hover:bg-gray-50'
            }`}
          >
            Unread
          </Link>
          <Link
            to={`/papers?bookmarked=true&sort_by=${sortBy}&sort_order=${sortOrder}`}
            className={`px-3 py-1.5 text-xs font-medium border-l border-gray-200 ${
              isBookmarked
                ? 'bg-gray-900 text-white'
                : 'text-gray-600 hover:bg-gray-50'
            }`}
          >
            Bookmarked
          </Link>
        </div>
      </div>

      {/* Papers Table */}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        {loading ? (
          <div className="px-4 py-8 text-center text-sm text-gray-500">Loading...</div>
        ) : papers.length === 0 ? (
          <div className="px-4 py-8 text-center">
            <p className="text-sm text-gray-500">No papers found</p>
            <p className="text-xs text-gray-400 mt-1">Try fetching some papers first</p>
          </div>
        ) : (
          <table>
            <thead>
              <tr className="bg-gray-50">
                <th className="w-8"></th>
                <th>Title</th>
                <th className="w-24">
                  <button
                    onClick={() => handleSort('published_date')}
                    className="inline-flex items-center gap-1 hover:text-gray-900"
                  >
                    Date
                    {renderSortIcon('published_date')}
                  </button>
                </th>
                <th className="w-20">
                  <button
                    onClick={() => handleSort('relevance_score')}
                    className="inline-flex items-center gap-1 hover:text-gray-900"
                  >
                    Score
                    {renderSortIcon('relevance_score')}
                  </button>
                </th>
                <th className="w-20">Actions</th>
              </tr>
            </thead>
            <tbody>
              {papers.map((paper) => (
                <tr key={paper.id}>
                  <td>
                    <button
                      onClick={() => handleToggleBookmark(paper)}
                      className="p-1 hover:bg-gray-100 rounded"
                    >
                      {paper.is_bookmarked ? (
                        <BookmarkCheck className="w-3.5 h-3.5 text-gray-900" />
                      ) : (
                        <Bookmark className="w-3.5 h-3.5 text-gray-300" />
                      )}
                    </button>
                  </td>
                  <td>
                    <Link
                      to={`/papers/${paper.id}`}
                      onClick={() => handleMarkRead(paper)}
                      className={`hover:text-gray-900 ${
                        paper.is_read ? 'text-gray-600' : 'text-gray-900 font-medium'
                      }`}
                    >
                      <span className="text-sm">{paper.title}</span>
                    </Link>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {paper.authors.slice(0, 3).join(', ')}
                      {paper.authors.length > 3 && ' et al.'}
                      {paper.categories?.[0] && (
                        <span className="ml-2 px-1.5 py-0.5 bg-gray-100 rounded text-[10px]">
                          {paper.categories[0]}
                        </span>
                      )}
                    </p>
                  </td>
                  <td className="text-xs text-gray-500">
                    {paper.published_date
                      ? format(new Date(paper.published_date), 'MMM d')
                      : '-'}
                  </td>
                  <td>
                    {paper.relevance_score != null && (
                      <span className="text-xs font-medium text-gray-700">
                        {Math.round(paper.relevance_score * 100)}%
                      </span>
                    )}
                  </td>
                  <td>
                    <div className="flex items-center gap-1">
                      {paper.pdf_url && (
                        <a
                          href={paper.pdf_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="p-1 hover:bg-gray-100 rounded"
                          title="View PDF"
                        >
                          <ExternalLink className="w-3.5 h-3.5 text-gray-400" />
                        </a>
                      )}
                      <button
                        onClick={() => handleDelete(paper)}
                        className="p-1 hover:bg-gray-100 rounded"
                        title="Delete"
                      >
                        <Trash2 className="w-3.5 h-3.5 text-gray-400" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-xs text-gray-500">
            Showing {(page - 1) * pageSize + 1}-{Math.min(page * pageSize, total)} of {total}
          </p>
          <div className="flex items-center gap-1">
            <button
              onClick={() => {
                const newParams = new URLSearchParams(searchParams)
                newParams.set('page', String(page - 1))
                setSearchParams(newParams)
              }}
              disabled={page <= 1}
              className="p-1.5 border border-gray-200 rounded hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="px-2 text-xs text-gray-600">
              {page} / {totalPages}
            </span>
            <button
              onClick={() => {
                const newParams = new URLSearchParams(searchParams)
                newParams.set('page', String(page + 1))
                setSearchParams(newParams)
              }}
              disabled={page >= totalPages}
              className="p-1.5 border border-gray-200 rounded hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
