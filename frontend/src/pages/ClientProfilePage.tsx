import { Link, useParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { api } from '../api/client'
import AssistantChat from '../components/AssistantChat'
import ConfidenceArc from '../components/ConfidenceArc'
import ReasoningTrace from '../components/ReasoningTrace'
import Sparkline from '../components/charts/Sparkline'
import TrendChart from '../components/charts/TrendChart'
import PageState from '../components/PageState'
import { PageBar } from '../layout/AppShell'
import { useAsync } from '../lib/useAsync'
import { CountUp, fadeRise, staggerContainer } from '../lib/motion'
import { money, signedPct, titleize } from '../lib/format'
import { ClientDetail } from '../types'
import './ClientProfilePage.css'

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

export default function ClientProfilePage() {
  const { clientId } = useParams<{ clientId: string }>()
  const { data, status, reload } = useAsync<ClientDetail>(() => api.client(clientId!), [clientId])

  return (
    <>
      <PageBar title="Client 360" meta={<Link className="link" to="/clients">← Back to clients</Link>} />
      <div className="page stack">
        {status === 'loading' && <PageState status="loading" />}
        {status === 'error' && <PageState status="error" onRetry={reload} />}
        {status === 'ready' && data && <Profile c={data} />}
      </div>
    </>
  )
}

function Profile({ c }: { c: ClientDetail }) {
  const segLabel = (c.segment as { label?: string }).label ?? 'Unsegmented'
  const portfolioSeries = c.transactions.map((t) => t.portfolio_value)
  const portfolioLabels = c.transactions.map((t) => t.month)
  const loginSeries = c.digital_behavior.map((b) => b.logins)
  const openSeries = c.digital_behavior.map((b) => b.email_opens)
  const portUnit = moneyUnit(c.portfolio_value)

  const timeline = [
    ...c.life_events_detail.map((e) => ({ date: e.date, kind: 'event' as const, text: `Life event: ${titleize(e.type)}` })),
    ...c.call_log.map((n) => ({ date: n.date, kind: 'call' as const, text: n.note })),
  ].sort((a, b) => (a.date < b.date ? 1 : -1))

  return (
    <motion.div
      className="stack"
      variants={staggerContainer}
      initial="hidden"
      animate="show"
    >
      <motion.div className="panel profile__header" variants={fadeRise}>
        <div>
          <div className="profile__name-row">
            <h1 className="profile__name">{c.name}</h1>
            {c.action && <span className={`badge badge--${c.action.action_type.toLowerCase()}`}>{c.action.action_type}</span>}
            <span className="chip">{segLabel}</span>
          </div>
          <p className="profile__meta mono">
            {c.client_id} · {c.email} · {c.account_tenure_years} yrs tenure · last contact {c.days_since_last_contact}d ago
          </p>
        </div>
        <div className="profile__value">
          <span className="kpi__value">
            <CountUp value={portUnit.value} decimals={portUnit.decimals} prefix={portUnit.prefix} suffix={portUnit.suffix} />
          </span>
          <span className={c.portfolio_change_pct >= 0 ? 'text-cool mono' : 'text-warm mono'}>
            {signedPct(c.portfolio_change_pct)} · 90d
          </span>
        </div>
      </motion.div>

      <div className="profile__grid">
        <div className="stack">
          <motion.div className="panel" variants={fadeRise}>
            <div className="panel__head"><span className="panel__title">Portfolio value</span>
              <span className="text-muted mono">transaction history · 12 mo</span>
            </div>
            <TrendChart
              values={portfolioSeries}
              labels={portfolioLabels}
              color={c.portfolio_change_pct >= 0 ? 'var(--chart-cool)' : 'var(--chart-warm)'}
              height={180}
            />
          </motion.div>

          <motion.div className="grid grid--2" variants={fadeRise}>
            <div className="panel">
              <span className="eyebrow">Logins · 12 wk</span>
              <Sparkline values={loginSeries} color="var(--cool-500)" height={44} />
              <p className="kpi__sub">{signedPct(c.login_frequency_change)} vs. baseline</p>
            </div>
            <div className="panel">
              <span className="eyebrow">Email opens · 12 wk</span>
              <Sparkline values={openSeries} color="var(--warm-500)" height={44} />
              <p className="kpi__sub">{signedPct(c.email_open_rate_change)} vs. baseline</p>
            </div>
          </motion.div>

          <motion.div className="panel" variants={fadeRise}>
            <div className="panel__head"><span className="panel__title">Relationship timeline</span></div>
            <motion.div
              className="timeline"
              initial="hidden"
              animate="show"
              variants={{ show: { transition: { staggerChildren: 0.05, delayChildren: 0.1 } } }}
            >
              {timeline.map((t, i) => (
                <motion.div
                  key={i}
                  className="timeline__item"
                  variants={{ hidden: { opacity: 0, x: -8 }, show: { opacity: 1, x: 0, transition: { duration: 0.3 } } }}
                >
                  <span className={`timeline__dot timeline__dot--${t.kind}`} />
                  <div>
                    <span className="timeline__date mono">{t.date}</span>
                    <p className="timeline__text">{t.text}</p>
                  </div>
                </motion.div>
              ))}
            </motion.div>
          </motion.div>
        </div>

        <div className="stack">
          <motion.div className="panel" variants={fadeRise}>
            <div className="panel__head"><span className="panel__title">Agent recommendation</span></div>
            {c.action && c.action.draft_message ? (
              <>
                <div className="profile__reco-head">
                  <div>
                    <p className="profile__headline">{c.action.headline}</p>
                    <p className="kpi__sub">{c.action.rationale}</p>
                  </div>
                  <div className="profile__conf">
                    <span className="eyebrow">CONFIDENCE</span>
                    <ConfidenceArc value={c.action.confidence} />
                  </div>
                </div>
                <div className="profile__draft">
                  <span className="eyebrow">Draft opener</span>
                  <p className="profile__draft-text">{c.action.draft_message}</p>
                </div>
                <span className="eyebrow" style={{ marginTop: 'var(--space-4)' }}>WHY NOW · agent trace</span>
                <ReasoningTrace steps={c.action.reasoning_trace} />
              </>
            ) : (
              <p className="state__text">
                This client scored {c.attrition_risk}% attrition / {c.upsell_ready}% upsell — below today's
                drafting threshold, so the agent hasn't composed an opener. The engines still track them.
              </p>
            )}
          </motion.div>

          <motion.div className="panel" variants={fadeRise}>
            <div className="panel__head"><span className="panel__title">Signals</span></div>
            <motion.div
              className="profile__signals"
              initial="hidden"
              animate="show"
              variants={{ show: { transition: { staggerChildren: 0.06, delayChildren: 0.1 } } }}
            >
              <Signal label="Attrition risk" value={`${c.attrition_risk}%`} tone="warm" />
              <Signal label="Upsell readiness" value={`${c.upsell_ready}%`} tone="cool" />
              <Signal label="Revenue impact" value={money(c.revenue_impact)} tone="cool" />
              <Signal label="90d withdrawals" value={money(c.withdrawals_last_90_days)} tone="warm" />
            </motion.div>
          </motion.div>

          <motion.div className="panel" variants={fadeRise}>
            <div className="panel__head">
              <span className="panel__title">Ask about this client</span>
              <span className="text-muted mono">grounded copilot</span>
            </div>
            <AssistantChat scopeClientId={c.client_id} scopeName={c.name.split(' ')[0]} compact />
          </motion.div>

          <motion.div className="panel" variants={fadeRise}>
            <div className="panel__head"><span className="panel__title">Market exposure</span></div>
            <div className="chip-row">
              {c.market_exposure.map((m) => (
                <span key={m} className="chip">{titleize(m)}</span>
              ))}
            </div>
          </motion.div>

          {c.lookalikes.length > 0 && (
            <motion.div className="panel" variants={fadeRise}>
              <div className="panel__head"><span className="panel__title">Look-alike clients</span></div>
              <div className="chip-row">
                {c.lookalikes.map((id) => (
                  <Link key={id} to={`/clients/${id}`} className="chip chip--cool">{id}</Link>
                ))}
              </div>
              <p className="kpi__sub" style={{ marginTop: 'var(--space-3)' }}>
                Nearest neighbours in behavioural feature space — what worked for them may work here.
              </p>
            </motion.div>
          )}
        </div>
      </div>
    </motion.div>
  )
}

function Signal({ label, value, tone }: { label: string; value: string; tone: 'warm' | 'cool' }) {
  return (
    <motion.div
      className="profile__signal"
      variants={{ hidden: { opacity: 0, y: 6 }, show: { opacity: 1, y: 0, transition: { duration: 0.3 } } }}
    >
      <span className="kpi__label">{label}</span>
      <span className={`mono profile__signal-val ${tone === 'warm' ? 'text-warm' : 'text-cool'}`}>{value}</span>
    </motion.div>
  )
}
