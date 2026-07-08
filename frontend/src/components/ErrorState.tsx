import { motion } from 'framer-motion'
import './ErrorState.css'

export default function ErrorState() {
  return (
    <div className="error-state">
      <motion.div
        className="error-state__icon"
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      >
        <svg width="44" height="44" viewBox="0 0 44 44" fill="none" aria-hidden="true">
          <circle cx="22" cy="22" r="17" stroke="var(--warm-500)" strokeWidth="2" fill="none" style={{ filter: 'drop-shadow(0 0 6px var(--warm-glow))' }} />
          <line x1="22" y1="13" x2="22" y2="24" stroke="var(--warm-500)" strokeWidth="2" strokeLinecap="round" />
          <circle cx="22" cy="29" r="1.8" fill="var(--warm-500)" />
        </svg>
      </motion.div>
      <p className="error-state__text">
        Something went wrong loading today's dispatch. Check that the pipeline has run and try refreshing.
      </p>
      <button className="error-state__btn" onClick={() => window.location.reload()}>
        Refresh
      </button>
    </div>
  )
}
