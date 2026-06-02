import { useEffect, useState } from 'react'
import { Search, CheckCircle, XCircle, Clock, Save, Trash2, ChevronLeft, ChevronRight } from 'lucide-react'
import { systemApi } from '../../services/api'
import type { FetchLog } from '../../types'
import { format } from 'date-fns'
import FetchModal from '../../components/FetchModal'
import toast from 'react-hot-toast'

export default function SettingsPage() {
  const [fetchLogs, setFetchLogs] = useState<FetchLog[]>([])
  const [logTotal, setLogTotal] = useState(0)
  const [logPage, setLogPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [showFetchModal, setShowFetchModal] = useState(false)

  const pageSize = 10

  // Scheduler config
  const [schedulerHour, setSchedulerHour] = useState(8)
  const [schedulerMinute, setSchedulerMinute] = useState(0)
  const [schedulerEnabled, setSchedulerEnabled] = useState(true)
  const [schedulerDaysBack, setSchedulerDaysBack] = useState(7)
  const [schedulerMaxResults, setSchedulerMaxResults] = useState(30)
  const [savingScheduler, setSavingScheduler] = useState(false)

  useEffect(() => {
    loadFetchLogs()
    loadSchedulerConfig()
  }, [logPage])

  const loadFetchLogs = async () => {
    setLoading(true)
    try {
      const data = await systemApi.getFetchLogs(pageSize, logPage)
      setFetchLogs(data.logs)
      setLogTotal(data.total)
    } catch (error) {
      console.error('Failed to load fetch logs:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadSchedulerConfig = async () => {
    try {
      const config = await systemApi.getSchedulerConfig()
      setSchedulerHour(config.hour)
      setSchedulerMinute(config.minute)
      setSchedulerEnabled(config.is_enabled)
      setSchedulerDaysBack(config.days_back ?? 7)
      setSchedulerMaxResults(config.max_results ?? 30)
    } catch (error) {
      console.error('Failed to load scheduler config:', error)
    }
  }

  const handleSaveScheduler = async () => {
    setSavingScheduler(true)
    try {
      await systemApi.updateSchedulerConfig(
        schedulerHour, schedulerMinute, schedulerEnabled,
        schedulerDaysBack, schedulerMaxResults
      )
      toast.success('Schedule updated')
    } catch (error) {
      toast.error('Failed to update schedule')
    } finally {
      setSavingScheduler(false)
    }
  }

  const handleDeleteLog = async (logId: number) => {
    try {
      await systemApi.deleteFetchLog(logId)
      setFetchLogs((prev) => prev.filter((l) => l.id !== logId))
      setLogTotal((prev) => prev - 1)
      toast.success('Log deleted')
    } catch (error) {
      toast.error('Failed to delete log')
    }
  }

  const formatTime = (hour: number, minute: number) => {
    return `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`
  }

  const totalLogPages = Math.ceil(logTotal / pageSize)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="fade-in stagger-1">
        <h1 className="text-2xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent" style={{ fontFamily: 'Outfit, sans-serif' }}>
          Settings
        </h1>
        <p className="text-sm text-gray-500 mt-1">System configuration and fetch history</p>
      </div>

      {/* Manual Fetch */}
      <div className="glass-card p-6 fade-in stagger-2">
        <h2 className="text-sm font-semibold text-gray-800 mb-2" style={{ fontFamily: 'Outfit, sans-serif' }}>
          Manual Fetch
        </h2>
        <p className="text-xs text-gray-500 mb-4">
          Fetch latest papers from arXiv. You can select specific topics and date range.
        </p>
        <button
          onClick={() => setShowFetchModal(true)}
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-indigo-500 to-purple-500 text-white text-sm font-medium rounded-2xl hover:from-indigo-600 hover:to-purple-600 transition-all duration-300 hover:scale-105"
        >
          <Search className="w-4 h-4" />
          Fetch Papers
        </button>
      </div>

      {/* Auto Fetch Schedule */}
      <div className="glass-card p-6 fade-in stagger-3">
        <div className="flex items-center gap-2 mb-4">
          <Clock className="w-4 h-4 text-gray-500" />
          <h2 className="text-sm font-semibold text-gray-800" style={{ fontFamily: 'Outfit, sans-serif' }}>
            Auto Fetch Schedule
          </h2>
        </div>
        <p className="text-xs text-gray-500 mb-4">
          Configure when to automatically fetch new papers every day.
        </p>

        <div className="flex items-end gap-4">
          <div className="flex items-center gap-2">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Hour</label>
              <select
                value={schedulerHour}
                onChange={(e) => setSchedulerHour(parseInt(e.target.value))}
                className="px-3 py-2 text-sm bg-white/80 border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400 text-gray-800 transition-all duration-300"
              >
                {Array.from({ length: 24 }, (_, i) => (
                  <option key={i} value={i}>
                    {i.toString().padStart(2, '0')}
                  </option>
                ))}
              </select>
            </div>
            <span className="text-sm text-gray-400 pb-1">:</span>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Minute</label>
              <select
                value={schedulerMinute}
                onChange={(e) => setSchedulerMinute(parseInt(e.target.value))}
                className="px-3 py-2 text-sm bg-white/80 border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400 text-gray-800 transition-all duration-300"
              >
                {Array.from({ length: 60 }, (_, i) => (
                  <option key={i} value={i}>
                    {i.toString().padStart(2, '0')}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <label className="flex items-center gap-2 pb-1">
            <input
              type="checkbox"
              checked={schedulerEnabled}
              onChange={(e) => setSchedulerEnabled(e.target.checked)}
              className="rounded"
            />
            <span className="text-sm text-gray-600">Enabled</span>
          </label>

          <button
            onClick={handleSaveScheduler}
            disabled={savingScheduler}
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-indigo-500 to-purple-500 text-white text-sm font-medium rounded-2xl hover:from-indigo-600 hover:to-purple-600 disabled:opacity-50 transition-all duration-300"
          >
            <Save className="w-4 h-4" />
            {savingScheduler ? 'Saving...' : 'Save'}
          </button>
        </div>

        <div className="flex items-end gap-4 mt-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Search Period (days)</label>
            <select
              value={schedulerDaysBack}
              onChange={(e) => setSchedulerDaysBack(parseInt(e.target.value))}
              className="px-3 py-2 text-sm bg-white/80 border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400 text-gray-800 transition-all duration-300"
            >
              <option value={1}>1 day</option>
              <option value={3}>3 days</option>
              <option value={7}>7 days</option>
              <option value={14}>14 days</option>
              <option value={30}>30 days</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Max Results per Topic</label>
            <select
              value={schedulerMaxResults}
              onChange={(e) => setSchedulerMaxResults(parseInt(e.target.value))}
              className="px-3 py-2 text-sm bg-white/80 border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400 text-gray-800 transition-all duration-300"
            >
              <option value={10}>10 papers</option>
              <option value={20}>20 papers</option>
              <option value={30}>30 papers</option>
              <option value={50}>50 papers</option>
            </select>
          </div>
        </div>

        <p className="text-xs text-gray-400 mt-4">
          {schedulerEnabled
            ? `Papers will be fetched daily at ${formatTime(schedulerHour, schedulerMinute)}`
            : 'Auto fetch is disabled'}
        </p>
      </div>

      {/* Fetch History */}
      <div className="glass-card overflow-hidden fade-in stagger-4">
        <div className="px-6 py-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-800" style={{ fontFamily: 'Outfit, sans-serif' }}>
            Fetch History
          </h2>
          <span className="text-xs text-gray-400">{logTotal} total</span>
        </div>

        {loading ? (
          <div className="px-6 py-8 text-center text-sm text-gray-500">Loading...</div>
        ) : fetchLogs.length === 0 ? (
          <div className="px-6 py-8 text-center">
            <p className="text-sm text-gray-500">No fetch history</p>
          </div>
        ) : (
          <>
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Source</th>
                  <th>Status</th>
                  <th>Found</th>
                  <th>Relevant</th>
                  <th>Topics</th>
                  <th className="w-12"></th>
                </tr>
              </thead>
              <tbody>
                {fetchLogs.map((log, index) => (
                  <tr
                    key={log.id}
                    className="fade-in"
                    style={{ animationDelay: `${(index + 4) * 50}ms` }}
                  >
                    <td className="text-xs text-gray-600">
                      {log.fetch_date
                        ? format(new Date(log.fetch_date), 'MMM d, HH:mm')
                        : '-'}
                    </td>
                    <td>
                      <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-lg ${
                        log.source === 'auto'
                          ? 'bg-blue-100 text-blue-700'
                          : 'bg-gray-100 text-gray-600'
                      }`}>
                        {log.source === 'auto' ? 'Auto' : 'Manual'}
                      </span>
                    </td>
                    <td>
                      {log.status === 'success' ? (
                        <span className="inline-flex items-center gap-1 text-xs text-green-600">
                          <CheckCircle className="w-3 h-3" />
                          Success
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-xs text-red-600">
                          <XCircle className="w-3 h-3" />
                          Failed
                        </span>
                      )}
                    </td>
                    <td className="text-xs text-gray-600">{log.papers_found}</td>
                    <td className="text-xs text-gray-600">{log.papers_relevant}</td>
                    <td className="text-xs text-gray-500 max-w-xs truncate">
                      {log.categories_fetched?.join(', ') || '-'}
                    </td>
                    <td>
                      <button
                        onClick={() => handleDeleteLog(log.id)}
                        className="p-1 hover:bg-red-50 rounded-lg transition-colors duration-300"
                        title="Delete"
                      >
                        <Trash2 className="w-3.5 h-3.5 text-gray-400" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Pagination */}
            {totalLogPages > 1 && (
              <div className="px-6 py-4 flex items-center justify-between">
                <p className="text-xs text-gray-500">
                  Page {logPage} of {totalLogPages}
                </p>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setLogPage((p) => Math.max(1, p - 1))}
                    disabled={logPage <= 1}
                    className="p-2 glass-card hover:bg-indigo-50 disabled:opacity-40 transition-all duration-300"
                  >
                    <ChevronLeft className="w-3.5 h-3.5 text-gray-600" />
                  </button>
                  <button
                    onClick={() => setLogPage((p) => Math.min(totalLogPages, p + 1))}
                    disabled={logPage >= totalLogPages}
                    className="p-2 glass-card hover:bg-indigo-50 disabled:opacity-40 transition-all duration-300"
                  >
                    <ChevronRight className="w-3.5 h-3.5 text-gray-600" />
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* System Info */}
      <div className="glass-card p-6 fade-in stagger-5">
        <h2 className="text-sm font-semibold text-gray-800 mb-4" style={{ fontFamily: 'Outfit, sans-serif' }}>
          System
        </h2>
        <div className="grid grid-cols-2 gap-3 text-xs">
          <div>
            <span className="text-gray-500">Version</span>
            <span className="ml-2 text-gray-800">0.1.0</span>
          </div>
          <div>
            <span className="text-gray-500">Backend</span>
            <span className="ml-2 text-gray-800">FastAPI + LangGraph</span>
          </div>
          <div>
            <span className="text-gray-500">LLM</span>
            <span className="ml-2 text-gray-800">DeepSeek v4 Flash</span>
          </div>
          <div>
            <span className="text-gray-500">Embedding</span>
            <span className="ml-2 text-gray-800">DashScope v4</span>
          </div>
        </div>
      </div>

      {/* Fetch Modal */}
      <FetchModal
        isOpen={showFetchModal}
        onClose={() => setShowFetchModal(false)}
        onComplete={() => {
          loadFetchLogs()
        }}
      />
    </div>
  )
}
