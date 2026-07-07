import {
  Advisor,
  AgentActivityItem,
  AgentMetrics,
  AgentRunRow,
  BookAnalytics,
  ChatResponse,
  ClientDetail,
  ClientSummary,
  EvalReport,
  MarketSectorDetail,
  NextBestAction,
  SegmentSummary,
} from '../types'

const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export const api = {
  advisors: () => get<Advisor[]>('/advisors'),
  dispatch: (advisor = 'A001') => get<NextBestAction[]>(`/dispatch?advisor_id=${advisor}`),
  clients: (advisor = 'A001', segment?: string, q?: string) => {
    const params = new URLSearchParams({ advisor_id: advisor })
    if (segment) params.set('segment', segment)
    if (q) params.set('q', q)
    return get<ClientSummary[]>(`/clients?${params.toString()}`)
  },
  client: (id: string) => get<ClientDetail>(`/clients/${id}`),
  segments: (advisor = 'A001') => get<SegmentSummary[]>(`/segments?advisor_id=${advisor}`),
  analytics: (advisor = 'A001') => get<BookAnalytics>(`/book/analytics?advisor_id=${advisor}`),
  market: () => get<MarketSectorDetail[]>('/market'),
  campaigns: (advisor = 'A001') => get<NextBestAction[]>(`/campaigns?advisor_id=${advisor}`),
  activity: (advisor = 'A001') => get<AgentActivityItem[]>(`/agent/activity?advisor_id=${advisor}`),
  agentMetrics: (advisor = 'A001') => get<AgentMetrics>(`/agent/metrics?advisor_id=${advisor}`),
  agentRuns: (advisor = 'A001') => get<AgentRunRow[]>(`/agent/runs?advisor_id=${advisor}`),
  evalReport: () => get<EvalReport>('/eval/report'),
  recordAction: (
    clientId: string,
    action: 'accept' | 'skip' | 'edit',
    extra?: { draft_text?: string; feedback?: string },
  ) => post<NextBestAction>(`/actions/${clientId}`, { action, ...extra }),
  chat: (query: string, clientId?: string) =>
    post<ChatResponse>('/chat', { query, client_id: clientId ?? null }),
  chatSuggestions: (clientId?: string) => {
    const params = clientId ? `?client_id=${clientId}` : ''
    return get<string[]>(`/chat/suggestions${params}`)
  },
}
