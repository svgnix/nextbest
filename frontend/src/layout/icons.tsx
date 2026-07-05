interface IconProps {
  className?: string
}

const base = {
  width: 18,
  height: 18,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
}

export function DispatchIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className} aria-hidden="true">
      <path d="M4 6h16M4 12h10M4 18h7" />
      <circle cx="19" cy="15" r="3" />
    </svg>
  )
}

export function BookIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className} aria-hidden="true">
      <path d="M4 19V5a2 2 0 0 1 2-2h12v18H6a2 2 0 0 1-2-2Z" />
      <path d="M9 7h6M9 11h6" />
    </svg>
  )
}

export function ClientsIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className} aria-hidden="true">
      <circle cx="9" cy="8" r="3" />
      <path d="M3 20a6 6 0 0 1 12 0M16 3.5a3 3 0 0 1 0 9M21 20a6 6 0 0 0-4-5.6" />
    </svg>
  )
}

export function SegmentsIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className} aria-hidden="true">
      <path d="M12 12V3a9 9 0 1 0 9 9h-9Z" />
      <path d="M14 3.2A9 9 0 0 1 20.8 10H14V3.2Z" />
    </svg>
  )
}

export function CampaignsIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className} aria-hidden="true">
      <path d="m3 11 18-6-4 16-5-6-9-4Z" />
      <path d="m12 15 5-9" />
    </svg>
  )
}

export function AgentIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className} aria-hidden="true">
      <circle cx="12" cy="12" r="2.4" />
      <path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2" />
    </svg>
  )
}

export function MarketIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className} aria-hidden="true">
      <path d="M3 17l5-5 4 3 8-8" />
      <path d="M15 4h5v5" />
    </svg>
  )
}

export function ChatIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className} aria-hidden="true">
      <path d="M4 5h16v11H8l-4 4V5Z" />
      <path d="M8 9h8M8 12.5h5" />
    </svg>
  )
}
