import { api } from '../api/client'
import { motion } from 'framer-motion'
import PageState from '../components/PageState'
import { PageBar } from '../layout/AppShell'
import { useAsync } from '../lib/useAsync'
import { fadeRise, staggerContainer } from '../lib/motion'
import { titleize } from '../lib/format'
import { MarketSignal } from '../types'
import './MarketPage.css'

export default function MarketPage() {
  const { data, status, reload } = useAsync<MarketSignal[]>(() => api.market(), [])

  return (
    <>
      <PageBar title="Market signals" meta="5th data source · sentiment feed" />
      <div className="page stack">
        {status === 'loading' && <PageState status="loading" />}
        {status === 'error' && <PageState status="error" onRetry={reload} />}
        {status === 'ready' && data && (
          <motion.div variants={staggerContainer} initial="hidden" animate="show">
            <motion.p className="segments__intro" variants={fadeRise}>
              The Market-Signal agent cross-references this feed against each client's exposures to frame
              timely, relevant outreach and portfolio nudges.
            </motion.p>
            <div className="market__list">
              {data.map((m, i) => (
                <motion.div key={i} className="panel market__row" variants={fadeRise}>
                  <div className="market__row-main">
                    <div className="market__sector">
                      <span className="market__date mono">{m.date}</span>
                      <h3>{titleize(m.sector)}</h3>
                    </div>
                    <p className="market__signal">{m.signal}</p>
                  </div>
                  <span className={`sentiment sentiment--${m.sentiment}`}>{m.sentiment}</span>
                </motion.div>
              ))}
            </div>
          </motion.div>
        )}
      </div>
    </>
  )
}
