import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { useEffect, useMemo, useState } from 'react'
import { NextBestAction } from '../types'
import ClientCard from './ClientCard'
import './DispatchFeed.css'

interface DispatchFeedProps {
  actions: NextBestAction[]
  onPersist?: (clientId: string, action: 'accept' | 'skip' | 'edit', draftText?: string) => void
}

const dotColor = (t: NextBestAction['action_type']): string =>
  t === 'URGENT' ? 'var(--warm-500)' : t === 'OPPORTUNITY' ? 'var(--cool-500)' : 'var(--slate-500)'

/* Scroll-spy: the card whose top is nearest the page bar (and still within the
 * upper ~45% of the viewport) is the active one. Standard IntersectionObserver
 * pattern (CSS-Tricks / Bram.us) — no scroll-event math. The rail highlight
 * therefore tracks the feed as the RM scrolls. */
function useScrollSpy(ids: string[], offset: number): string | null {
  const [active, setActive] = useState<string | null>(null)
  const key = ids.join(',')
  useEffect(() => {
    if (!ids.length) return
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
        if (visible[0]) {
          setActive(visible[0].target.id.replace('card-', ''))
        }
      },
      { rootMargin: `-${offset}px 0px -55% 0px`, threshold: 0 },
    )
    ids.forEach((id) => {
      const el = document.getElementById(id)
      if (el) observer.observe(el)
    })
    return () => observer.disconnect()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, offset])
  return active
}

export default function DispatchFeed({ actions, onPersist }: DispatchFeedProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [skipped, setSkipped] = useState<Set<string>>(new Set())
  const [accepted, setAccepted] = useState<Set<string>>(new Set())

  const orderedActions = useMemo(() => {
    const active = actions.filter((a) => !skipped.has(a.client_id))
    const skippedActions = actions.filter((a) => skipped.has(a.client_id))
    return [...active, ...skippedActions]
  }, [actions, skipped])

  const cardIds = useMemo(() => orderedActions.map((a) => `card-${a.client_id}`), [orderedActions])
  const activeId = useScrollSpy(cardIds, 84)

  const handleExpand = (clientId: string) => {
    setExpandedId((prev) => (prev === clientId ? null : clientId))
  }

  const handleSelect = (clientId: string) => {
    setExpandedId(clientId)
    requestAnimationFrame(() => {
      const el = document.getElementById(`card-${clientId}`)
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  }

  const handleAccept = (clientId: string) => {
    setAccepted((prev) => new Set(prev).add(clientId))
    setExpandedId(null)
  }

  const handleSkip = (clientId: string) => {
    setSkipped((prev) => new Set(prev).add(clientId))
    setExpandedId(null)
  }

  return (
    <div className="dispatch">
      <PriorityRail
        actions={orderedActions}
        activeId={activeId}
        skipped={skipped}
        onSelect={handleSelect}
      />

      <div className="dispatch__feed">
        <AnimatePresence mode="popLayout">
          {orderedActions.map((action, i) => (
            <motion.div
              key={action.client_id}
              id={`card-${action.client_id}`}
              layout
              initial={{ opacity: 0, y: 16 }}
              animate={{
                opacity: skipped.has(action.client_id) ? 0.4 : 1,
                y: 0,
              }}
              exit={{ opacity: 0, y: -12 }}
              transition={{
                duration: 0.45,
                delay: i < 10 ? 0.5 + i * 0.07 : 0,
                ease: [0.16, 1, 0.3, 1],
                layout: { duration: 0.3 },
              }}
            >
              <ClientCard
                action={action}
                isExpanded={expandedId === action.client_id}
                isAccepted={accepted.has(action.client_id)}
                isSkipped={skipped.has(action.client_id)}
                onExpand={() => handleExpand(action.client_id)}
                onAccept={() => handleAccept(action.client_id)}
                onSkip={() => handleSkip(action.client_id)}
                onPersist={onPersist}
              />
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  )
}

interface RailProps {
  actions: NextBestAction[]
  activeId: string | null
  skipped: Set<string>
  onSelect: (clientId: string) => void
}

function PriorityRail({ actions, activeId, skipped, onSelect }: RailProps) {
  const reduce = useReducedMotion()

  // Keep the active notch scrolled into view inside the rail itself, so the
  // index follows the feed even when the morning is long. `nearest` only
  // scrolls when needed — it never fights the user.
  useEffect(() => {
    if (!activeId) return
    const node = document.querySelector<HTMLElement>(
      `.dispatch__rail [data-rail-id="${activeId}"]`,
    )
    node?.scrollIntoView({ block: 'nearest' })
  }, [activeId])

  return (
    <motion.aside
      className="dispatch__rail"
      aria-label="Priority index"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="rail__head">
        <span className="eyebrow rail__eyebrow">Priority</span>
        <span className="rail__count">{actions.length}</span>
      </div>

      <div className="rail__notches">
        {actions.map((action, i) => {
          const isActive = activeId === action.client_id
          const isSkipped = skipped.has(action.client_id)
          const leading = Math.max(action.attrition_risk, action.upsell_ready)
          const color = isSkipped ? 'var(--slate-500)' : dotColor(action.action_type)
          return (
            <button
              key={action.client_id}
              type="button"
              data-rail-id={action.client_id}
              className={`rail__notch ${isActive ? 'rail__notch--active' : ''} ${isSkipped ? 'rail__notch--skipped' : ''}`}
              onClick={() => onSelect(action.client_id)}
              aria-label={`Rank ${i + 1}: ${action.name} — ${action.action_type}`}
              aria-current={isActive ? 'true' : undefined}
              style={{ ['--notch-color' as string]: color }}
            >
              {isActive && (
                <motion.span
                  layoutId="rail-active-bar"
                  className="rail__active-bar"
                  transition={
                    reduce
                      ? { duration: 0 }
                      : { type: 'spring', stiffness: 420, damping: 36 }
                  }
                />
              )}
              <span className="rail__rank">{String(i + 1).padStart(2, '0')}</span>
              <span className="rail__dot" />
              <span className="rail__name">{action.name}</span>
              <span className="rail__metric">
                {leading}
                <span className="rail__metric-pct">%</span>
              </span>
            </button>
          )
        })}
      </div>
    </motion.aside>
  )
}
