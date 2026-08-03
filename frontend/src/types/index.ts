export interface Document {
  id: string
  filename: string
  chunk_count: number
  char_count: number
}

export interface Source {
  content: string
  filename: string
  doc_id: string
  chunk_index: number
  score: number
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
}
