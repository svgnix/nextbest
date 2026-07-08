import { ReactNode, useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { api } from '../api/client'
import { Advisor } from '../types'
import ThemeToggle from '../components/ThemeToggle'
import {
  AgentIcon,
  BookIcon,
  CampaignsIcon,
  ChatIcon,
  ClientsIcon,
  DispatchIcon,
  EvalIcon,
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
  { to: '/assistant', label: 'Book Assistant', icon: ChatIcon },
  { to: '/agent', label: 'Agent Activity', icon: AgentIcon },
  { to: '/eval', label: 'Agent Eval', icon: EvalIcon },
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
      <nav className="nav" aria-label="Primary">
        <div className="nav__brand">
          <span className="nav__brand-mark" aria-hidden="true">
            <span className="nav__brand-mark-core" />
          </span>
          <div className="nav__brand-text">
            <span className="nav__brand-name">NextBest</span>
            <span className="nav__brand-sub">Advisor Intelligence</span>
          </div>
        </div>

        <div className="nav__edition" aria-label="Enterprise edition">
          <span className="nav__edition-dot" aria-hidden="true" />
          Enterprise Edition
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
              <span className="nav__label">{label}</span>
              {to === '/' && dispatchCount > 0 && (
                <span className="nav__link-badge">{dispatchCount}</span>
              )}
            </NavLink>
          ))}
        </div>

        <div className="nav__footer">
          <div className="nav__advisor">
            <span className="nav__avatar" aria-hidden="true">{initials}</span>
            <div className="nav__advisor-meta">
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
      <div className="pagebar__left">
        <span className="pagebar__title">{title}</span>
      </div>
      <div className="pagebar__right">
        {meta && <span className="pagebar__meta">{meta}</span>}
        <ThemeToggle />
      </div>
    </div>
  )
}
