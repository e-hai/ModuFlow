import {
  StrategicInitiative,
  Product,
  WorkflowTemplate,
  WorkflowRun,
  ModuleInstance,
  CollaborationSession,
  SessionMessage,
  Artifact,
  Issue,
  ExecutiveCockpitResponse,
  ExecutiveDecisionItem,
  ExecutiveRiskItem,
  AgentSettings,
  ChangeReview,
  GateConfig,
  GateApplication,
  ProductProfile,
  ShadowStats,
  HotfixTasksStatus,
  HotfixFollowupTask,
  PortfolioWeeklyReport,
  ProjectDailyDigest
} from '../types';

const API_BASE = '/api/v1';

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });
  if (!res.ok) {
    let errorDetail = 'Request failed';
    try {
      const err = await res.json();
      errorDetail = err.detail || errorDetail;
    } catch (_) {}
    throw new Error(errorDetail);
  }
  return res.json();
}

export const api = {
  // Initiatives
  getInitiatives: () => fetchJSON<StrategicInitiative[]>('/initiatives'),
  createInitiative: (data: Partial<StrategicInitiative>) =>
    fetchJSON<StrategicInitiative>('/initiatives', { method: 'POST', body: JSON.stringify(data) }),
  updateInitiative: (id: string, data: Partial<StrategicInitiative>) =>
    fetchJSON<StrategicInitiative>(`/initiatives/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteInitiative: (id: string) =>
    fetchJSON<{ ok: boolean; message: string }>(`/initiatives/${id}`, { method: 'DELETE' }),

  // Products
  getProducts: (initiativeId?: string) =>
    fetchJSON<Product[]>(initiativeId ? `/products?initiative_id=${initiativeId}` : '/products'),
  createProduct: (data: Partial<Product>) =>
    fetchJSON<Product>('/products', { method: 'POST', body: JSON.stringify(data) }),

  // Templates
  getTemplates: () => fetchJSON<WorkflowTemplate[]>('/templates'),

  // Runs
  getRuns: (productId?: string) =>
    fetchJSON<WorkflowRun[]>(productId ? `/runs?product_id=${productId}` : '/runs'),
  getRun: (runId: string) => fetchJSON<WorkflowRun>(`/runs/${runId}`),
  createRun: (data: { product_id: string; template_id: string; name: string }) =>
    fetchJSON<WorkflowRun>('/runs', { method: 'POST', body: JSON.stringify(data) }),
  updateRun: (runId: string, updates: { name?: string; status?: string }) =>
    fetchJSON<WorkflowRun>(`/runs/${runId}`, { method: 'PATCH', body: JSON.stringify(updates) }),

  // Modules
  getModule: (moduleId: string) => fetchJSON<ModuleInstance>(`/modules/${moduleId}`),
  updateModulePhase: (moduleId: string, phase: string, artifactId?: string) =>
    fetchJSON<ModuleInstance>(`/modules/${moduleId}/phase`, {
      method: 'PATCH',
      body: JSON.stringify({ phase, artifact_id: artifactId }),
    }),

  // Sessions & Messages
  getModuleSession: (moduleId: string) => fetchJSON<CollaborationSession>(`/modules/${moduleId}/session`),
  sendMessage: (sessionId: string, message: Partial<SessionMessage>, triggerAgent = true) =>
    fetchJSON<SessionMessage[]>(`/sessions/${sessionId}/messages?trigger_agent=${triggerAgent}`, {
      method: 'POST',
      body: JSON.stringify(message),
    }),

  // Artifacts & Bundles
  getModuleArtifacts: (moduleId: string) => fetchJSON<Artifact[]>(`/modules/${moduleId}/artifacts`),
  getArtifact: (artifactId: string) => fetchJSON<Artifact>(`/artifacts/${artifactId}`),
  getArtifactPreviewUrl: (artifactId: string, path = '') =>
    `${API_BASE}/artifacts/${artifactId}/preview${path ? `/${path}` : ''}`,
  uploadModuleArtifact: async (moduleId: string, file: File, changeSummary?: string) => {
    const formData = new FormData();
    formData.append('file', file);
    if (changeSummary) {
      formData.append('change_summary', changeSummary);
    }
    const res = await fetch(`${API_BASE}/modules/${moduleId}/artifacts/upload`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      let errorDetail = 'Upload failed';
      try {
        const err = await res.json();
        errorDetail = err.detail || errorDetail;
      } catch (_) {}
      throw new Error(errorDetail);
    }
    return res.json() as Promise<{ artifact: Artifact; change_review: ChangeReview }>;
  },

  // Change Reviews & Unified Approvals
  getChangeReviews: (params?: { module_id?: string; run_id?: string; status?: string }) => {
    const query = new URLSearchParams(params as any).toString();
    return fetchJSON<ChangeReview[]>(`/change-reviews${query ? `?${query}` : ''}`);
  },
  getChangeReview: (reviewId: string) => fetchJSON<ChangeReview>(`/change-reviews/${reviewId}`),
  approveChangeReview: (reviewId: string, data?: { approver?: string; rejection_reason?: string }) =>
    fetchJSON<ChangeReview>(`/change-reviews/${reviewId}/approve`, {
      method: 'POST',
      body: JSON.stringify(data || { approver: '统一审批人' }),
    }),
  rejectChangeReview: (reviewId: string, data?: { approver?: string; rejection_reason?: string }) =>
    fetchJSON<ChangeReview>(`/change-reviews/${reviewId}/reject`, {
      method: 'POST',
      body: JSON.stringify(data || { approver: '统一审批人', rejection_reason: '未通过审核' }),
    }),

  // Downstream Upstream Acknowledgment
  ackUpstreamModule: (moduleId: string, upstreamCode?: string) =>
    fetchJSON<ModuleInstance>(`/modules/${moduleId}/ack-upstream`, {
      method: 'POST',
      body: JSON.stringify(upstreamCode ? { upstream_code: upstreamCode } : {}),
    }),

  // Issues
  getIssues: (params?: { run_id?: string; target_module_id?: string; status?: string }) => {
    const query = new URLSearchParams(params as any).toString();
    return fetchJSON<Issue[]>(`/issues${query ? `?${query}` : ''}`);
  },
  createIssue: (issue: Partial<Issue>) =>
    fetchJSON<Issue>('/issues', { method: 'POST', body: JSON.stringify(issue) }),
  updateIssue: (issueId: string, updates: Partial<Issue>) =>
    fetchJSON<Issue>(`/issues/${issueId}`, { method: 'PATCH', body: JSON.stringify(updates) }),

  // Executive Cockpit
  getCockpit: (initiativeId: string, period = 'lifetime') =>
    fetchJSON<ExecutiveCockpitResponse>(`/initiatives/${initiativeId}/cockpit?period=${period}`),
  actOnDecision: (initiativeId: string, decisionId: string, action: 'approve' | 'reject', operator = 'CEO') =>
    fetchJSON<ExecutiveDecisionItem>(`/initiatives/${initiativeId}/decisions/${decisionId}/action`, {
      method: 'POST',
      body: JSON.stringify({ action, operator }),
    }),
  resolveRisk: (initiativeId: string, riskId: string) =>
    fetchJSON<ExecutiveRiskItem>(`/initiatives/${initiativeId}/risks/${riskId}/resolve`, {
      method: 'POST',
    }),

  // Workspace Sync
  syncWorkspace: (initiativeId: string) =>
    fetchJSON<{ success: boolean; workspace_root: string; artifacts_synced: number }>(
      `/initiatives/${initiativeId}/sync-workspace`,
      { method: 'POST' }
    ),

  // Agent Settings
  getAgentSettings: () => fetchJSON<AgentSettings>('/settings/agent'),
  updateAgentSettings: (data: Partial<AgentSettings>) =>
    fetchJSON<AgentSettings>('/settings/agent', { method: 'PATCH', body: JSON.stringify(data) }),
  testAgentSettings: () =>
    fetchJSON<{ success: boolean; installed?: boolean; adapter_type: string; cli_command: string; events_count: number }>(
      '/settings/agent/test',
      { method: 'POST' }
    ),

  // Core Agent Roles
  getAgentRoles: () => fetchJSON<import('../types').AgentRoleDefinition[]>('/roles'),
  getAgentRole: (roleCode: string) => fetchJSON<import('../types').AgentRoleDefinition>(`/roles/${roleCode}`),
  getModuleRoles: (moduleId: string) =>
    fetchJSON<{ primary: import('../types').AgentRoleDefinition | null; collaborators: import('../types').AgentRoleDefinition[] }>(
      `/modules/${moduleId}/roles`
    ),

  // --- Human Gate System (Phases 2 & 4) ---
  getModuleGateConfig: (moduleId: string) =>
    fetchJSON<GateConfig>(`/modules/${moduleId}/gate-config`),
  getModuleGateApplication: (moduleId: string) =>
    fetchJSON<GateApplication>(`/modules/${moduleId}/gate-application`),
  submitGateApplication: (
    moduleId: string,
    data: {
      recommendation: string;
      evidence: any[];
      risk_assessment: string;
      decision_options?: string[];
      context?: Record<string, any>;
    }
  ) =>
    fetchJSON<GateApplication>(`/modules/${moduleId}/gate-application`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  reviewGateApplication: (
    gateId: string,
    data: { action: 'approve' | 'reject' | 'adjust'; comment?: string; reviewer_name?: string }
  ) =>
    fetchJSON<GateApplication>(`/gates/${gateId}/review`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  listPendingGatesForBatch: (params?: { level?: string; product_code?: string }) => {
    const query = new URLSearchParams(params as any).toString();
    return fetchJSON<GateApplication[]>(`/gates/pending-batch${query ? `?${query}` : ''}`);
  },
  evaluateGateByLead: (moduleId: string) =>
    fetchJSON<GateApplication>(`/modules/${moduleId}/lead/evaluate-gate`, {
      method: 'POST',
    }),

  // --- Lead Agent & Shadow Mode (Phase 4) ---
  getProductShadowStats: (productId: string) =>
    fetchJSON<ShadowStats>(`/products/${productId}/lead/shadow-stats`),
  toggleProductShadowMode: (productId: string, enabled: boolean) =>
    fetchJSON<{ ok: boolean; product_id: string; product_code: string; shadow_mode: boolean; message: string }>(
      `/products/${productId}/lead/shadow-mode`,
      {
        method: 'POST',
        headers: {
          'X-ModuFlow-Actor': 'human:sponsor',
        },
        body: JSON.stringify({ enabled }),
      }
    ),
  getProjectDailyDigest: (productId: string) =>
    fetchJSON<ProjectDailyDigest>(`/products/${productId}/lead/daily-digest`),

  // --- Project Profile & Guardrails (Phase 6) ---
  getProductProfile: (productId: string) =>
    fetchJSON<ProductProfile>(`/products/${productId}/profile`),

  // --- Hotfix 24h SLA & Portfolio Weekly Report (Phase 7) ---
  triggerHotfixRelease: (runId: string) =>
    fetchJSON<{ ok: boolean; run_id: string; tasks_created: number; sla_deadline: string }>(
      `/runs/${runId}/hotfix-release`,
      { method: 'POST' }
    ),
  getHotfixTasks: (runId: string) =>
    fetchJSON<HotfixTasksStatus>(`/runs/${runId}/hotfix-tasks`),
  completeHotfixTask: (taskId: string, notes?: string) =>
    fetchJSON<HotfixFollowupTask>(`/hotfix-tasks/${taskId}/complete`, {
      method: 'POST',
      body: JSON.stringify({ notes }),
    }),
  getPortfolioWeeklyReport: (initiativeId?: string) =>
    fetchJSON<PortfolioWeeklyReport>(
      initiativeId ? `/portfolio/weekly-report?initiative_id=${initiativeId}` : '/portfolio/weekly-report'
    ),
};
