/** Paper types */
export interface Paper {
  id: number
  arxiv_id: string
  title: string
  authors: string[]
  abstract: string
  categories: string[]
  published_date: string | null
  pdf_url: string | null
  ai_summary: string | null
  ai_summary_zh: string | null
  key_findings: string[] | null
  relevance_score: number | null
  is_downloaded: boolean
  is_read: boolean
  is_bookmarked: boolean
  created_at: string | null
  similarity_score?: number
}

export interface PaperListResponse {
  papers: Paper[]
  total: number
  page: number
  page_size: number
}

/** Interest types */
export interface Interest {
  id: number
  topic: string
  description: string | null
  keywords: string[]
  categories: string[]
  weight: number
  is_active: boolean
}

export interface InterestCreate {
  topic: string
  description?: string
  keywords: string[]
  categories: string[]
  weight: number
}

/** Recommendation types */
export interface Recommendation {
  id: number
  paper: Paper
  score: number
  reason: string | null
  is_viewed: boolean
  is_dismissed: boolean
  recommended_at: string | null
}

export interface RecommendationListResponse {
  recommendations: Recommendation[]
  total: number
  page: number
  page_size: number
}

/** Conversation types */
export interface Conversation {
  id: number
  paper_id: number
  user_message: string
  ai_response: string
  created_at: string | null
}

export interface QuestionRequest {
  paper_id: number
  question: string
  conversation_history?: { role: string; content: string }[]
}

export interface QuestionResponse {
  response: string
  sources: string[]
  error?: string
  requires_download?: boolean
  paper: {
    id: number
    title: string
    arxiv_id: string
  }
}

/** System types */
export interface SystemStats {
  total_papers: number
  total_interests: number
  total_recommendations: number
  unread_papers: number
  bookmarked_papers: number
  last_fetch: string | null
}

export interface FetchLog {
  id: number
  fetch_date: string | null
  source: string
  categories_fetched: string[] | null
  papers_found: number
  papers_relevant: number
  papers_downloaded: number
  status: string
  error_message: string | null
}

/** Search result */
export interface SearchResult {
  arxiv_id: string
  title: string
  score: number
  snippet: string
}
