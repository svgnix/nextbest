import { motion, useReducedMotion } from 'framer-motion'
import './ConfidenceArc.css'

interface ConfidenceArcProps {
  value: number
}

export default function ConfidenceArc({ value }: ConfidenceArcProps) {
  const shouldReduceMotion = useReducedMotion()
  const size = 80
  const strokeWidth = 6
  const radius = (size - strokeWidth) / 2
  const circumference = Math.PI * radius
  const arcLength = (value / 100) * circumference

  const strokeColor = value >= 70 ? 'var(--cool-500)' : value >= 40 ? 'var(--warm-500)' : 'var(--warm-600)'

  return (
    <div className="confidence-arc">
      <svg width={size} height={size / 2 + strokeWidth} viewBox={`0 0 ${size} ${size / 2 + strokeWidth}`}>
        <path
          d={describeArc(size / 2, size / 2, radius)}
          fill="none"
          stroke="var(--line)"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
        />
        <motion.path
          d={describeArc(size / 2, size / 2, radius)}
          fill="none"
          stroke={strokeColor}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: shouldReduceMotion ? circumference - arcLength : circumference }}
          animate={{ strokeDashoffset: circumference - arcLength }}
          transition={{ duration: 0.8, delay: 0.3, ease: 'easeOut' }}
        />
      </svg>
      <span className="confidence-arc__value">{value}</span>
    </div>
  )
}

function describeArc(cx: number, cy: number, r: number): string {
  return `M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`
}
