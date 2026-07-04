import { motion } from 'framer-motion'
import { ReasoningStep } from '../types'
import './ReasoningTrace.css'

interface ReasoningTraceProps {
  steps: ReasoningStep[]
}

const AGENT_LABELS: Record<string, string> = {
  orchestrator: 'ORCHESTRATOR',
  segmentation: 'SEGMENTATION',
  propensity: 'PROPENSITY',
  market: 'MARKET',
  portfolio: 'PORTFOLIO',
  outreach: 'OUTREACH',
}

const AGENT_COLORS: Record<string, string> = {
  orchestrator: 'var(--ink-700)',
  segmentation: 'var(--cool-500)',
  propensity: 'var(--warm-500)',
  market: 'var(--cool-600)',
  portfolio: 'var(--cool-500)',
  outreach: 'var(--ink-800)',
}

export default function ReasoningTrace({ steps }: ReasoningTraceProps) {
  if (!steps.length) {
    return <p className="trace__empty">No reasoning trace — this client wasn't in the agent's top picks today.</p>
  }

  return (
    <div className="trace">
      {steps.map((step, i) => {
        const color = AGENT_COLORS[step.agent] ?? 'var(--cool-500)'
        return (
          <motion.div
            key={i}
            className="trace__step"
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.2, delay: i * 0.04 }}
          >
            <div className="trace__node" style={{ borderColor: color }} />
            {i < steps.length - 1 && <div className="trace__connector" />}
            <div className="trace__content">
              <span className="trace__agent" style={{ color }}>
                {AGENT_LABELS[step.agent] ?? step.agent.toUpperCase()}
              </span>
              <span className="trace__finding">{step.finding}</span>
            </div>
          </motion.div>
        )
      })}
    </div>
  )
}
