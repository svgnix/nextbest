import { motion, useReducedMotion } from 'framer-motion'
import './Charts.css'

export interface BarItem {
  label: string
  value: number
  display?: string
  color?: string
}

interface BarListProps {
  items: BarItem[]
  max?: number
}

/** Horizontal labelled bars — used for scores and small distributions. */
export default function BarList({ items, max }: BarListProps) {
  const reduce = useReducedMotion()
  const top = max ?? Math.max(...items.map((i) => i.value), 1)
  return (
    <div className="chart">
      {items.map((item, i) => {
        const pct = Math.max(2, (item.value / top) * 100)
        const color = item.color ?? 'var(--cool-500)'
        return (
          <div key={i} className="bar-row">
            <span className="bar-row__label" title={item.label}>{item.label}</span>
            <span className="bar-row__track">
              <motion.span
                className="bar-row__fill"
                initial={{ width: reduce ? `${pct}%` : 0 }}
                animate={{ width: `${pct}%` }}
                transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1], delay: 0.15 + i * 0.08 }}
                style={{ background: color }}
              />
            </span>
            <span className="bar-row__value">{item.display ?? item.value}</span>
          </div>
        )
      })}
    </div>
  )
}
