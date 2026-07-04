import { AnimatePresence, motion } from 'framer-motion'
import { useMemo, useState } from 'react'
import { NextBestAction } from '../types'
import ClientCard from './ClientCard'
import './DispatchFeed.css'

interface DispatchFeedProps {
  actions: NextBestAction[]
  onPersist?: (clientId: string, action: 'accept' | 'skip' | 'edit', draftText?: string) => void
}

export default function DispatchFeed({ actions, onPersist }: DispatchFeedProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [skipped, setSkipped] = useState<Set<string>>(new Set())
  const [accepted, setAccepted] = useState<Set<string>>(new Set())

  const orderedActions = useMemo(() => {
    const active = actions.filter(a => !skipped.has(a.client_id))
    const skippedActions = actions.filter(a => skipped.has(a.client_id))
    return [...active, ...skippedActions]
  }, [actions, skipped])

  const handleExpand = (clientId: string) => {
    setExpandedId(expandedId === clientId ? null : clientId)
  }

  const handleAccept = (clientId: string) => {
    setAccepted(prev => new Set(prev).add(clientId))
    setExpandedId(null)
  }

  const handleSkip = (clientId: string) => {
    setSkipped(prev => new Set(prev).add(clientId))
    setExpandedId(null)
  }

  return (
    <div className="dispatch">
      <motion.div
        className="dispatch__rail"
        initial={{ scaleY: 0 }}
        animate={{ scaleY: 1 }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
        style={{ transformOrigin: 'top' }}
      >
        <AnimatePresence mode="popLayout">
          {orderedActions.map((action, i) => (
            <RailNotch
              key={action.client_id}
              action={action}
              index={i}
              isSkipped={skipped.has(action.client_id)}
            />
          ))}
        </AnimatePresence>
      </motion.div>

      <div className="dispatch__feed">
        <AnimatePresence mode="popLayout">
          {orderedActions.map((action, i) => (
            <motion.div
              key={action.client_id}
              layout
              initial={{ opacity: 0, y: 12 }}
              animate={{
                opacity: skipped.has(action.client_id) ? 0.4 : 1,
                y: 0,
              }}
              exit={{ opacity: 0, y: -12 }}
              transition={{
                duration: 0.3,
                delay: i < 10 ? 0.5 + i * 0.06 : 0,
                ease: 'easeOut',
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

function RailNotch({
  action,
  index,
  isSkipped,
}: {
  action: NextBestAction
  index: number
  isSkipped: boolean
}) {
  const dotColor =
    action.action_type === 'URGENT'
      ? 'var(--warm-500)'
      : action.action_type === 'OPPORTUNITY'
        ? 'var(--cool-500)'
        : 'var(--slate-500)'

  const leadingScore = Math.max(action.attrition_risk, action.upsell_ready)
  const tickWidth = 4 + (leadingScore / 100) * 20

  return (
    <motion.div
      className={`rail__notch ${isSkipped ? 'rail__notch--skipped' : ''}`}
      layout
      initial={{ opacity: 0 }}
      animate={{ opacity: isSkipped ? 0.3 : 1 }}
      transition={{ delay: index < 10 ? 0.5 + index * 0.06 : 0, layout: { duration: 0.3 } }}
    >
      <span className="rail__rank">{String(index + 1).padStart(2, '0')}</span>
      <span className="rail__dot" style={{ background: dotColor }} />
      <span className="rail__tick" style={{ width: tickWidth, background: dotColor }} />
    </motion.div>
  )
}
