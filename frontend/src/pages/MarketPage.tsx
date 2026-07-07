import { CSSProperties, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { api } from '../api/client'
import PageState from '../components/PageState'
import Sparkline from '../components/charts/Sparkline'
import TrendChart from '../components/charts/TrendChart'
import { PageBar } from '../layout/AppShell'
import { useAsync } from '../lib/useAsync'
import { signedPct } from '../lib/format'
import { MarketSectorDetail } from '../types'
import './MarketPage.css'

function sentimentVar(s: string): string {
  if (s === 'bullish') return 'var(--bullish)'
  if (s === 'bearish') return 'var(--bearish)'
  return 'var(--neutral)'
}

export default function MarketPage() {
  const { data, status, reload } = useAsync<MarketSectorDetail[]>(() => api.market(), [])
  const [expanded, setExpanded] = useState<string | null>(null)

  const summary = useMemo(() => {
    const s = { bullish: 0, bearish: 0, neutral: 0 }
    for (const d of data ?? []) s[d.sentiment] += 1
    return s
  }, [data])

  const asOf = data && data.length ? data.reduce((a, b) => (a.date > b.date ? a : b)).date : undefined
  const isLive = !!(data && data.length && data.every((d) => d.live))

  return (
    <>
      <PageBar
        title="Market signals"
        meta={asOf ? `${isLive ? 'Live ETF proxies' : 'Sample feed'} · as of ${asOf}` : '5th data source · sentiment feed'}
      />
      <div className="page stack">
        {status === 'loading' && <PageState status="loading" />}
        {status === 'error' && <PageState status="error" onRetry={reload} />}
        {status === 'ready' && data && (
          <>
            <div className="market__head">
              <p className="segments__intro">
                The Market-Signal agent cross-references this feed against each client's exposures to
                frame timely outreach and portfolio nudges. {isLive
                  ? 'Prices are pulled live from real, liquid ETF proxies for each sector.'
                  : 'Live prices are temporarily unavailable — showing a representative sample feed.'}
              </p>
              <div className="market__summary">
                <SummaryPill label="Bullish" count={summary.bullish} tone="bullish" />
                <SummaryPill label="Neutral" count={summary.neutral} tone="neutral" />
                <SummaryPill label="Bearish" count={summary.bearish} tone="bearish" />
              </div>
            </div>

            <div className="market__grid">
              {data.map((m) => (
                <SectorCard
                  key={m.sector}
                  m={m}
                  isOpen={expanded === m.sector}
                  onToggle={() => setExpanded(expanded === m.sector ? null : m.sector)}
                />
              ))}
            </div>
          </>
        )}
      </div>
    </>
  )
}

function SummaryPill({ label, count, tone }: { label: string; count: number; tone: string }) {
  return (
    <div className="market__summary-pill" style={{ '--tone': sentimentVar(tone) } as CSSProperties}>
      <span className="market__summary-count">{count}</span>
      <span className="market__summary-label">{label}</span>
    </div>
  )
}

function SectorCard({
  m,
  isOpen,
  onToggle,
}: {
  m: MarketSectorDetail
  isOpen: boolean
  onToggle: () => void
}) {
  const color = sentimentVar(m.sentiment)
  const closes = m.history.map((h) => h.close)
  const hasHistory = closes.length >= 2
  const labels = hasHistory ? [m.history[0].date, m.history[m.history.length - 1].date] : undefined
  const rangeLow = hasHistory ? Math.min(...closes) : 0
  const rangeHigh = hasHistory ? Math.max(...closes) : 0

  return (
    <div
      className={`panel market__card ${isOpen ? 'market__card--open' : ''}`}
      style={{ '--accent': color } as CSSProperties}
    >
      <button className="market__card-head" onClick={onToggle} aria-expanded={isOpen}>
        <div className="market__card-id">
          <div className="market__card-title">
            <h3>{m.label}</h3>
            {m.ticker && <span className="market__ticker mono">{m.ticker}</span>}
          </div>
          <span className={`sentiment sentiment--${m.sentiment}`}>{m.sentiment}</span>
        </div>

        <div className="market__card-metric">
          {hasHistory && (
            <div className="market__spark">
              <Sparkline values={closes} color={color} height={40} />
            </div>
          )}
          <span className="market__change mono" style={{ color }}>
            {signedPct(m.change_pct)}
          </span>
          <span className={`market__chevron ${isOpen ? 'market__chevron--open' : ''}`} aria-hidden>›</span>
        </div>
      </button>

      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            className="market__card-body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.28, ease: 'easeOut' }}
          >
            <div className="market__card-body-inner">
              {hasHistory ? (
                <TrendChart values={closes} labels={labels} color={color} height={180} />
              ) : (
                <p className="market__signal">No price history available for this sector.</p>
              )}

              <p className="market__signal">{m.signal}</p>

              <div className="market__stats">
                <Stat label="Last close" value={m.last_close ? `$${m.last_close.toFixed(2)}` : '—'} />
                <Stat label="90-day change" value={signedPct(m.change_pct)} color={color} />
                <Stat label="Range (low–high)" value={hasHistory ? `$${rangeLow.toFixed(0)}–$${rangeHigh.toFixed(0)}` : '—'} />
                <Stat label="Data points" value={`${closes.length}`} />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="market__stat">
      <span className="market__stat-label">{label}</span>
      <span className="market__stat-value mono" style={color ? { color } : undefined}>{value}</span>
    </div>
  )
}
