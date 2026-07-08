import { motion } from 'framer-motion'
import './EmptyState.css'

export default function EmptyState() {
  return (
    <div className="empty-state">
      <motion.div
        className="empty-state__icon"
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      >
        <svg width="56" height="56" viewBox="0 0 56 56" fill="none" aria-hidden="true">
          <rect x="10" y="12" width="5" height="32" rx="2.5" style={{ fill: 'var(--chart-track)' }} />
          <circle cx="12.5" cy="20" r="3.4" fill="var(--cool-500)" />
          <path d="M12.5 20 L12.5 44" style={{ stroke: 'var(--chart-tick)' }} strokeWidth="2" />
          <path d="M24 28 L46 28" style={{ stroke: 'var(--chart-tick)' }} strokeWidth="2" strokeLinecap="round" />
          <path d="M31 25 L26 30" stroke="var(--cool-500)" strokeWidth="2.2" strokeLinecap="round" />
          <path d="M26 25 L31 30" stroke="var(--cool-500)" strokeWidth="2.2" strokeLinecap="round" />
        </svg>
      </motion.div>
      <p className="empty-state__text">
        You're clear for today. New signals arrive overnight.
      </p>
    </div>
  )
}
