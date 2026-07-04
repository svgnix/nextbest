import { Link } from 'react-router-dom'
import { api } from '../api/client'
import BarList from '../components/charts/BarList'
import DonutChart from '../components/charts/DonutChart'
import PageState from '../components/PageState'
import { PageBar } from '../layout/AppShell'
import { useAsync } from '../lib/useAsync'
import { money } from '../lib/format'
import { BookAnalytics, ClientSummary } from '../types'

const SEGMENT_COLORS: Record<string, string> = {
  Disengaging: 'var(--warm-500)',
  'Growth-minded': 'var(--cool-500)',
  'Steady loyalist': 'var(--slate-500)',
  'New & exploring': 'var(--cool-600)',
}

export default function BookAnalyticsPage() {
  const { data, status, reload } = useAsync<BookAnalytics>(() => api.analytics(), [])

  return (
    <>
      <PageBar title="Book analytics" meta={data ? `${data.total_clients} clients` : ''} />
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

  return (
    <>
      <div className="grid grid--4">
        <Kpi label="Assets under management" value={money(data.total_aum)} />
        <Kpi label="Revenue at risk" value={money(data.revenue_at_risk)} tone="warm" sub={`${data.urgent_count} urgent clients`} />
        <Kpi label="Upsell pipeline" value={money(data.upsell_pipeline)} tone="cool" sub={`${data.opportunity_count} opportunities`} />
        <Kpi label="Avg days since contact" value={String(data.avg_days_since_contact)} sub="across the book" />
      </div>

      <div className="grid grid--2">
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
      </div>

      <div className="grid grid--2">
        <ClientTable title="Top attrition risks" rows={data.top_at_risk} metric="attrition_risk" tone="warm" />
        <ClientTable title="Top upsell opportunities" rows={data.top_opportunities} metric="upsell_ready" tone="cool" />
      </div>
    </>
  )
}

function Kpi({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: 'warm' | 'cool' }) {
  return (
    <div className="kpi">
      <span className="kpi__label">{label}</span>
      <span className={`kpi__value ${tone === 'warm' ? 'kpi__value--warm' : tone === 'cool' ? 'kpi__value--cool' : ''}`}>{value}</span>
      {sub && <span className="kpi__sub">{sub}</span>}
    </div>
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
