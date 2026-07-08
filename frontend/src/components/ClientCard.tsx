import { AnimatePresence, motion } from 'framer-motion'
import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { NextBestAction } from '../types'
import ConfidenceArc from './ConfidenceArc'
import ReasoningTrace from './ReasoningTrace'
import Toast from './Toast'
import { CountUp } from '../lib/motion'
import './ClientCard.css'

interface ClientCardProps {
  action: NextBestAction
  isExpanded: boolean
  isAccepted: boolean
  isSkipped: boolean
  onExpand: () => void
  onAccept: () => void
  onSkip: () => void
  onPersist?: (clientId: string, action: 'accept' | 'skip' | 'edit', draftText?: string) => void
}

export default function ClientCard({
  action,
  isExpanded,
  isAccepted,
  isSkipped,
  onExpand,
  onAccept,
  onSkip,
  onPersist,
}: ClientCardProps) {
  const [draftText, setDraftText] = useState(action.draft_message)
  const [toastMsg, setToastMsg] = useState<string | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const leadingMetric =
    action.action_type === 'URGENT'
      ? { value: action.attrition_risk, label: 'attrition risk' }
      : action.action_type === 'OPPORTUNITY'
        ? { value: action.upsell_ready, label: 'upsell readiness' }
        : { value: Math.max(action.attrition_risk, action.upsell_ready), label: 'signal' }

  const metricBarColor =
    action.action_type === 'URGENT' ? 'var(--warm-500)' : 'var(--cool-500)'

  const handleAccept = (e: React.MouseEvent | React.KeyboardEvent) => {
    e.stopPropagation()
    onPersist?.(action.client_id, 'accept', draftText)
    onAccept()
    setToastMsg('Accepted')
    setTimeout(() => setToastMsg(null), 2500)
  }

  const handleEdit = (e: React.MouseEvent | React.KeyboardEvent) => {
    e.stopPropagation()
    if (!isExpanded) onExpand()
    setTimeout(() => textareaRef.current?.focus(), 180)
  }

  const handleSkip = (e: React.MouseEvent | React.KeyboardEvent) => {
    e.stopPropagation()
    onPersist?.(action.client_id, 'skip')
    onSkip()
    setToastMsg('Skipped')
    setTimeout(() => setToastMsg(null), 2500)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onExpand()
    }
  }

  const revenueStr =
    action.revenue_impact >= 1_000_000
      ? `$${(action.revenue_impact / 1_000_000).toFixed(1)}M upside`
      : action.revenue_impact > 0
        ? `$${(action.revenue_impact / 1_000).toFixed(0)}K upside`
        : null

  if (isAccepted) {
    return (
      <motion.div
        className="card card--accepted"
        initial={{ opacity: 1, scale: 0.99 }}
        animate={{ opacity: 0.7, scale: 1 }}
        transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="card__accepted-stamp">
          <span className="card__accepted-check" aria-hidden="true">✓</span>
          ACCEPTED · ready to send
        </div>
        <div className="card__name">{action.name}</div>
        <AnimatePresence>{toastMsg && <Toast message={toastMsg} />}</AnimatePresence>
      </motion.div>
    )
  }

  if (isSkipped) {
    return (
      <motion.div
        className="card card--skipped"
        initial={{ opacity: 1 }}
        animate={{ opacity: 0.45, y: 6 }}
        transition={{ duration: 0.3 }}
      >
        <div className="card__skipped-stamp">SKIPPED</div>
        <div className="card__name">{action.name}</div>
      </motion.div>
    )
  }

  return (
    <motion.div
      className={`card ${isExpanded ? 'card--expanded-state' : ''}`}
      onClick={onExpand}
      onKeyDown={handleKeyDown}
      role="button"
      tabIndex={0}
      aria-expanded={isExpanded}
    >
      <div className="card__header">
        <div className="card__name">{action.name}</div>
        <ActionBadge type={action.action_type} />
        <div className="card__metric">
          <span className="card__metric-value">
            <CountUp value={leadingMetric.value} suffix="%" />
          </span>
          <span className="card__metric-label">{leadingMetric.label}</span>
          <span className="card__metric-bar">
            <motion.span
              className="card__metric-bar-fill"
              initial={{ width: 0 }}
              animate={{ width: `${leadingMetric.value}%` }}
              transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1], delay: 0.4 }}
              style={{ background: metricBarColor }}
            />
          </span>
        </div>
      </div>

      <p className="card__headline">{action.headline}</p>
      <p className="card__rationale">{action.rationale}</p>

      {revenueStr && <span className="card__revenue-chip">{revenueStr}</span>}

      {action.draft_message && (
        <div className="card__draft-section">
          <span className="eyebrow">DRAFT</span>
          <textarea
            ref={textareaRef}
            className="card__draft-textarea"
            value={draftText}
            onChange={(e) => setDraftText(e.target.value)}
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => e.stopPropagation()}
            rows={3}
            aria-label={`Draft message for ${action.name}`}
          />
          <div className="card__actions">
            <button className="card__btn card__btn--accept" onClick={handleAccept}>
              Accept
            </button>
            <button className="card__btn card__btn--edit" onClick={handleEdit}>
              Edit
            </button>
            <button className="card__btn card__btn--skip" onClick={handleSkip}>
              Skip
            </button>
          </div>
        </div>
      )}

      <AnimatePresence>
        {isExpanded && (
          <motion.div
            className="card__expanded"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.28, ease: 'easeInOut' }}
          >
            <div className="card__expanded-inner">
              <div className="card__expanded-row">
                <div className="card__trace-section">
                  <span className="eyebrow">WHY NOW</span>
                  <ReasoningTrace steps={action.reasoning_trace} />
                </div>
                <div className="card__confidence-section">
                  <span className="eyebrow">CONFIDENCE</span>
                  <ConfidenceArc value={action.confidence} />
                </div>
              </div>

              <motion.div
                className="card__reasons"
                initial="hidden"
                animate="show"
                variants={{ show: { transition: { staggerChildren: 0.05, delayChildren: 0.2 } } }}
              >
                <span className="eyebrow">DRIVERS</span>
                <div className="card__reasons-list">
                  {action.reasons.map((r, i) => (
                    <motion.span
                      key={i}
                      className="card__reason-chip"
                      variants={{
                        hidden: { opacity: 0, y: 6 },
                        show: { opacity: 1, y: 0, transition: { duration: 0.3 } },
                      }}
                    >
                      {r}
                    </motion.span>
                  ))}
                </div>
              </motion.div>

              {(action.market_insight || action.portfolio_nudge || action.recommended_product) && (
                <div className="card__intel">
                  <span className="eyebrow">AGENT FINDINGS</span>
                  {action.market_insight && (
                    <p className="card__intel-line"><b>Market:</b> {action.market_insight}</p>
                  )}
                  {action.portfolio_nudge && (
                    <p className="card__intel-line"><b>Portfolio:</b> {action.portfolio_nudge}</p>
                  )}
                  {action.recommended_product && (
                    <p className="card__intel-line"><b>Product fit:</b> {action.recommended_product}</p>
                  )}
                </div>
              )}

              <div className="card__segment">
                <span className="eyebrow">SEGMENT</span>
                <span className="card__segment-label">{action.segment.label}</span>
              </div>

              <Link
                to={`/clients/${action.client_id}`}
                className="link card__link"
                onClick={(e) => e.stopPropagation()}
              >
                View full client 360 &rarr;
              </Link>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>{toastMsg && <Toast message={toastMsg} />}</AnimatePresence>
    </motion.div>
  )
}

function ActionBadge({ type }: { type: NextBestAction['action_type'] }) {
  const className = `badge badge--${type.toLowerCase()}`
  return <span className={className}>{type}</span>
}
