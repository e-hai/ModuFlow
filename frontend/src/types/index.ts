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
  platform?: string;
  shadow_mode?: boolean;
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

export interface AgentRoleDefinition {
  id: string;
  role_code: string;
  name: string;
  title: string;
  avatar_icon: string;
  color: string;
  responsibilities: string;
  system_persona: string;
  allowed_tools: string[];
  preferred_executor: string;
  created_at: string;
}

export interface StaleDetail {
  upstream_module_id: string;
  upstream_code: string;
  upstream_name: string;
  current_synced_version: number;
  latest_upstream_version: number;
  artifact_id?: string;
  artifact_type?: string;
  upstream_change_summary?: string;
  message: string;
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
  primary_role_code?: string;
  collaborator_role_codes?: string[];
  primary_role?: AgentRoleDefinition;
  collaborator_roles?: AgentRoleDefinition[];
  execution_mode?: 'agent_driven' | 'human_driven' | 'hybrid';
  synced_upstream_versions?: Record<string, number>;
  is_upstream_stale?: boolean;
  stale_details?: StaleDetail[];
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
  auto_advance?: boolean;
  created_at: string;
  updated_at: string;
  modules: ModuleInstance[];
}

export type OrchestrationStageState =
  | 'running'
  | 'paused'
  | 'revision_failed'
  | 'in_review'
  | 'dispute'
  | 'handoff_incomplete'
  | 'awaiting_human_gate'
  | 'gate_returned'
  | 'awaiting_human_confirm'
  | 'dispatch_failed'
  | 'ready';

export interface OrchestrationStage {
  module_id: string;
  module_code: string;
  name: string;
  execution_mode: string;
  state: OrchestrationStageState;
  detail: string;
  gate_id?: string | null;
}

export interface OrchestrationQueue {
  queued: number;
  running: number;
  runner_alive: boolean;
  current?: { task: string; worker?: string | null; started_at?: string | null } | null;
}

export interface RunOrchestrationStatus {
  run_id: string;
  found: boolean;
  auto_advance: boolean;
  orchestrator_enabled: boolean;
  run_block_reason?: string | null;
  current_stage?: OrchestrationStage | null;
  active_stages: OrchestrationStage[];
  queue?: OrchestrationQueue | null;
}

export interface SessionMessage {
  id: string;
  session_id: string;
  sender: string;
  sender_role: string;
  role_code?: string;
  message_type: 'instruction' | 'feedback' | 'draft_artifact' | 'revised_artifact' | 'question' | 'answer' | 'error' | 'issue' | 'approve' | 'reject' | 'review';
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
  artifact_type?: 'markdown' | 'html_bundle';
  content: string;
  storage_rel_path?: string;
  entry_file?: string;
  change_summary?: string;
  content_hash: string;
  is_baseline: boolean;
  created_at: string;
}

export interface ChangeReview {
  id: string;
  module_id: string;
  artifact_id: string;
  from_version: number;
  to_version: number;
  title: string;
  diff_summary: string;
  impact_analysis: string[];
  status: 'pending_approval' | 'approved' | 'rejected';
  approver?: string;
  rejection_reason?: string;
  created_at: string;
  approved_at?: string;
}

export interface Issue {
  id: string;
  title: string;
  source_module_id: string;
  target_module_id: string;
  reporter: string;
  reporter_role: string;
  category: 'bug' | 'question' | 'improvement' | 'task' | 'requirement_cr';
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
    unreasonable_point?: string;
    constraint?: string;
    suggested_change?: string;
    affected_modules?: string[];
    [key: string]: any;
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

export interface DecisionInboxItem {
  kind: 'dispute' | 'stuck' | 'handoff_gap';
  risk_id?: string | null;
  module_id: string;
  module_code: string;
  product_code: string;
  title: string;
  detail: string;
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
  install_command?: string;
  install_guide?: string;
}

export interface CliModelItem {
  id: string;
  label: string;
}

export interface CliModelList {
  command: string;
  models: CliModelItem[];
  error?: string | null;
}

export interface AgentSettings {
  adapter_type: 'cli' | 'simulator';
  cli_command: string;
  cli_model?: string | null;
  timeout: number;
  available_presets: AgentPresetItem[];
  is_current_installed?: boolean;
  any_installed?: boolean;
}

// --- Three-Tier Architecture, Gate Classification & Profile Types ---

export type GateLevel = 'green' | 'yellow' | 'red';

export interface GateConfig {
  name: string;
  level: GateLevel;
  approver: 'lead' | 'human' | 'qa';
  conditions: string[];
  auto_escalate_triggers: string[];
}

export interface GateApplication {
  id: string;
  module_id: string;
  run_id: string;
  product_code: string;
  module_code: string;
  gate_name: string;
  base_level: GateLevel;
  effective_level: GateLevel;
  is_escalated: boolean;
  escalation_reasons: string[];
  status: 'pending' | 'approved' | 'rejected' | 'adjusted' | string;
  recommendation: string;
  evidence: any;
  risk_assessment: string;
  decision_options: string[];
  submitted_by: string;
  submitted_at: string;
  reviewed_by?: string;
  reviewer_role?: string;
  reviewed_at?: string;
  review_comment?: string;
  decision_action?: string;
  lead_recommendation?: string;
  lead_rationale?: string;
  is_consistent?: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProductProfile {
  product_id: string;
  product_code: string;
  platform: 'ios' | 'android' | string;
  client_zero_inference: boolean;
  ruleset: string;
}

export interface ShadowStats {
  product_id: string;
  product_code?: string;
  shadow_mode_enabled: boolean;
  ready_to_disable?: boolean;
  readiness_reason?: string;
  total_evaluated: number;
  consistent_count: number;
  divergent_count: number;
  consistency_rate: number;
  recent_decisions: Array<{
    gate_id: string;
    gate_name?: string;
    lead_recommendation: string;
    human_action?: string;
    is_consistent: boolean;
    evaluated_at?: string;
  }>;
}

export interface HotfixFollowupTask {
  id: string;
  run_id: string;
  task_type: 'cr_patch' | 'postmortem' | 'prd_update';
  title: string;
  status: 'pending' | 'completed';
  sla_deadline: string;
  is_breached: boolean;
  created_at: string;
  completed_at?: string;
  completed_by?: string;
  notes?: string;
}

export interface HotfixTasksStatus {
  run_id: string;
  sla_deadline: string;
  is_breached: boolean;
  hours_remaining: number;
  all_completed: boolean;
  tasks: HotfixFollowupTask[];
}

export interface PortfolioWeeklyProductSummary {
  product_code: string;
  name: string;
  stage: string;
  spent: number;
  budget: number;
  burn_percent: number;
  status_color: 'green' | 'amber' | 'red';
  recommendation: string;
  kill_criteria_hit: boolean;
}

export interface PortfolioWeeklyReport {
  generated_at: string;
  total_products: number;
  healthy_count: number;
  risky_count: number;
  total_budget_usd: number;
  total_spent_usd: number;
  budget_utilization_rate: number;
  products_summary: PortfolioWeeklyProductSummary[];
  strategic_recommendations: string[];
  redline_notice: string;
}

export interface ProjectDailyDigest {
  product_code: string;
  date: string;
  author: string;
  active_run_id?: string;
  active_run_name?: string;
  template_id?: string;
  stage_progress: {
    baselined_modules: number;
    total_modules: number;
    completion_rate_percent: number;
  };
  budget_status: {
    spent: number;
    budget: number;
    burn_percent: number;
  };
  today_events: Array<{
    time: string;
    module_code: string;
    event_type: string;
    summary: string;
  }>;
  pending_items: Array<{
    item_type: string;
    title: string;
    urgency: string;
  }>;
  lead_assessment: string;
  shadow_mode_active?: boolean;
  shadow_consistency?: {
    consistency_rate: string;
    total_evaluated: number;
    ready_to_disable: boolean;
    readiness_reason: string;
  };
  collaboration?: {
    reviews_today: number;
    review_requests_changes_today: number;
    disputes_pending: number;
    dispute_stages: string[];
    carried_over_crs: number;
    handoff_gaps_open: number;
  };
}

export interface CodebaseTreeNode {
  name: string;
  type: 'file' | 'directory';
  path: string;
  language?: string;
  size?: number;
  children?: CodebaseTreeNode[];
}

export interface CodebaseSummaryAndTree {
  root_name: string;
  codebase_path: string;
  exists: boolean;
  total_files: number;
  total_lines: number;
  tree: CodebaseTreeNode[];
}

export interface CodebaseFileContent {
  path: string;
  name: string;
  size: number;
  language: string;
  content: string;
}

export interface OpenIdeResult {
  success: boolean;
  ide: string;
  app_name: string;
  opened_path: string;
  message: string;
}


