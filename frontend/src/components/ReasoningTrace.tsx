import { motion } from 'framer-motion'
import { ReasoningStep } from '../types'
import './ReasoningTrace.css'

interface ReasoningTraceProps {
  steps: ReasoningStep[]
}

/* Tool-based mapping (the trace records the tool each agent step called).
 * Failed critique steps pulse warm to tie into the warm/cool signal system. */

type Tone = 'cool' | 'warm' | 'neutral'

const TOOL_META: Record<string, { label: string; tone: Tone }> = {
  get_client_segment: { label: 'SEGMENTATION', tone: 'cool' },
  compute_propensity: { label: 'PROPENSITY', tone: 'warm' },
  get_call_context: { label: 'CALL CONTEXT', tone: 'cool' },
  get_market_context: { label: 'MARKET', tone: 'cool' },
  get_market_sentiment: { label: 'MARKET', tone: 'cool' },
  get_product_catalog: { label: 'PRODUCTS', tone: 'cool' },
  recommend_rebalance: { label: 'PORTFOLIO', tone: 'cool' },
  draft_message: { label: 'DRAFT', tone: 'warm' },
  critique: { label: 'CRITIQUE', tone: 'warm' },
}

const TONE_COLOR: Record<Tone, string> = {
  cool: 'var(--cool-500)',
  warm: 'var(--warm-500)',
  neutral: 'var(--slate-500)',
}

function isFailed(step: ReasoningStep): boolean {
  return step.tool === 'critique' && step.finding.toLowerCase().includes('failed')
}

export default function ReasoningTrace({ steps }: ReasoningTraceProps) {
  if (!steps.length) {
    return <p className="trace__empty">No reasoning trace — this client wasn't in the agent's top picks today.</p>
  }

  return (
    <motion.div
      className="trace"
      initial="hidden"
      animate="show"
      variants={{ show: { transition: { staggerChildren: 0.08, delayChildren: 0.15 } } }}
    >
      {steps.map((step, i) => {
        const meta = TOOL_META[step.tool] ?? { label: step.tool.toUpperCase(), tone: 'cool' as Tone }
        const failed = isFailed(step)
        const color = TONE_COLOR[meta.tone]
        const isLast = i === steps.length - 1
        return (
          <motion.div
            key={i}
            className={`trace__step ${failed ? 'trace__step--failed' : ''}`}
            variants={{
              hidden: { opacity: 0, x: -10 },
              show: { opacity: 1, x: 0, transition: { duration: 0.35, ease: [0.16, 1, 0.3, 1] } },
            }}
          >
            <div className="trace__marker">
              <span className="trace__node" style={{ ['--node-color' as string]: color }} />
              {!isLast && <span className="trace__connector" style={{ ['--node-color' as string]: color }} />}
            </div>
            <div className="trace__content">
              <div className="trace__label-row">
                <span className="trace__agent" style={{ color }}>{meta.label}</span>
                {failed && <span className="trace__failed-tag">FAILED</span>}
              </div>
              <span className="trace__finding">{step.finding}</span>
            </div>
          </motion.div>
        )
      })}
    </motion.div>
  )
}
