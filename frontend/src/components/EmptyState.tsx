import './EmptyState.css'

export default function EmptyState() {
  return (
    <div className="empty-state">
      <div className="empty-state__icon">
        <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
          <rect x="8" y="10" width="4" height="28" rx="2" fill="var(--ink-700)" />
          <circle cx="10" cy="18" r="3" fill="var(--cool-500)" />
          <path d="M10 18 L10 38" stroke="var(--ink-700)" strokeWidth="2" />
          <path d="M20 24 L40 24" stroke="var(--line)" strokeWidth="2" strokeLinecap="round" />
          <path d="M26 22 L22 26" stroke="var(--cool-500)" strokeWidth="2" strokeLinecap="round" />
          <path d="M22 22 L26 26" stroke="var(--cool-500)" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </div>
      <p className="empty-state__text">
        You're clear for today. New signals arrive overnight.
      </p>
    </div>
  )
}
