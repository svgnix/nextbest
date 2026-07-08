import { motion, useReducedMotion } from 'framer-motion'
import './Charts.css'

interface TrendChartProps {
  values: number[]
  labels?: string[]
  color?: string
  height?: number
}

/** A labelled area+line chart for a value series (e.g. portfolio over time). */
export default function TrendChart({
  values,
  labels,
  color = 'var(--chart-cool)',
  height = 160,
}: TrendChartProps) {
  const reduce = useReducedMotion()
  if (values.length < 2) return null
  const w = 320
  const padL = 6
  const padR = 6
  const padB = 18
  const innerW = w - padL - padR
  const innerH = height - padB - 6

  const max = Math.max(...values)
  const min = Math.min(...values)
  const span = max - min || 1

  const pts = values.map((v, i) => {
    const x = padL + (i / (values.length - 1)) * innerW
    const y = 6 + innerH - ((v - min) / span) * innerH
    return [x, y] as const
  })

  const line = pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const area = `${padL},${6 + innerH} ${line} ${padL + innerW},${6 + innerH}`
  const [endX, endY] = pts[pts.length - 1]

  const gridLines = [0, 0.5, 1].map((f) => 6 + innerH * f)

  return (
    <div className="chart">
      <svg viewBox={`0 0 ${w} ${height}`} preserveAspectRatio="none">
        {gridLines.map((y, i) => (
          <motion.line
            key={i}
            className="chart__grid"
            x1={padL}
            y1={y}
            x2={padL + innerW}
            y2={y}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.1 + i * 0.06 }}
          />
        ))}
        <motion.polygon
          points={area}
          fill={color}
          initial={{ opacity: 0 }}
          animate={{ opacity: 0.16 }}
          transition={{ duration: 0.9, delay: 0.35 }}
        />
        <motion.polyline
          points={line}
          fill="none"
          stroke={color}
          strokeWidth={2.2}
          strokeLinejoin="round"
          strokeLinecap="round"
          initial={{ pathLength: reduce ? 1 : 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 1.3, ease: [0.16, 1, 0.3, 1] }}
        />
        <motion.circle
          cx={endX}
          cy={endY}
          r={3}
          fill={color}
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ delay: 1.2, type: 'spring', stiffness: 500, damping: 20 }}
        />
        {labels && (
          <>
            <text className="chart__axis-label" x={padL} y={height - 4}>
              {labels[0]}
            </text>
            <text className="chart__axis-label" x={padL + innerW} y={height - 4} textAnchor="end">
              {labels[labels.length - 1]}
            </text>
          </>
        )}
      </svg>
    </div>
  )
}
