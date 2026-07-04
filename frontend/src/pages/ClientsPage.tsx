import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import PageState from '../components/PageState'
import { PageBar } from '../layout/AppShell'
import { useAsync } from '../lib/useAsync'
import { money, signedPct } from '../lib/format'
import { ClientSummary } from '../types'
import './ClientsPage.css'

const SEGMENTS = ['Disengaging', 'Growth-minded', 'Steady loyalist', 'New & exploring']

export default function ClientsPage() {
  const { data, status, reload } = useAsync<ClientSummary[]>(() => api.clients(), [])
  const [q, setQ] = useState('')
  const [segment, setSegment] = useState('')

  const rows = useMemo(() => {
    let r = data ?? []
    if (segment) r = r.filter((c) => (c.segment as { label?: string }).label === segment)
    if (q) r = r.filter((c) => c.name.toLowerCase().includes(q.toLowerCase()))
    return r
  }, [data, q, segment])

  return (
    <>
      <PageBar title="Clients" meta={data ? `${data.length} in your book` : ''} />
      <div className="page stack">
        {status === 'loading' && <PageState status="loading" />}
        {status === 'error' && <PageState status="error" onRetry={reload} />}
        {status === 'ready' && (
          <>
            <div className="roster__controls">
              <input
                className="roster__search"
                placeholder="Search clients…"
                value={q}
                onChange={(e) => setQ(e.target.value)}
              />
              <div className="roster__filters">
                <button
                  className={`roster__filter ${segment === '' ? 'roster__filter--active' : ''}`}
                  onClick={() => setSegment('')}
                >
                  All
                </button>
                {SEGMENTS.map((s) => (
                  <button
                    key={s}
                    className={`roster__filter ${segment === s ? 'roster__filter--active' : ''}`}
                    onClick={() => setSegment(s)}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            <div className="panel panel--pad-lg">
              <table className="table">
                <thead>
                  <tr>
                    <th>Client</th>
                    <th>Segment</th>
                    <th>Signal</th>
                    <th className="num">Attrition</th>
                    <th className="num">Upsell</th>
                    <th className="num">Portfolio</th>
                    <th className="num">Last contact</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((c) => (
                    <tr key={c.client_id}>
                      <td><Link className="link" to={`/clients/${c.client_id}`}>{c.name}</Link></td>
                      <td className="text-muted">{(c.segment as { label?: string }).label ?? '—'}</td>
                      <td><span className={`badge badge--${c.action_type.toLowerCase()}`}>{c.action_type}</span></td>
                      <td className="num text-warm">{c.attrition_risk}%</td>
                      <td className="num text-cool">{c.upsell_ready}%</td>
                      <td className="num">{money(c.portfolio_value)} <span className="text-muted">({signedPct(c.portfolio_change_pct)})</span></td>
                      <td className="num">{c.days_since_last_contact}d ago</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {rows.length === 0 && <p className="state__text" style={{ padding: 'var(--space-6)' }}>No clients match.</p>}
            </div>
          </>
        )}
      </div>
    </>
  )
}
