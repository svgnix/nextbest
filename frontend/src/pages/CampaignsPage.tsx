import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { api } from '../api/client'
import PageState from '../components/PageState'
import { PageBar } from '../layout/AppShell'
import { useAsync } from '../lib/useAsync'
import { fadeRise, staggerContainer } from '../lib/motion'
import { NextBestAction, ActionStatus } from '../types'
import './CampaignsPage.css'

type Filter = 'all' | 'pending' | 'accepted' | 'skipped'

export default function CampaignsPage() {
  const { data, status, reload } = useAsync<NextBestAction[]>(() => api.campaigns(), [])
  const [items, setItems] = useState<NextBestAction[]>([])
  const [filter, setFilter] = useState<Filter>('all')

  useEffect(() => {
    if (data) setItems(data)
  }, [data])

  const act = (clientId: string, action: 'accept' | 'skip') => {
    const newStatus: ActionStatus = action === 'accept' ? 'accepted' : 'skipped'
    setItems((prev) => prev.map((i) => (i.client_id === clientId ? { ...i, action_status: newStatus } : i)))
    api.recordAction(clientId, action).catch(() => {})
  }

  const filtered = useMemo(() => {
    if (filter === 'all') return items
    return items.filter((i) => i.action_status === filter || (filter === 'accepted' && i.action_status === 'edited'))
  }, [items, filter])

  const counts = useMemo(() => ({
    all: items.length,
    pending: items.filter((i) => i.action_status === 'pending').length,
    accepted: items.filter((i) => i.action_status === 'accepted' || i.action_status === 'edited').length,
    skipped: items.filter((i) => i.action_status === 'skipped').length,
  }), [items])

  return (
    <>
      <PageBar title="Campaigns" meta={`${counts.pending} awaiting review`} />
      <div className="page stack">
        {status === 'loading' && <PageState status="loading" />}
        {status === 'error' && <PageState status="error" onRetry={reload} />}
        {status === 'ready' && (
          <>
            <div className="roster__filters">
              {(['all', 'pending', 'accepted', 'skipped'] as Filter[]).map((f) => (
                <button
                  key={f}
                  className={`roster__filter ${filter === f ? 'roster__filter--active' : ''}`}
                  onClick={() => setFilter(f)}
                >
                  {f} · {counts[f]}
                </button>
              ))}
            </div>

            <motion.div
              className="stack"
              variants={staggerContainer}
              initial="hidden"
              animate="show"
            >
              {filtered.map((c) => (
                <motion.div key={c.client_id} className={`panel campaign ${c.action_status !== 'pending' ? 'campaign--done' : ''}`} variants={fadeRise}>
                  <div className="campaign__top">
                    <div>
                      <Link className="link campaign__name" to={`/clients/${c.client_id}`}>{c.name}</Link>
                      <span className={`badge badge--${c.action_type.toLowerCase()}`}>{c.action_type}</span>
                      <StatusTag status={c.action_status} />
                    </div>
                    {c.action_status === 'pending' && (
                      <div className="campaign__actions">
                        <button className="card__btn card__btn--accept" onClick={() => act(c.client_id, 'accept')}>Accept</button>
                        <button className="card__btn card__btn--skip" onClick={() => act(c.client_id, 'skip')}>Skip</button>
                      </div>
                    )}
                  </div>
                  <p className="campaign__headline">{c.headline}</p>
                  <p className="campaign__draft">{c.draft_message}</p>
                </motion.div>
              ))}
              {filtered.length === 0 && <p className="state__text">Nothing here yet.</p>}
            </motion.div>
          </>
        )}
      </div>
    </>
  )
}

function StatusTag({ status }: { status: ActionStatus }) {
  if (status === 'pending') return null
  const label = status === 'edited' ? 'accepted' : status
  const cls = status === 'skipped' ? 'campaign__status--skip' : 'campaign__status--accept'
  return <span className={`campaign__status ${cls}`}>{label} · ready to send</span>
}
