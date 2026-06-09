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

/** Research report types */
export interface ResearchReport {
  id: number
  fetch_log_id: number | null
  source: string
  title: string
  summary: string | null
  content_md: string
  paper_ids: number[]
  stats: Record<string, number | string | null>
  status: string
  error_message: string | null
  created_at: string | null
  updated_at: string | null
  papers: Paper[]
}

export interface ResearchReportListResponse {
  reports: ResearchReport[]
  total: number
  page: number
  page_size: number
}

/** Conversation types */
export interface SourceChunk {
  id: number
  chunk_index: number
  page_start: number | null
  page_end: number | null
  confidence: number
  semantic_score: number
  keyword_score: number
  rrf_score: number
  snippet: string
}

export interface Conversation {
  id: number
  paper_id: number
  user_message: string
  ai_response: string
  created_at: string | null
  retrieval_mode?: 'hybrid_chunks' | 'full_text'
  source_chunks?: SourceChunk[]
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
  retrieval_mode?: 'hybrid_chunks' | 'full_text'
  source_chunks?: SourceChunk[]
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

/** Topic Explorer types */
export interface ExplorePaper {
  arxiv_id: string
  title: string
  authors: string[]
  abstract: string
  categories: string[]
  published_date: string
  pdf_url: string | null
  relevance_score: number
  relevance_reason: string
  summary: string
}

export interface ExploreResult {
  status: string
  query: string
  topic_understanding: string
  keywords: string[]
  expanded_keywords: string[]
  categories: string[]
  papers: ExplorePaper[]
  total_found: number
  total_analyzed: number
}

export interface ExploreResponse {
  status: string
  task_id: string
  message: string
}
