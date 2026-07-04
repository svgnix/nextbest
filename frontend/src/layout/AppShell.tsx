import { ReactNode, useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { api } from '../api/client'
import { Advisor } from '../types'
import {
  AgentIcon,
  BookIcon,
  CampaignsIcon,
  ClientsIcon,
  DispatchIcon,
  MarketIcon,
  SegmentsIcon,
} from './icons'
import './AppShell.css'

interface NavItem {
  to: string
  label: string
  icon: (p: { className?: string }) => ReactNode
  end?: boolean
}

const NAV: NavItem[] = [
  { to: '/', label: 'Morning Dispatch', icon: DispatchIcon, end: true },
  { to: '/book', label: 'Book Analytics', icon: BookIcon },
  { to: '/clients', label: 'Clients', icon: ClientsIcon },
  { to: '/segments', label: 'Segments', icon: SegmentsIcon },
  { to: '/market', label: 'Market Signals', icon: MarketIcon },
  { to: '/campaigns', label: 'Campaigns', icon: CampaignsIcon },
  { to: '/agent', label: 'Agent Activity', icon: AgentIcon },
]

export default function AppShell() {
  const [advisor, setAdvisor] = useState<Advisor | null>(null)
  const [dispatchCount, setDispatchCount] = useState<number>(0)

  useEffect(() => {
    api.advisors().then((a) => setAdvisor(a[0] ?? null)).catch(() => {})
    api.dispatch().then((d) => setDispatchCount(d.filter((x) => x.action_status === 'pending').length)).catch(() => {})
  }, [])

  const initials = advisor
    ? advisor.name.split(' ').map((n) => n[0]).slice(0, 2).join('')
    : 'NB'

  return (
    <div className="shell">
      <nav className="nav">
        <div className="nav__brand">
          <span className="nav__brand-mark" />
          <span className="nav__brand-name">NextBest</span>
        </div>

        <div className="nav__links">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => `nav__link ${isActive ? 'nav__link--active' : ''}`}
            >
              <Icon className="nav__icon" />
              <span>{label}</span>
              {to === '/' && dispatchCount > 0 && (
                <span className="nav__link-badge">{dispatchCount}</span>
              )}
            </NavLink>
          ))}
        </div>

        <div className="nav__footer">
          <div className="nav__advisor">
            <span className="nav__avatar">{initials}</span>
            <div>
              <div className="nav__advisor-name">{advisor?.name ?? 'Advisor'}</div>
              <div className="nav__advisor-title">{advisor?.title ?? 'Relationship Manager'}</div>
            </div>
          </div>
        </div>
      </nav>

      <main className="shell__main">
        <Outlet />
      </main>
    </div>
  )
}

export function PageBar({ title, meta }: { title: string; meta?: ReactNode }) {
  return (
    <div className="pagebar">
      <span className="pagebar__title">{title}</span>
      {meta && <span className="pagebar__meta">{meta}</span>}
    </div>
  )
}
