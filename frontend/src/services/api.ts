import axios from 'axios'
import type {
  Paper,
  PaperListResponse,
  Interest,
  InterestCreate,
  Recommendation,
  RecommendationListResponse,
  Conversation,
  QuestionRequest,
  QuestionResponse,
  SystemStats,
  FetchLog,
  SearchResult,
} from '../types'

const api = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
})

/** Papers API */
export const papersApi = {
  list: async (params: {
    page?: number
    page_size?: number
    category?: string
    is_read?: boolean
    is_bookmarked?: boolean
    sort_by?: string
    sort_order?: string
  }): Promise<PaperListResponse> => {
    const { data } = await api.get('/papers', { params })
    return data
  },

  get: async (id: number): Promise<Paper> => {
    const { data } = await api.get(`/papers/${id}`)
    return data
  },

  markRead: async (id: number): Promise<void> => {
    await api.put(`/papers/${id}/read`)
  },

  toggleBookmark: async (id: number): Promise<{ is_bookmarked: boolean }> => {
    const { data } = await api.put(`/papers/${id}/bookmark`)
    return data
  },

  setRelevance: async (id: number, is_relevant: boolean): Promise<void> => {
    await api.put(`/papers/${id}/relevance`, null, { params: { is_relevant } })
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/papers/${id}`)
  },

  batchDelete: async (paperIds: number[]): Promise<{ deleted: number }> => {
    const { data } = await api.post('/papers/batch-delete', { paper_ids: paperIds })
    return data
  },

  downloadPdf: async (id: number): Promise<{ message: string; text_length: number; chunks: number }> => {
    const { data } = await api.post(`/papers/${id}/download`)
    return data
  },

  search: async (query: string, k?: number): Promise<{ results: SearchResult[] }> => {
    const { data } = await api.post('/papers/search', null, { params: { query, k } })
    return data
  },

  getSimilar: async (paperId: number, k?: number): Promise<{ papers: Paper[]; total: number }> => {
    const { data } = await api.get(`/papers/${paperId}/similar`, { params: { k } })
    return data
  },
}

/** Interests API */
export const interestsApi = {
  list: async (active_only?: boolean): Promise<Interest[]> => {
    const { data } = await api.get('/interests', { params: { active_only } })
    return data
  },

  create: async (interest: InterestCreate): Promise<Interest> => {
    const { data } = await api.post('/interests', interest)
    return data
  },

  get: async (id: number): Promise<Interest> => {
    const { data } = await api.get(`/interests/${id}`)
    return data
  },

  update: async (id: number, update: Partial<InterestCreate>): Promise<Interest> => {
    const { data } = await api.put(`/interests/${id}`, update)
    return data
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/interests/${id}`)
  },
}

/** Recommendations API */
export const recommendationsApi = {
  list: async (params: {
    page?: number
    page_size?: number
    viewed?: boolean
    dismissed?: boolean
    min_score?: number
  }): Promise<RecommendationListResponse> => {
    const { data } = await api.get('/recommendations', { params })
    return data
  },

  getToday: async (): Promise<{ recommendations: Recommendation[] }> => {
    const { data } = await api.get('/recommendations/today')
    return data
  },

  getDigest: async (): Promise<{ digest: string; papers: Paper[] }> => {
    const { data } = await api.get('/recommendations/digest')
    return data
  },

  markViewed: async (id: number): Promise<void> => {
    await api.put(`/recommendations/${id}/viewed`)
  },

  dismiss: async (id: number): Promise<void> => {
    await api.put(`/recommendations/${id}/dismiss`)
  },

  refresh: async (): Promise<{
    message: string
    papers_found: number
    papers_relevant: number
    recommendations: number
    digest: string
  }> => {
    const { data } = await api.post('/recommendations/refresh')
    return data
  },
}

/** Conversations API */
export const conversationsApi = {
  ask: async (request: QuestionRequest): Promise<QuestionResponse> => {
    const { data } = await api.post('/conversations/ask', request)
    return data
  },

  list: async (paperId: number): Promise<Conversation[]> => {
    const { data } = await api.get(`/conversations/${paperId}`)
    return data
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/conversations/${id}`)
  },

  clearByPaper: async (paperId: number): Promise<void> => {
    await api.delete(`/conversations/paper/${paperId}`)
  },
}

/** System API */
export const systemApi = {
  getStats: async (): Promise<SystemStats> => {
    const { data } = await api.get('/system/stats')
    return data
  },

  getInterests: async (): Promise<any[]> => {
    const { data } = await api.get('/system/interests')
    return data
  },

  triggerFetch: async (): Promise<{
    status: string
    task_id?: string
    papers_found?: number
    papers_relevant?: number
    papers_saved?: number
    digest?: string
  }> => {
    const { data } = await api.post('/system/fetch', { days_back: 7, max_results: 30 })
    return data
  },

  triggerFetchWithOptions: async (options: {
    interest_ids?: number[]
    days_back?: number
    max_results?: number
  }): Promise<{
    status: string
    task_id?: string
    message?: string
    interests?: any[]
  }> => {
    const { data } = await api.post('/system/fetch', options)
    return data
  },

  cancelFetch: async (taskId: string): Promise<void> => {
    await api.post(`/system/fetch/${taskId}/cancel`)
  },

  getFetchLogs: async (limit?: number, page?: number): Promise<{ logs: FetchLog[]; total: number; page: number; page_size: number }> => {
    const { data } = await api.get('/system/fetch-logs', { params: { limit, page } })
    return data
  },

  deleteFetchLog: async (logId: number): Promise<void> => {
    await api.delete(`/system/fetch-logs/${logId}`)
  },

  getSchedulerConfig: async (): Promise<{ hour: number; minute: number; is_enabled: boolean }> => {
    const { data } = await api.get('/system/scheduler')
    return data
  },

  updateSchedulerConfig: async (hour: number, minute: number, is_enabled: boolean): Promise<any> => {
    const { data } = await api.put('/system/scheduler', null, {
      params: { hour, minute, is_enabled },
    })
    return data
  },

  healthCheck: async (): Promise<{ status: string }> => {
    const { data } = await api.get('/system/health')
    return data
  },
}

export default api
