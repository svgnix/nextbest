import { Link } from 'react-router-dom'
import { api } from '../api/client'
import PageState from '../components/PageState'
import { PageBar } from '../layout/AppShell'
import { useAsync } from '../lib/useAsync'
import { AgentActivityItem } from '../types'
import './AgentActivityPage.css'

const AGENT_COLORS: Record<string, string> = {
  orchestrator: 'var(--ink-700)',
  segmentation: 'var(--cool-500)',
  propensity: 'var(--warm-500)',
  market: 'var(--cool-600)',
  portfolio: 'var(--cool-500)',
  outreach: 'var(--ink-800)',
}

const AGENTS = ['orchestrator', 'segmentation', 'propensity', 'market', 'portfolio', 'outreach']

export default function AgentActivityPage() {
  const { data, status, reload } = useAsync<AgentActivityItem[]>(() => api.activity(), [])

  return (
    <>
      <PageBar title="Agent activity" meta={data ? `${data.length} reasoning steps` : ''} />
      <div className="page stack">
        {status === 'loading' && <PageState status="loading" />}
        {status === 'error' && <PageState status="error" onRetry={reload} />}
        {status === 'ready' && data && (
          <>
            <div className="panel">
              <span className="eyebrow">The agent team</span>
              <div className="chip-row">
                {AGENTS.map((a) => (
                  <span key={a} className="activity__legend">
                    <span className="activity__legend-dot" style={{ background: AGENT_COLORS[a] }} />
                    {a}
                  </span>
                ))}
              </div>
              <p className="kpi__sub" style={{ marginTop: 'var(--space-3)' }}>
                Every recommendation is produced by an orchestrator delegating to specialist agents, then an
                outreach agent that drafts and critiques itself. This is the full audit trail.
              </p>
            </div>

            <div className="panel activity">
              {data.map((s, i) => (
                <div key={i} className="activity__row">
                  <span className="activity__dot" style={{ background: AGENT_COLORS[s.agent] ?? 'var(--slate-500)' }} />
                  <span className="activity__agent" style={{ color: AGENT_COLORS[s.agent] ?? 'var(--slate-500)' }}>
                    {s.agent}
                  </span>
                  <Link className="activity__client link" to={`/clients/${s.client_id}`}>
                    #{s.priority_rank} {s.client_name}
                  </Link>
                  <span className="activity__finding">{s.finding}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </>
  )
}
