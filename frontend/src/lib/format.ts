export function money(n: number): string {
  if (Math.abs(n) >= 1_000_000_000) return `$${(n / 1_000_000_000).toFixed(2)}B`
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`
  if (Math.abs(n) >= 1_000) return `$${(n / 1_000).toFixed(0)}K`
  return `$${n.toFixed(0)}`
}

export function signedPct(n: number): string {
  return `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`
}

export function titleize(s: string): string {
  return s
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

export function actionColor(type: string): string {
  if (type === 'URGENT') return 'var(--warm-500)'
  if (type === 'OPPORTUNITY') return 'var(--cool-500)'
  return 'var(--slate-500)'
}

export function sentimentColor(s: string): string {
  if (s === 'bullish') return 'var(--bullish)'
  if (s === 'bearish') return 'var(--bearish)'
  return 'var(--neutral)'
}
