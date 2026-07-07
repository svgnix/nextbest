import { Link } from 'react-router-dom'
import { api } from '../api/client'
import BarList from '../components/charts/BarList'
import DonutChart from '../components/charts/DonutChart'
import PageState from '../components/PageState'
import { PageBar } from '../layout/AppShell'
import { useAsync } from '../lib/useAsync'
import { AgentMetrics, AgentRunRow, EvalReport, JudgeScore } from '../types'
import './EvalPage.css'

const FRAMING_COLORS: Record<string, string> = {
  're-engagement': 'var(--warm-500)',
  opportunity: 'var(--cool-500)',
  'check-in': 'var(--slate-500)',
}

interface Bundle {
  metrics: AgentMetrics
  runs: AgentRunRow[]
  report: EvalReport
}

export default function EvalPage() {
  const { data, status, reload } = useAsync<Bundle>(async () => {
    const [metrics, runs, report] = await Promise.all([
      api.agentMetrics(),
      api.agentRuns(),
      api.evalReport(),
    ])
    return { metrics, runs, report }
  }, [])

  return (
    <>
      <PageBar
        title="Agent evaluation & observability"
        meta={data ? `${data.metrics.runs} runs · ${data.metrics.mode ?? '—'} mode` : ''}
      />
      <div className="page stack">
        {status === 'loading' && <PageState status="loading" />}
        {status === 'error' && <PageState status="error" onRetry={reload} />}
        {status === 'ready' && data && (
          data.metrics.runs === 0 ? <Empty /> : <Content {...data} />
        )}
      </div>
    </>
  )
}

function Empty() {
  return (
    <div className="panel">
      <span className="eyebrow">No agent runs yet</span>
      <p className="kpi__sub" style={{ marginTop: 'var(--space-3)' }}>
        Score the book first: <span className="mono">python -m backend.run_pipeline</span>, then optionally{' '}
        <span className="mono">python -m backend.eval</span> to add LLM-as-judge quality scores.
      </p>
    </div>
  )
}

function Content({ metrics, runs, report }: Bundle) {
  const det = report.deterministic
  const judge = report.judge

  return (
    <>
      {/* ---- Observability ---- */}
      <div className="panel eval__section-head">
        <span className="eyebrow">Observability · runtime telemetry</span>
        <p className="kpi__sub">
          Every recommendation is one multi-agent run. These are the operational signals captured live
          from the LangGraph orchestrator — latency, token spend, and where time goes.
        </p>
      </div>

      <div className="grid grid--4">
        <Kpi label="Avg latency / run" value={ms(metrics.avg_latency_ms)} sub={`p95 ${ms(metrics.p95_latency_ms)}`} />
        <Kpi label="Tokens / run" value={num(metrics.tokens?.avg_per_run)} sub={`${num(metrics.tokens?.total)} total`} />
        <Kpi label="Critique pass rate" value={pct(metrics.critique_pass_rate)} tone="cool" sub={`${metrics.llm_calls_total ?? 0} LLM calls`} />
        <Kpi label="Avg redrafts" value={String(metrics.avg_redrafts ?? 0)} tone="warm" sub={`${metrics.metric_leaks_caught ?? 0} leaks caught`} />
      </div>

      <div className="grid grid--2">
        <div className="panel">
          <div className="panel__head"><span className="panel__title">Where time goes (avg ms / node)</span></div>
          <BarList
            items={(metrics.node_timings_avg ?? []).map((n) => ({
              label: n.label,
              value: n.value,
              display: ms(n.value),
              color: 'var(--cool-500)',
            }))}
          />
          <p className="kpi__sub" style={{ marginTop: 'var(--space-4)' }}>
            The draft and critique nodes dominate — that's the reflection loop doing its work.
          </p>
        </div>

        <div className="panel">
          <div className="panel__head"><span className="panel__title">Framing chosen by the orchestrator</span></div>
          <DonutChart
            slices={(metrics.framing_distribution ?? []).map((f) => ({
              label: f.label,
              value: f.count,
              color: FRAMING_COLORS[f.label] ?? 'var(--slate-500)',
            }))}
            centerLabel={String(metrics.runs)}
            centerSub="RUNS"
          />
        </div>
      </div>

      {/* ---- Evaluation ---- */}
      <div className="panel eval__section-head">
        <span className="eyebrow">Evaluation · output quality</span>
        <p className="kpi__sub">
          How good are the recommendations? Deterministic checks run every time; the LLM-as-judge scores
          add an independent read on draft quality when an API key is set.
          {report.source === 'live' && ' (Showing live deterministic metrics — run backend.eval for judge scores.)'}
        </p>
      </div>

      <div className="grid grid--4">
        <Kpi label="Draft coverage" value={pct(det.draft_coverage)} sub={`${det.drafted}/${det.top_n} clients`} />
        <Kpi label="Compliance (no leaks)" value={pct(1 - det.metric_leak_rate)} tone="cool" sub="metric-free drafts" />
        <Kpi label="Specialist coverage" value={pct(det.specialist_coverage)} sub="consulted agents that fired" />
        <Kpi label="Avg confidence" value={String(det.confidence.avg)} sub={`${det.confidence.min}–${det.confidence.max} range`} />
      </div>

      <div className="grid grid--2">
        <div className="panel">
          <div className="panel__head"><span className="panel__title">Confidence distribution</span></div>
          <BarList
            items={det.confidence.distribution.map((b) => ({
              label: b.label,
              value: b.count,
              display: String(b.count),
              color: 'var(--cool-600)',
            }))}
          />
        </div>
        <div className="panel">
          <div className="panel__head"><span className="panel__title">Reflection loop (redrafts)</span></div>
          <BarList
            items={(metrics.redraft_distribution ?? []).map((r) => ({
              label: r.label,
              value: r.count,
              display: String(r.count),
              color: 'var(--warm-500)',
            }))}
          />
          <p className="kpi__sub" style={{ marginTop: 'var(--space-4)' }}>
            A redraft means a draft failed the compliance/quality gate and the agent regenerated it.
          </p>
        </div>
      </div>

      {judge && judge.scored > 0 ? <Judge judge={judge} /> : <JudgeUnavailable />}

      {/* ---- Per-run telemetry ---- */}
      <div className="panel">
        <div className="panel__head"><span className="panel__title">Per-run telemetry</span></div>
        <table className="table">
          <thead>
            <tr>
              <th>Client</th>
              <th>Framing</th>
              <th className="num">Latency</th>
              <th className="num">Tokens</th>
              <th className="num">Redrafts</th>
              <th className="num">Words</th>
              <th>Gate</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.client_id}>
                <td><Link className="link" to={`/clients/${r.client_id}`}>#{r.priority_rank} {r.name}</Link></td>
                <td><span className="eval__tag" style={{ color: FRAMING_COLORS[r.framing] ?? 'var(--slate-500)' }}>{r.framing}</span></td>
                <td className="num">{ms(r.total_ms)}</td>
                <td className="num">{num(r.total_tokens)}</td>
                <td className="num">{r.redrafts}</td>
                <td className="num">{r.draft_word_count}</td>
                <td>
                  <span className={`eval__pill ${r.draft_passed ? 'eval__pill--pass' : 'eval__pill--fail'}`}>
                    {r.draft_passed ? 'passed' : 'failed'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

function Judge({ judge }: { judge: NonNullable<EvalReport['judge']> }) {
  const a = judge.averages
  return (
    <>
      <div className="grid grid--4">
        <Kpi label="Judge · overall" value={`${a.overall ?? 0}/5`} tone="cool" sub={`${judge.scored} drafts scored`} />
        <Kpi label="Personalization" value={`${a.personalization ?? 0}/5`} />
        <Kpi label="Actionability" value={`${a.actionability ?? 0}/5`} />
        <Kpi label="Judge compliance" value={pct(judge.compliant_rate)} sub="drafts flagged clean" />
      </div>

      <div className="panel">
        <div className="panel__head"><span className="panel__title">LLM-as-judge · per draft</span></div>
        <table className="table">
          <thead>
            <tr>
              <th>Client</th>
              <th className="num">Person.</th>
              <th className="num">Tone</th>
              <th className="num">Action.</th>
              <th className="num">Ground.</th>
              <th className="num">Overall</th>
              <th>Note</th>
            </tr>
          </thead>
          <tbody>
            {judge.per_client.map((p: JudgeScore) => (
              <tr key={p.client_id}>
                <td><Link className="link" to={`/clients/${p.client_id}`}>{p.name}</Link></td>
                <td className="num">{p.personalization}</td>
                <td className="num">{p.tone}</td>
                <td className="num">{p.actionability}</td>
                <td className="num">{p.groundedness}</td>
                <td className="num"><strong>{p.overall}</strong></td>
                <td className="eval__note">{p.comment}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

function JudgeUnavailable() {
  return (
    <div className="panel">
      <span className="eyebrow">LLM-as-judge not run</span>
      <p className="kpi__sub" style={{ marginTop: 'var(--space-3)' }}>
        Independent draft-quality scores appear here after you run{' '}
        <span className="mono">python -m backend.eval</span> with an API key configured. Without a key,
        only the deterministic metrics above are available.
      </p>
    </div>
  )
}

function Kpi({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: 'warm' | 'cool' }) {
  return (
    <div className="kpi">
      <span className="kpi__label">{label}</span>
      <span className={`kpi__value ${tone === 'warm' ? 'kpi__value--warm' : tone === 'cool' ? 'kpi__value--cool' : ''}`}>{value}</span>
      {sub && <span className="kpi__sub">{sub}</span>}
    </div>
  )
}

// -- formatters --------------------------------------------------------------
function ms(v?: number): string {
  if (!v) return '0ms'
  return v >= 1000 ? `${(v / 1000).toFixed(1)}s` : `${Math.round(v)}ms`
}
function num(v?: number): string {
  if (!v) return '0'
  return v >= 1000 ? `${(v / 1000).toFixed(1)}k` : String(Math.round(v))
}
function pct(v?: number): string {
  return `${Math.round((v ?? 0) * 100)}%`
}
