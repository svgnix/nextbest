import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { api } from '../api/client'
import BarList from '../components/charts/BarList'
import DonutChart from '../components/charts/DonutChart'
import PageState from '../components/PageState'
import { PageBar } from '../layout/AppShell'
import { useAsync } from '../lib/useAsync'
import { CountUp, fadeRise, staggerContainer } from '../lib/motion'
import { money } from '../lib/format'
import { BookAnalytics, ClientSummary } from '../types'

const SEGMENT_COLORS: Record<string, string> = {
  Disengaging: 'var(--warm-500)',
  'Growth-minded': 'var(--cool-500)',
  'Steady loyalist': 'var(--slate-500)',
  'New & exploring': 'var(--cool-600)',
}

interface Unit {
  value: number
  decimals: number
  prefix: string
  suffix: string
}

function moneyUnit(n: number): Unit {
  if (Math.abs(n) >= 1_000_000_000) return { value: n / 1_000_000_000, decimals: 2, prefix: '$', suffix: 'B' }
  if (Math.abs(n) >= 1_000_000) return { value: n / 1_000_000, decimals: 1, prefix: '$', suffix: 'M' }
  if (Math.abs(n) >= 1_000) return { value: n / 1_000, decimals: 0, prefix: '$', suffix: 'K' }
  return { value: n, decimals: 0, prefix: '$', suffix: '' }
}

export default function BookAnalyticsPage() {
  const { data, status, reload } = useAsync<BookAnalytics>(() => api.analytics(), [])

  const meta = data ? (
    <><CountUp value={data.total_clients} /> clients</>
  ) : ''

  return (
    <>
      <PageBar title="Book analytics" meta={meta} />
      <div className="page stack">
        {status === 'loading' && <PageState status="loading" />}
        {status === 'error' && <PageState status="error" onRetry={reload} />}
        {status === 'ready' && data && <Analytics data={data} />}
      </div>
    </>
  )
}

function Analytics({ data }: { data: BookAnalytics }) {
  const slices = data.segment_distribution.map((s) => ({
    label: s.label,
    value: s.count,
    color: SEGMENT_COLORS[s.label] ?? 'var(--slate-500)',
  }))

  const aum = moneyUnit(data.total_aum)
  const rev = moneyUnit(data.revenue_at_risk)
  const upsell = moneyUnit(data.upsell_pipeline)

  return (
    <motion.div
      className="stack"
      variants={staggerContainer}
      initial="hidden"
      animate="show"
    >
      <div className="grid grid--4">
        <Kpi label="Assets under management">
          <CountUp value={aum.value} decimals={aum.decimals} prefix={aum.prefix} suffix={aum.suffix} className="kpi__value kpi__value--cool" />
        </Kpi>
        <Kpi label="Revenue at risk" sub={`${data.urgent_count} urgent clients`}>
          <CountUp value={rev.value} decimals={rev.decimals} prefix={rev.prefix} suffix={rev.suffix} className="kpi__value kpi__value--warm" />
        </Kpi>
        <Kpi label="Upsell pipeline" sub={`${data.opportunity_count} opportunities`}>
          <CountUp value={upsell.value} decimals={upsell.decimals} prefix={upsell.prefix} suffix={upsell.suffix} className="kpi__value kpi__value--cool" />
        </Kpi>
        <Kpi label="Avg days since contact" sub="across the book">
          <CountUp value={data.avg_days_since_contact} className="kpi__value" />
        </Kpi>
      </div>

      <motion.div className="grid grid--2" variants={fadeRise}>
        <div className="panel">
          <div className="panel__head"><span className="panel__title">Behavioural segments</span></div>
          <DonutChart
            slices={slices}
            centerLabel={String(data.total_clients)}
            centerSub="CLIENTS"
          />
        </div>

        <div className="panel">
          <div className="panel__head"><span className="panel__title">Where the book sits</span></div>
          <BarList
            items={[
              { label: 'Urgent (at risk)', value: data.urgent_count, color: 'var(--warm-500)', display: String(data.urgent_count) },
              { label: 'Opportunity', value: data.opportunity_count, color: 'var(--cool-500)', display: String(data.opportunity_count) },
              { label: 'Watchlist', value: data.watchlist_count, color: 'var(--slate-500)', display: String(data.watchlist_count) },
            ]}
          />
          <p className="kpi__sub" style={{ marginTop: 'var(--space-4)' }}>
            Segmentation is behavioural, not AUM-based — engagement, flows, and life events drive the clusters.
          </p>
        </div>
      </motion.div>

      <motion.div className="grid grid--2" variants={fadeRise}>
        <ClientTable title="Top attrition risks" rows={data.top_at_risk} metric="attrition_risk" tone="warm" />
        <ClientTable title="Top upsell opportunities" rows={data.top_opportunities} metric="upsell_ready" tone="cool" />
      </motion.div>
    </motion.div>
  )
}

function Kpi({
  label,
  sub,
  children,
}: {
  label: string
  sub?: string
  children: React.ReactNode
}) {
  return (
    <motion.div className="kpi" variants={fadeRise}>
      <span className="kpi__label">{label}</span>
      {children}
      {sub && <span className="kpi__sub">{sub}</span>}
    </motion.div>
  )
}

function ClientTable({
  title,
  rows,
  metric,
  tone,
}: {
  title: string
  rows: ClientSummary[]
  metric: 'attrition_risk' | 'upsell_ready'
  tone: 'warm' | 'cool'
}) {
  return (
    <div className="panel">
      <div className="panel__head"><span className="panel__title">{title}</span></div>
      <table className="table">
        <thead>
          <tr>
            <th>Client</th>
            <th className="num">{metric === 'attrition_risk' ? 'Risk' : 'Ready'}</th>
            <th className="num">Portfolio</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.client_id}>
              <td><Link className="link" to={`/clients/${r.client_id}`}>{r.name}</Link></td>
              <td className={`num ${tone === 'warm' ? 'text-warm' : 'text-cool'}`}>{r[metric]}%</td>
              <td className="num">{money(r.portfolio_value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
