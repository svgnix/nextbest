import './TopBar.css'

interface TopBarProps {
  clientCount: number
}

export default function TopBar({ clientCount }: TopBarProps) {
  const today = new Date()
  const dateStr = today.toLocaleDateString('en-US', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  })

  return (
    <header className="topbar">
      <div className="topbar__wordmark">NEXTBEST</div>
      <div className="topbar__meta">
        {dateStr} · {clientCount} client{clientCount !== 1 ? 's' : ''} need you today
      </div>
    </header>
  )
}
