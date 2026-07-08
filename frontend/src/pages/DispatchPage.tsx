import { api } from '../api/client'
import BookVitals from '../components/BookVitals'
import DispatchFeed from '../components/DispatchFeed'
import EmptyState from '../components/EmptyState'
import PageState from '../components/PageState'
import { PageBar } from '../layout/AppShell'
import { useAsync } from '../lib/useAsync'
import { CountUp } from '../lib/motion'
import { NextBestAction } from '../types'

const WEEKDAY = new Date().toLocaleDateString('en-GB', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
})

export default function DispatchPage() {
  const { data, status, reload } = useAsync<NextBestAction[]>(() => api.dispatch(), [])

  const persist = (clientId: string, action: 'accept' | 'skip' | 'edit', draftText?: string) => {
    api.recordAction(clientId, action, draftText ? { draft_text: draftText } : undefined).catch(() => {})
  }

  const count = data?.length ?? 0
  const meta = status === 'ready' ? (
    <>
      {WEEKDAY} · <CountUp value={count} /> clients need you
    </>
  ) : (
    WEEKDAY
  )

  return (
    <>
      <PageBar title="Today's dispatch" meta={meta} />
      <div className="page page--dispatch">
        {status === 'loading' && <PageState status="loading" />}
        {status === 'error' && <PageState status="error" onRetry={reload} />}
        {status === 'ready' && (
          count === 0 ? <EmptyState /> : (
            <>
              <BookVitals />
              <DispatchFeed actions={data!} onPersist={persist} />
            </>
          )
        )}
      </div>
    </>
  )
}
