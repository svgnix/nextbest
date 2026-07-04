import { api } from '../api/client'
import DispatchFeed from '../components/DispatchFeed'
import EmptyState from '../components/EmptyState'
import PageState from '../components/PageState'
import { PageBar } from '../layout/AppShell'
import { useAsync } from '../lib/useAsync'
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

  return (
    <>
      <PageBar
        title="Today's dispatch"
        meta={status === 'ready' ? `${WEEKDAY} · ${count} clients need you` : WEEKDAY}
      />
      <div className="page">
        {status === 'loading' && <PageState status="loading" />}
        {status === 'error' && <PageState status="error" onRetry={reload} />}
        {status === 'ready' && (count === 0 ? <EmptyState /> : <DispatchFeed actions={data!} onPersist={persist} />)}
      </div>
    </>
  )
}
