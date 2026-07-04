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

  return (
    <div className="chart">
      <svg viewBox={`0 0 ${w} ${height}`} preserveAspectRatio="none" aria-hidden="true">
        {fill && <polygon points={area} fill={color} opacity={0.1} />}
        <polyline points={line} fill="none" stroke={color} strokeWidth={1.6} strokeLinejoin="round" />
        <circle cx={points[points.length - 1][0]} cy={points[points.length - 1][1]} r={2} fill={color} />
      </svg>
    </div>
  )
}
