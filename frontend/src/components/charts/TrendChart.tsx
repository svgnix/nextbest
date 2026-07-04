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

  const gridLines = [0, 0.5, 1].map((f) => 6 + innerH * f)

  return (
    <div className="chart">
      <svg viewBox={`0 0 ${w} ${height}`} preserveAspectRatio="none">
        {gridLines.map((y, i) => (
          <line key={i} className="chart__grid" x1={padL} y1={y} x2={padL + innerW} y2={y} />
        ))}
        <polygon points={area} fill={color} opacity={0.12} />
        <polyline points={line} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" />
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
