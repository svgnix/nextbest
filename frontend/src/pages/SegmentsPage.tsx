import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { api } from '../api/client'
import BarList from '../components/charts/BarList'
import PageState from '../components/PageState'
import { PageBar } from '../layout/AppShell'
import { useAsync } from '../lib/useAsync'
import { fadeRise, staggerContainer } from '../lib/motion'
import { money } from '../lib/format'
import { SegmentSummary } from '../types'
import './SegmentsPage.css'

const SEGMENT_COLORS: Record<string, string> = {
  Disengaging: 'var(--warm-500)',
  'Growth-minded': 'var(--cool-500)',
  'Steady loyalist': 'var(--slate-500)',
  'New & exploring': 'var(--cool-600)',
}

export default function SegmentsPage() {
  const { data, status, reload } = useAsync<SegmentSummary[]>(() => api.segments(), [])

  return (
    <>
      <PageBar title="Segments" meta="Behavioural clustering · KMeans" />
      <div className="page stack">
        {status === 'loading' && <PageState status="loading" />}
        {status === 'error' && <PageState status="error" onRetry={reload} />}
        {status === 'ready' && data && (
          <motion.div variants={staggerContainer} initial="hidden" animate="show">
            <motion.p className="segments__intro" variants={fadeRise}>
              Clients are grouped by <b>behaviour</b> — engagement trend, flows, and life events — not by
              assets alone. Each cluster carries a suggested playbook the agent uses to frame outreach.
            </motion.p>
            <div className="grid grid--2">
              {data.map((s) => (
                <motion.div key={s.id} className="panel segment-card" variants={fadeRise}>
                  <div className="segment-card__head">
                    <span className="segment-card__dot" style={{ background: SEGMENT_COLORS[s.label] ?? 'var(--slate-500)' }} />
                    <h3 className="segment-card__title">{s.label}</h3>
                    <span className="segment-card__count mono">{s.count}</span>
                  </div>

                  <BarList
                    items={[
                      { label: 'Avg attrition', value: s.avg_attrition, color: 'var(--warm-500)', display: `${s.avg_attrition}%` },
                      { label: 'Avg upsell', value: s.avg_upsell, color: 'var(--cool-500)', display: `${s.avg_upsell}%` },
                    ]}
                    max={100}
                  />

                  <p className="segment-card__aum mono">{money(s.total_aum)} AUM</p>

                  <div className="segment-card__playbook">
                    <span className="eyebrow">Playbook</span>
                    <p>{s.playbook}</p>
                  </div>

                  <div className="chip-row">
                    {s.member_ids.map((id) => (
                      <Link key={id} to={`/clients/${id}`} className="chip">{id}</Link>
                    ))}
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.div>
        )}
      </div>
    </>
  )
}
