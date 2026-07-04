import { motion } from 'framer-motion'
import './LoadingState.css'

export default function LoadingState() {
  return (
    <div className="loading-state">
      <div className="loading-state__rail">
        {[0, 1, 2, 3, 4].map(i => (
          <motion.div
            key={i}
            className="loading-state__notch"
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.3 }}
            transition={{ delay: i * 0.06, duration: 0.3 }}
          />
        ))}
      </div>
      <div className="loading-state__cards">
        {[0, 1, 2, 3, 4].map(i => (
          <motion.div
            key={i}
            className="loading-state__card"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 + i * 0.06, duration: 0.3 }}
          />
        ))}
      </div>
    </div>
  )
}
