export interface StrategicInitiative {
  id: string;
  name: string;
  description?: string;
  owner: string;
  budget: number;
  status: string;
  strategic_intent?: string;
  target_market?: string;
  business_model_hypothesis?: string;
  created_at: string;
  updated_at: string;
  product_count?: number;
}

export interface Product {
  id: string;
  initiative_id?: string;
  name: string;
  code: string;
  description?: string;
  created_at: string;
  updated_at: string;
  active_runs_count?: number;
}

export interface WorkflowTemplate {
  id: string;
  name: string;
  description?: string;
  modules_config: Array<{ code: string; name: string; required: boolean }>;
  default_dependencies: Array<{ from: string; to: string; gate?: string }>;
  created_at: string;
}

export interface ModuleInstance {
  id: string;
  run_id: string;
  module_code: string;
  name: string;
  order_index: number;
  phase: 'draft' | 'discussing' | 'reviewing' | 'baselined';
  is_unlocked: boolean;
  dependencies: string[];
  baseline_artifact_id?: string;
  open_issues_count?: number;
  blocking_issues_count?: number;
  artifacts_count?: number;
  created_at: string;
  updated_at: string;
}

export interface WorkflowRun {
  id: string;
  product_id: string;
  template_id: string;
  name: string;
  status: string;
  created_at: string;
  updated_at: string;
  modules: ModuleInstance[];
}

export interface SessionMessage {
  id: string;
  session_id: string;
  sender: string;
  sender_role: string;
  message_type: 'instruction' | 'feedback' | 'draft_artifact' | 'revised_artifact' | 'question' | 'answer' | 'issue' | 'approve' | 'reject';
  content: string;
  artifact_ref_id?: string;
  issue_ref_id?: string;
  metadata_json?: any;
  created_at: string;
}

export interface CollaborationSession {
  id: string;
  module_id: string;
  title: string;
  status: string;
  participants: Array<{ role: string; name: string }>;
  created_at: string;
  messages: SessionMessage[];
}

export interface Artifact {
  id: string;
  module_id: string;
  title: string;
  version: number;
  content: string;
  content_hash: string;
  is_baseline: boolean;
  created_at: string;
}

export interface Issue {
  id: string;
  title: string;
  source_module_id: string;
  target_module_id: string;
  reporter: string;
  reporter_role: string;
  category: 'bug' | 'question' | 'improvement' | 'task';
  severity: 'critical' | 'major' | 'minor' | 'trivial';
  priority: 'P0' | 'P1' | 'P2' | 'P3';
  status: 'open' | 'investigating' | 'fixing' | 'verifying' | 'closed';
  resolution?: string;
  description: {
    summary?: string;
    steps_to_reproduce?: string[];
    expected?: string;
    actual?: string;
    environment?: Record<string, string>;
  };
  related_artifact_id?: string;
  source_module_name?: string;
  target_module_name?: string;
  created_at: string;
  updated_at: string;
  closed_at?: string;
}

// --- Executive Business Cockpit Types ---
export interface FinancialMetrics {
  budget_total: number;
  committed_unpaid: number;
  actual_paid: number;
  available_budget: number;
  revenue_recognized: number;
  cash_collected: number;
  net_cash_flow: number;
  roi_percent?: number | null;
  target_breakeven_date?: string | null;
  forecast_breakeven_date?: string | null;
  burn_rate_monthly: number;
  currency: string;
  data_source: string;
}

export interface FocusAlert {
  id: string;
  title: string;
  summary: string;
  type: 'cac_spike' | 'breakeven_delayed' | 'pending_approval' | 'general' | string;
  severity: 'critical' | 'warning' | 'info';
  action_hint?: string;
}

export interface PortfolioProductItem {
  id: string;
  name: string;
  code: string;
  strategic_role: 'acquisition' | 'monetization' | 'retention' | 'validation' | 'infra' | string;
  stage: 'validating' | 'building' | 'growth' | 'profitable' | 'paused' | string;
  budget_allocated: number;
  actual_spent: number;
  revenue_contribution: number;
  kpi_name?: string;
  kpi_target?: number;
  kpi_actual?: number;
  kpi_unit?: string;
  kpi_completion_rate?: number;
  key_risk?: string;
  recommendation: string;
  active_runs_count: number;
}

export interface MarketingSubChannelItem {
  name: string;
  spend: number;
  acquired_users: number;
  cac: number;
  status: 'active' | 'planned' | 'testing' | string;
}

export interface MarketingCategoryItem {
  category_code: 'paid_acquisition' | 'partnerships' | 'organic_referral' | string;
  category_name: string;
  spend: number;
  acquired_users: number;
  user_share_percent: number;
  cac: number;
  conversion_rate: number;
  revenue_contribution: number;
  payback_days?: number | null;
  decision_recommendation: string;
  sub_channels: MarketingSubChannelItem[];
}

export interface MarketingCockpitData {
  total_spend: number;
  effective_new_users: number;
  blended_cac: number;
  categories: MarketingCategoryItem[];
}

export interface OperationsCockpitData {
  dau: number;
  mau: number;
  retention_1d: number;
  retention_7d: number;
  retention_30d: number;
  paid_users: number;
  arpu: number;
  arppu: number;
  ltv: number;
  ltv_cac_ratio: number;
  funnel: Array<{ stage: string; count: number; conversion_rate: number }>;
}

export interface ExecutiveRiskItem {
  id: string;
  rule_code: string;
  title: string;
  severity: 'critical' | 'major' | 'minor';
  description: string;
  product_code?: string;
  action_suggestion?: string;
  is_resolved: boolean;
  created_at: string;
}

export interface ExecutiveDecisionItem {
  id: string;
  title: string;
  status: 'proposed' | 'approved' | 'rejected' | 'executed';
  recommendation: {
    action_type?: string;
    from_product_code?: string;
    to_product_code?: string;
    amount?: number;
    currency?: string;
    summary?: string;
    [key: string]: any;
  };
  evidence: {
    source_refs?: Array<{ dataset: string; period: string }>;
    assumptions?: string[];
    data_coverage?: string;
    [key: string]: any;
  };
  impact_projection: {
    expected_cost_savings?: number;
    forecast_breakeven_variance_days?: number;
    confidence_interval?: string;
    identified_risks?: string[];
    [key: string]: any;
  };
  idempotency_key: string;
  approved_by?: string;
  approved_at?: string;
  created_at: string;
}

export interface ExecutiveCockpitResponse {
  initiative_id: string;
  initiative_name: string;
  owner: string;
  status: string;
  strategic_intent: string;
  target_market: string;
  business_model_hypothesis: string;
  period: 'MTD' | 'QTD' | 'YTD' | 'lifetime' | string;
  updated_at: string;
  data_integrity: string;
  financials: FinancialMetrics;
  focus_alerts: FocusAlert[];
  portfolio: PortfolioProductItem[];
  marketing: MarketingCockpitData;
  operations: OperationsCockpitData;
  risks: ExecutiveRiskItem[];
  decisions: ExecutiveDecisionItem[];
}

export interface AgentPresetItem {
  id: string;
  name: string;
  command: string;
  description: string;
  installed: boolean;
  path?: string;
}

export interface AgentSettings {
  adapter_type: 'cli' | 'simulator';
  cli_command: string;
  timeout: number;
  available_presets: AgentPresetItem[];
}
