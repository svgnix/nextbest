export type ActionType = "URGENT" | "OPPORTUNITY" | "WATCHLIST";
export type ActionStatus = "pending" | "accepted" | "skipped" | "edited";
export type Sentiment = "bullish" | "neutral" | "bearish";

export interface ReasoningStep {
  agent: string;
  tool: string;
  finding: string;
  ts_ms: number;
}

export interface Segment {
  id: number;
  label: string;
}

export interface NextBestAction {
  client_id: string;
  name: string;
  advisor_id: string;
  action_type: ActionType;
  attrition_risk: number;
  upsell_ready: number;
  revenue_impact: number;
  revenue_impact_score: number;
  priority_rank: number;
  confidence: number;
  segment: Segment;
  headline: string;
  rationale: string;
  reasons: string[];
  draft_message: string;
  draft_passed_critique: boolean;
  reasoning_trace: ReasoningStep[];
  framing: string;
  portfolio_nudge: string | null;
  recommended_product: string | null;
  market_insight: string | null;
  action_status: ActionStatus;
}

export interface Advisor {
  advisor_id: string;
  name: string;
  title: string;
}

export interface ClientSummary {
  client_id: string;
  name: string;
  advisor_id: string;
  portfolio_value: number;
  portfolio_change_pct: number;
  days_since_last_contact: number;
  segment: Segment | Record<string, never>;
  attrition_risk: number;
  upsell_ready: number;
  action_type: ActionType;
}

export interface TransactionPoint {
  month: string;
  portfolio_value: number;
  net_flow: number;
}

export interface BehaviorPoint {
  week: string;
  logins: number;
  email_opens: number;
  sessions: number;
}

export interface CallLogEntry {
  date: string;
  note: string;
}

export interface LifeEventDetail {
  type: string;
  date: string;
}

export interface ClientDetail {
  client_id: string;
  name: string;
  advisor_id: string;
  email: string | null;
  portfolio_value: number;
  portfolio_change_pct: number;
  withdrawals_last_90_days: number;
  account_tenure_years: number;
  days_since_last_contact: number;
  login_frequency_change: number;
  email_open_rate_change: number;
  last_contact_note: string;
  life_events: string[];
  life_events_detail: LifeEventDetail[];
  market_exposure: string[];
  call_log: CallLogEntry[];
  transactions: TransactionPoint[];
  digital_behavior: BehaviorPoint[];
  segment: Segment | Record<string, never>;
  lookalikes: string[];
  attrition_risk: number;
  upsell_ready: number;
  revenue_impact: number;
  revenue_impact_score: number;
  action: NextBestAction | null;
}

export interface SegmentSummary {
  id: number;
  label: string;
  count: number;
  avg_attrition: number;
  avg_upsell: number;
  total_aum: number;
  playbook: string;
  member_ids: string[];
}

export interface BookAnalytics {
  total_clients: number;
  total_aum: number;
  revenue_at_risk: number;
  upsell_pipeline: number;
  urgent_count: number;
  opportunity_count: number;
  watchlist_count: number;
  avg_days_since_contact: number;
  segment_distribution: SegmentSummary[];
  top_at_risk: ClientSummary[];
  top_opportunities: ClientSummary[];
}

export interface MarketSignal {
  date: string;
  sector: string;
  sentiment: Sentiment;
  signal: string;
}

export interface MarketPoint {
  date: string;
  close: number;
}

export interface MarketSectorDetail {
  sector: string;
  label: string;
  ticker: string;
  date: string;
  sentiment: Sentiment;
  signal: string;
  change_pct: number;
  last_close: number;
  live: boolean;
  history: MarketPoint[];
}

export interface AgentActivityItem {
  client_id: string;
  client_name: string;
  priority_rank: number;
  agent: string;
  tool: string;
  finding: string;
  ts_ms: number;
}

export interface ChatCitation {
  client_id: string;
  name: string;
  doc_type: string;
  date: string;
  snippet: string;
}

export interface ChatResponse {
  answer: string;
  citations: ChatCitation[];
  grounded: boolean;
  mode: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  citations?: ChatCitation[];
  grounded?: boolean;
  pending?: boolean;
}

export interface LabeledCount {
  label: string;
  count: number;
}

export interface LabeledValue {
  label: string;
  value: number;
}

export interface AgentMetrics {
  runs: number;
  mode?: string;
  avg_latency_ms?: number;
  p50_latency_ms?: number;
  p95_latency_ms?: number;
  avg_redrafts?: number;
  critique_pass_rate?: number;
  metric_leaks_caught?: number;
  llm_calls_total?: number;
  tokens?: {
    total: number;
    prompt: number;
    completion: number;
    avg_per_run: number;
  };
  node_timings_avg?: LabeledValue[];
  framing_distribution?: LabeledCount[];
  redraft_distribution?: LabeledCount[];
}

export interface AgentRunRow {
  client_id: string;
  name: string;
  priority_rank: number;
  framing: string;
  total_ms: number;
  llm_calls: number;
  total_tokens: number;
  mode: string;
  redrafts: number;
  draft_passed: boolean;
  metric_leak_caught: boolean;
  draft_word_count: number;
}

export interface JudgeScore {
  client_id: string;
  name: string;
  framing: string;
  personalization: number;
  tone: number;
  actionability: number;
  groundedness: number;
  overall: number;
  compliant: boolean;
  comment: string;
}

export interface EvalReport {
  generated_at: string;
  mode: string;
  source?: string;
  deterministic: {
    top_n: number;
    runs: number;
    drafted: number;
    draft_coverage: number;
    critique_pass_rate: number;
    metric_leak_rate: number;
    avg_redrafts: number;
    specialist_coverage: number;
    framing_distribution: LabeledCount[];
    confidence: {
      avg: number;
      min: number;
      max: number;
      distribution: LabeledCount[];
    };
    latency_ms: { avg: number; p50: number; p95: number };
    tokens: { total: number; avg_per_run: number; prompt: number; completion: number };
  };
  judge: {
    scored: number;
    averages: Record<string, number>;
    compliant_rate: number;
    per_client: JudgeScore[];
  } | null;
}
