import { motion, useReducedMotion } from 'framer-motion'
import './Charts.css'

interface SparklineProps {
  values: number[]
  color?: string
  height?: number
  fill?: boolean
}

export default function Sparkline({
  values,
  color = 'var(--chart-cool)',
  height = 40,
  fill = true,
}: SparklineProps) {
  const reduce = useReducedMotion()
  if (values.length < 2) return null
  const w = 100
  const max = Math.max(...values)
  const min = Math.min(...values)
  const span = max - min || 1

  const points = values.map((v, i) => {
    const x = (i / (values.length - 1)) * w
    const y = height - ((v - min) / span) * (height - 4) - 2
    return [x, y] as const
  })

  const line = points.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join(' ')
  const area = `0,${height} ${line} ${w},${height}`
  const [endX, endY] = points[points.length - 1]

  return (
    <div className="chart">
      <svg viewBox={`0 0 ${w} ${height}`} preserveAspectRatio="none" aria-hidden="true">
        {fill && (
          <motion.polygon
            points={area}
            fill={color}
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.14 }}
            transition={{ duration: 0.8, delay: 0.3 }}
          />
        )}
        <motion.polyline
          points={line}
          fill="none"
          stroke={color}
          strokeWidth={1.8}
          strokeLinejoin="round"
          strokeLinecap="round"
          initial={{ pathLength: reduce ? 1 : 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 1.1, ease: [0.16, 1, 0.3, 1] }}
        />
        <motion.circle
          cx={endX}
          cy={endY}
          r={2.4}
          fill={color}
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ delay: 1.0, type: 'spring', stiffness: 500, damping: 20 }}
        />
      </svg>
    </div>
  )
}
