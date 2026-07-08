import { motion, useReducedMotion } from 'framer-motion'
import { useId } from 'react'

/* Animated 270° instrument gauge for the Book Vitals hero. The arc sweeps in
 * from 0 to `fraction` on reveal, tick marks ring the dial, and the stroke
 * carries a tone gradient. The center content is supplied by the caller
 * (typically a CountUp + label) so formatting stays flexible. */

export type GaugeTone = 'warm' | 'cool' | 'neutral'

interface GaugeProps {
  fraction: number
  tone: GaugeTone
  size?: number
  label: string
  center: React.ReactNode
  active?: boolean
}

const TONE_STOPS: Record<GaugeTone, { from: string; to: string; tick: string }> = {
  warm: { from: '#E8873A', to: '#C9522C', tick: 'rgba(232,135,58,0.35)' },
  cool: { from: '#12A594', to: '#0E7C6B', tick: 'rgba(18,165,148,0.35)' },
  neutral: { from: '#64707E', to: '#3A4658', tick: 'rgba(100,112,126,0.35)' },
}

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

export default function Gauge({ fraction, tone, size = 138, label, center, active = true }: GaugeProps) {
  const reduce = useReducedMotion()
  const id = useId().replace(/:/g, '')
  const stops = TONE_STOPS[tone]
  const cx = size / 2
  const cy = size / 2
  const stroke = 9
  const r = (size - stroke) / 2 - 4
  const clamped = Math.max(0, Math.min(1, fraction))
  const endDeg = START + SWEEP * clamped

  const ticks = 28
  const tickEls = Array.from({ length: ticks }, (_, i) => {
    const deg = START + (SWEEP * i) / (ticks - 1)
    const [x1, y1] = polar(cx, cy, r + stroke / 2 + 2, deg)
    const [x2, y2] = polar(cx, cy, r + stroke / 2 + 6, deg)
    return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke={stops.tick} strokeWidth={1.2} />
  })

  return (
    <div className="gauge" style={{ width: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <defs>
          <linearGradient id={`g-${id}`} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={stops.from} />
            <stop offset="100%" stopColor={stops.to} />
          </linearGradient>
        </defs>

        {tickEls}

        {/* Track */}
        <path
          d={arcPath(cx, cy, r, START, START + SWEEP)}
          fill="none"
          style={{ stroke: 'var(--chart-track)' }}
          strokeWidth={stroke}
          strokeLinecap="round"
        />
        {/* Value arc — sweeps in on reveal */}
        <motion.path
          d={arcPath(cx, cy, r, START, endDeg)}
          fill="none"
          stroke={`url(#g-${id})`}
          strokeWidth={stroke}
          strokeLinecap="round"
          pathLength={1}
          strokeDasharray={1}
          initial={{ strokeDashoffset: reduce ? 0 : 1 }}
          animate={{ strokeDashoffset: 0 }}
          transition={{ duration: 1.1, ease: [0.16, 1, 0.3, 1], delay: 0.15 }}
        />
      </svg>
      <div className="gauge__center">
        <div className="gauge__value">{center}</div>
        <div className="gauge__label">{label}</div>
      </div>
      {!active && <span className="gauge__sr">{label}</span>}
    </div>
  )
}
