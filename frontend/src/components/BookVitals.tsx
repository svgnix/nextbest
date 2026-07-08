import { motion, useReducedMotion, useScroll, useTransform } from 'framer-motion'
import { useRef } from 'react'
import { api } from '../api/client'
import Gauge from './charts/Gauge'
import { useAsync } from '../lib/useAsync'
import { CountUp, fadeRise, staggerContainer } from '../lib/motion'
import { BookAnalytics } from '../types'
import './BookVitals.css'

/* The command-center hero strip on the Morning Dispatch: four animated
 * instrument gauges summarising the book's vital signs. Pulls from
 * /api/book/analytics independently of the dispatch feed. */

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

export default function BookVitals() {
  const { data } = useAsync<BookAnalytics>(() => api.analytics(), [])
  const reduce = useReducedMotion()
  const ref = useRef<HTMLElement>(null)

  /* Gentle scroll parallax — the hero drifts up a few px as it exits the top,
   * reading as a layer behind the cards. Capped small; static under reduced
   * motion. No tilt, no canvas. */
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start start', 'end start'] })
  const y = useTransform(scrollYProgress, [0, 1], [0, -14])

  const a = data
  const totalAum = a?.total_aum ?? 1
  const totalClients = a?.total_clients ?? 1

  const revUnit = moneyUnit(a?.revenue_at_risk ?? 0)
  const upUnit = moneyUnit(a?.upsell_pipeline ?? 0)

  const gauges = [
    {
      key: 'rev',
      tone: 'warm' as const,
      fraction: a ? a.revenue_at_risk / totalAum : 0,
      label: 'Revenue at risk',
      center: a ? <CountUp value={revUnit.value} decimals={revUnit.decimals} prefix={revUnit.prefix} suffix={revUnit.suffix} /> : '—',
    },
    {
      key: 'urgent',
      tone: 'warm' as const,
      fraction: a ? a.urgent_count / totalClients : 0,
      label: 'Urgent clients',
      center: a ? <CountUp value={a.urgent_count} /> : '—',
    },
    {
      key: 'upsell',
      tone: 'cool' as const,
      fraction: a ? a.upsell_pipeline / totalAum : 0,
      label: 'Upsell pipeline',
      center: a ? <CountUp value={upUnit.value} decimals={upUnit.decimals} prefix={upUnit.prefix} suffix={upUnit.suffix} /> : '—',
    },
    {
      key: 'days',
      tone: 'neutral' as const,
      fraction: a ? Math.min(a.avg_days_since_contact / 120, 1) : 0,
      label: 'Avg days silent',
      center: a ? <CountUp value={a.avg_days_since_contact} suffix="d" /> : '—',
    },
  ]

  return (
    <motion.section
      ref={ref}
      className="book-vitals"
      variants={staggerContainer}
      initial="hidden"
      animate="show"
      style={{ y: reduce ? 0 : y }}
    >
      <div className="book-vitals__head">
        <span className="eyebrow book-vitals__eyebrow">Book vitals · today</span>
        <span className="book-vitals__live" aria-hidden="true">
          <span className="book-vitals__live-dot" />
          LIVE
        </span>
      </div>
      <div className="book-vitals__grid">
        {gauges.map((g) => (
          <motion.div key={g.key} className="book-vitals__cell" variants={fadeRise}>
            <Gauge
              fraction={g.fraction}
              tone={g.tone}
              label={g.label}
              center={g.center}
              active={!!a}
            />
          </motion.div>
        ))}
      </div>
    </motion.section>
  )
}
