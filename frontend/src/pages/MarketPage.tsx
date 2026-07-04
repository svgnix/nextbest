import { api } from '../api/client'
import PageState from '../components/PageState'
import { PageBar } from '../layout/AppShell'
import { useAsync } from '../lib/useAsync'
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
          <>
            <p className="segments__intro">
              The Market-Signal agent cross-references this feed against each client's exposures to frame
              timely, relevant outreach and portfolio nudges.
            </p>
            <div className="market__list">
              {data.map((m, i) => (
                <div key={i} className="panel market__row">
                  <div className="market__row-main">
                    <div className="market__sector">
                      <span className="market__date mono">{m.date}</span>
                      <h3>{titleize(m.sector)}</h3>
                    </div>
                    <p className="market__signal">{m.signal}</p>
                  </div>
                  <span className={`sentiment sentiment--${m.sentiment}`}>{m.sentiment}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </>
  )
}
