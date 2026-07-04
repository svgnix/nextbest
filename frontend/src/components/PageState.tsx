interface PageStateProps {
  status: 'loading' | 'error'
  onRetry?: () => void
}

export default function PageState({ status, onRetry }: PageStateProps) {
  if (status === 'loading') {
    return (
      <div className="state">
        <div className="spinner" />
        <p className="state__text">Loading the book…</p>
      </div>
    )
  }
  return (
    <div className="state">
      <p className="state__title">Couldn't reach the agent service</p>
      <p className="state__text">
        Make sure the API is running: <span className="mono">uvicorn backend.api.main:app --port 8000</span>
      </p>
      {onRetry && (
        <button className="card__btn card__btn--edit" onClick={onRetry}>Retry</button>
      )}
    </div>
  )
}
