import './Charts.css'

export interface DonutSlice {
  label: string
  value: number
  color: string
}

interface DonutChartProps {
  slices: DonutSlice[]
  size?: number
  centerLabel?: string
  centerSub?: string
}

export default function DonutChart({
  slices,
  size = 150,
  centerLabel,
  centerSub,
}: DonutChartProps) {
  const total = slices.reduce((s, d) => s + d.value, 0) || 1
  const r = size / 2
  const stroke = 22
  const radius = r - stroke / 2
  const circ = 2 * Math.PI * radius

  let offset = 0
  const arcs = slices.map((s) => {
    const frac = s.value / total
    const dash = frac * circ
    const arc = { ...s, dash, gap: circ - dash, offset }
    offset -= dash
    return arc
  })

  return (
    <div className="donut__wrap">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img">
        <g transform={`rotate(-90 ${r} ${r})`}>
          {arcs.map((a, i) => (
            <circle
              key={i}
              cx={r}
              cy={r}
              r={radius}
              fill="none"
              stroke={a.color}
              strokeWidth={stroke}
              strokeDasharray={`${a.dash} ${a.gap}`}
              strokeDashoffset={a.offset}
            />
          ))}
        </g>
        {centerLabel && (
          <text className="donut__center" x={r} y={r - 2} textAnchor="middle" fontSize={22} fontWeight={600}>
            {centerLabel}
          </text>
        )}
        {centerSub && (
          <text x={r} y={r + 16} textAnchor="middle" fontSize={9} fill="var(--text-400)" fontFamily="var(--font-mono)">
            {centerSub}
          </text>
        )}
      </svg>
      <div className="donut__legend">
        {slices.map((s, i) => (
          <div key={i} className="donut__legend-row">
            <span className="donut__swatch" style={{ background: s.color }} />
            <span>{s.label}</span>
            <span style={{ marginLeft: 'auto', color: 'var(--text-900)' }}>{s.value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
