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
  const top = max ?? Math.max(...items.map((i) => i.value), 1)
  return (
    <div className="chart">
      {items.map((item, i) => (
        <div key={i} className="bar-row">
          <span className="bar-row__label" title={item.label}>{item.label}</span>
          <span className="bar-row__track">
            <span
              className="bar-row__fill"
              style={{
                width: `${Math.max(2, (item.value / top) * 100)}%`,
                background: item.color ?? 'var(--cool-500)',
              }}
            />
          </span>
          <span className="bar-row__value">{item.display ?? item.value}</span>
        </div>
      ))}
    </div>
  )
}
