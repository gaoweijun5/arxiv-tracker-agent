import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ChevronLeft, ChevronRight, Trash2, ExternalLink, Bookmark, BookmarkCheck, ChevronUp, ChevronDown } from 'lucide-react'
import { papersApi } from '../../services/api'
import type { Paper, PaperListResponse } from '../../types'
import { format } from 'date-fns'
import toast from 'react-hot-toast'

export default function PapersPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [papers, setPapers] = useState<Paper[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [deleting, setDeleting] = useState(false)

  const page = parseInt(searchParams.get('page') || '1')
  const pageSize = 20
  const isRead = searchParams.get('unread') === 'true' ? false : undefined
  const isBookmarked = searchParams.get('bookmarked') === 'true' ? true : undefined
  const sortBy = searchParams.get('sort_by') || 'published_date'
  const sortOrder = searchParams.get('sort_order') || 'desc'

  useEffect(() => {
    loadPapers()
    setSelected(new Set())
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
      newParams.set('sort_order', sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      newParams.set('sort_by', field)
      newParams.set('sort_order', 'desc')
    }
    newParams.set('page', '1')
    setSearchParams(newParams)
  }

  const renderSortIcon = (field: string) => {
    if (sortBy !== field) {
      return <ChevronUp className="w-3 h-3 text-white/30" />
    }
    return sortOrder === 'asc'
      ? <ChevronUp className="w-3 h-3 text-white/70" />
      : <ChevronDown className="w-3 h-3 text-white/70" />
  }

  const toggleSelect = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleSelectAll = () => {
    if (selected.size === papers.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(papers.map((p) => p.id)))
    }
  }

  const handleBatchDelete = async () => {
    if (selected.size === 0) return
    if (!confirm(`Delete ${selected.size} selected papers?`)) return

    setDeleting(true)
    try {
      const result = await papersApi.batchDelete(Array.from(selected))
      setPapers((prev) => prev.filter((p) => !selected.has(p.id)))
      setTotal((prev) => prev - result.deleted)
      setSelected(new Set())
      toast.success(`Deleted ${result.deleted} papers`)
    } catch (error) {
      toast.error('Failed to delete papers')
    } finally {
      setDeleting(false)
    }
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
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between fade-in stagger-1">
        <div>
          <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Outfit, sans-serif' }}>
            Papers
          </h1>
          <p className="text-sm text-white/60 mt-1">{total} papers</p>
        </div>
        {selected.size > 0 && (
          <button
            onClick={handleBatchDelete}
            disabled={deleting}
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-red-500/80 text-white text-sm font-medium rounded-2xl hover:bg-red-500 disabled:opacity-50 transition-all duration-300 backdrop-blur-sm border border-red-400/30"
          >
            <Trash2 className="w-4 h-4" />
            {deleting ? 'Deleting...' : `Delete ${selected.size} selected`}
          </button>
        )}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2 fade-in stagger-2">
        <div className="flex items-center glass-card overflow-hidden">
          <Link
            to={`/papers?sort_by=${sortBy}&sort_order=${sortOrder}`}
            className={`px-4 py-2.5 text-xs font-medium transition-all duration-300 ${
              !isRead && !isBookmarked
                ? 'bg-white/20 text-white'
                : 'text-white/60 hover:bg-white/10 hover:text-white'
            }`}
          >
            All
          </Link>
          <Link
            to={`/papers?unread=true&sort_by=${sortBy}&sort_order=${sortOrder}`}
            className={`px-4 py-2.5 text-xs font-medium transition-all duration-300 ${
              isRead === false
                ? 'bg-white/20 text-white'
                : 'text-white/60 hover:bg-white/10 hover:text-white'
            }`}
          >
            Unread
          </Link>
          <Link
            to={`/papers?bookmarked=true&sort_by=${sortBy}&sort_order=${sortOrder}`}
            className={`px-4 py-2.5 text-xs font-medium transition-all duration-300 ${
              isBookmarked
                ? 'bg-white/20 text-white'
                : 'text-white/60 hover:bg-white/10 hover:text-white'
            }`}
          >
            Bookmarked
          </Link>
        </div>
      </div>

      {/* Papers Table */}
      <div className="glass-card overflow-hidden fade-in stagger-3">
        {loading ? (
          <div className="px-6 py-8 text-center text-sm text-white/60">Loading...</div>
        ) : papers.length === 0 ? (
          <div className="px-6 py-8 text-center">
            <p className="text-sm text-white/60">No papers found</p>
            <p className="text-xs text-white/40 mt-1">Try fetching some papers first</p>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th className="w-8 px-2">
                  <input
                    type="checkbox"
                    checked={papers.length > 0 && selected.size === papers.length}
                    onChange={toggleSelectAll}
                    className="rounded"
                  />
                </th>
                <th className="w-8"></th>
                <th>Title</th>
                <th className="w-24">
                  <button
                    onClick={() => handleSort('published_date')}
                    className="inline-flex items-center gap-1 hover:text-white transition-colors duration-300"
                  >
                    Date
                    {renderSortIcon('published_date')}
                  </button>
                </th>
                <th className="w-20">
                  <button
                    onClick={() => handleSort('relevance_score')}
                    className="inline-flex items-center gap-1 hover:text-white transition-colors duration-300"
                  >
                    Score
                    {renderSortIcon('relevance_score')}
                  </button>
                </th>
                <th className="w-20">Actions</th>
              </tr>
            </thead>
            <tbody>
              {papers.map((paper, index) => (
                <tr
                  key={paper.id}
                  className={`${selected.has(paper.id) ? 'bg-white/10' : ''} fade-in`}
                  style={{ animationDelay: `${(index + 3) * 50}ms` }}
                >
                  <td className="px-2">
                    <input
                      type="checkbox"
                      checked={selected.has(paper.id)}
                      onChange={() => toggleSelect(paper.id)}
                      className="rounded"
                    />
                  </td>
                  <td>
                    <button
                      onClick={() => handleToggleBookmark(paper)}
                      className="p-1 hover:bg-white/10 rounded-lg transition-colors duration-300"
                    >
                      {paper.is_bookmarked ? (
                        <BookmarkCheck className="w-3.5 h-3.5 text-white" />
                      ) : (
                        <Bookmark className="w-3.5 h-3.5 text-white/30" />
                      )}
                    </button>
                  </td>
                  <td>
                    <Link
                      to={`/papers/${paper.id}`}
                      onClick={() => handleMarkRead(paper)}
                      className={`hover:text-white transition-colors duration-300 ${
                        paper.is_read ? 'text-white/70' : 'text-white font-medium'
                      }`}
                    >
                      <span className="text-sm">{paper.title}</span>
                    </Link>
                    <p className="text-xs text-white/50 mt-0.5">
                      {paper.authors.slice(0, 3).join(', ')}
                      {paper.authors.length > 3 && ' et al.'}
                      {paper.categories?.[0] && (
                        <span className="ml-2 px-2 py-0.5 bg-white/10 rounded-lg text-[10px]">
                          {paper.categories[0]}
                        </span>
                      )}
                    </p>
                  </td>
                  <td className="text-xs text-white/50">
                    {paper.published_date
                      ? format(new Date(paper.published_date), 'MMM d')
                      : '-'}
                  </td>
                  <td>
                    {paper.relevance_score != null && (
                      <span className="text-xs font-medium text-white/70">
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
                          className="p-1 hover:bg-white/10 rounded-lg transition-colors duration-300"
                          title="View PDF"
                        >
                          <ExternalLink className="w-3.5 h-3.5 text-white/50" />
                        </a>
                      )}
                      <button
                        onClick={() => handleDelete(paper)}
                        className="p-1 hover:bg-white/10 rounded-lg transition-colors duration-300"
                        title="Delete"
                      >
                        <Trash2 className="w-3.5 h-3.5 text-white/50" />
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
        <div className="flex items-center justify-between fade-in stagger-5">
          <p className="text-xs text-white/50">
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
              className="p-2 glass-card hover:bg-white/20 disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-300"
            >
              <ChevronLeft className="w-4 h-4 text-white" />
            </button>
            <span className="px-3 text-xs text-white/60">
              {page} / {totalPages}
            </span>
            <button
              onClick={() => {
                const newParams = new URLSearchParams(searchParams)
                newParams.set('page', String(page + 1))
                setSearchParams(newParams)
              }}
              disabled={page >= totalPages}
              className="p-2 glass-card hover:bg-white/20 disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-300"
            >
              <ChevronRight className="w-4 h-4 text-white" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
