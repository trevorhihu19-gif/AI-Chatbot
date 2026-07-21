const BASE = '/api/v1'

export interface Conversation {
  id: string
  title: string
  is_pinned: boolean
  is_archived: boolean
  model_used: string | null
  updated_at: string
}

export interface Document {
  id: string
  filename: string
  file_type: string
  size_bytes: number
  chunk_count: number | null
  status: 'pending' | 'processing' | 'ready' | 'failed'
  error_message: string | null
  created_at: string
}

export interface Usage {
  tokens_used: number
  tokens_limit: number
  tokens_remaining: number
  usage_percentage: number
  reset_at: string | null
}

export interface UserProfile {
  id: string
  email: string
  first_name: string | null
  last_name: string | null
  avatar_url: string | null
  plan_tier: string
  created_at: string
}


type TokenGetter = () => Promise<string | null>
let _getToken: TokenGetter = async () => null

export function setTokenGetter(fn: TokenGetter) {
  _getToken = fn
}

async function authHeaders(): Promise<HeadersInit> {
  const token = await _getToken()
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: await authHeaders(),
  })
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`)
  return res.json()
}

async function del(path: string): Promise<void> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'DELETE',
    headers: await authHeaders(),
  })
  if (!res.ok) throw new Error(`DELETE ${path} → ${res.status}`)
}

async function patch<T>(path: string, body?: object): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'PATCH',
    headers: await authHeaders(),
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`PATCH ${path} → ${res.status}`)
  return res.json()
}


export const api = {
  getMe: () => get<UserProfile>('/users/me'),
  getUsage: () => get<Usage>('/users/me/usage'),

  getConversations: () => get<Conversation[]>('/chat/conversations'),
  deleteConversation: (id: string) => del(`/chat/conversations/${id}`),
  pinConversation: (id: string) => patch(`/chat/conversations/${id}/pin`),

  getDocuments: () => get<Document[]>('/documents'),
  deleteDocument: (id: string) => del(`/documents/${id}`),

  uploadDocument: async (file: File, token: string): Promise<Document> => {
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(`${BASE}/documents/upload`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: form,
    })
    if (!res.ok) throw new Error(`Upload failed: ${res.status}`)
    return res.json()
  },
}

