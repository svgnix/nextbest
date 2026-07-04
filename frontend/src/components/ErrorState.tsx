import './ErrorState.css'

export default function ErrorState() {
  return (
    <div className="error-state">
      <div className="error-state__icon">
        <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
          <circle cx="20" cy="20" r="16" stroke="var(--warm-500)" strokeWidth="2" fill="none" />
          <line x1="20" y1="12" x2="20" y2="22" stroke="var(--warm-500)" strokeWidth="2" strokeLinecap="round" />
          <circle cx="20" cy="27" r="1.5" fill="var(--warm-500)" />
        </svg>
      </div>
      <p className="error-state__text">
        Something went wrong loading today's dispatch. Check that the pipeline has run and try refreshing.
      </p>
      <button className="error-state__btn" onClick={() => window.location.reload()}>
        Refresh
      </button>
    </div>
  )
}
