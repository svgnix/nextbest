import { motion, useReducedMotion } from 'framer-motion'
import { useId } from 'react'
import { CountUp } from '../lib/motion'
import './ConfidenceArc.css'

interface ConfidenceArcProps {
  value: number
  size?: number
}

/* 270° instrument dial. The arc sweeps in on reveal along the warm→cool
 * gradient (low confidence warmer, high cooler), tick marks ring the dial,
 * and the center number counts up. No glow — reads as a clean instrument. */

function polar(cx: number, cy: number, r: number, deg: number): [number, number] {
  const rad = ((deg - 90) * Math.PI) / 180
  return [cx + r * Math.cos(rad), cy + r * Math.sin(rad)]
}

function arcPath(cx: number, cy: number, r: number, startDeg: number, endDeg: number): string {
  const [sx, sy] = polar(cx, cy, r, startDeg)
  const [ex, ey] = polar(cx, cy, r, endDeg)
  const large = endDeg - startDeg > 180 ? 1 : 0
  return `M ${sx} ${sy} A ${r} ${r} 0 ${large} 1 ${ex} ${ey}`
}

const START = 225
const SWEEP = 270

export default function ConfidenceArc({ value, size = 104 }: ConfidenceArcProps) {
  const reduce = useReducedMotion()
  const id = useId().replace(/:/g, '')
  const cx = size / 2
  const cy = size / 2
  const stroke = 8
  const r = (size - stroke) / 2 - 3
  const clamped = Math.max(0, Math.min(100, value))
  const endDeg = START + SWEEP * (clamped / 100)

  const ticks = 24
  const tickEls = Array.from({ length: ticks }, (_, i) => {
    const deg = START + (SWEEP * i) / (ticks - 1)
    const [x1, y1] = polar(cx, cy, r + stroke / 2 + 1.5, deg)
    const [x2, y2] = polar(cx, cy, r + stroke / 2 + 4.5, deg)
    return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} style={{ stroke: 'var(--chart-tick)' }} strokeWidth={1} />
  })

  return (
    <div className="confidence-arc" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <defs>
          <linearGradient id={`c-${id}`} x1="0%" y1="100%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#E8873A" />
            <stop offset="100%" stopColor="#12A594" />
          </linearGradient>
        </defs>
        {tickEls}
        <path
          d={arcPath(cx, cy, r, START, START + SWEEP)}
          fill="none"
          style={{ stroke: 'var(--chart-track)' }}
          strokeWidth={stroke}
          strokeLinecap="round"
        />
        <motion.path
          d={arcPath(cx, cy, r, START, endDeg)}
          fill="none"
          stroke={`url(#c-${id})`}
          strokeWidth={stroke}
          strokeLinecap="round"
          pathLength={1}
          strokeDasharray={1}
          initial={{ strokeDashoffset: reduce ? 0 : 1 }}
          animate={{ strokeDashoffset: 0 }}
          transition={{ duration: 1.0, ease: [0.16, 1, 0.3, 1], delay: 0.2 }}
        />
      </svg>
      <div className="confidence-arc__center">
        <span className="confidence-arc__value">
          <CountUp value={clamped} />
        </span>
        <span className="confidence-arc__label">confidence</span>
      </div>
    </div>
  )
}
