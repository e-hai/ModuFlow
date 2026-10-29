import React, { useState, useEffect } from 'react';
import {
  ShieldAlert,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  HelpCircle,
  FileCheck2,
  TrendingDown,
  ArrowRight,
  Database,
  Lock,
  UserCheck,
  Clock,
  Sparkles,
  Bot,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import { DecisionInboxItem, ExecutiveDecisionItem, ExecutiveRiskItem, GateApplication, Product, ShadowStats } from '../../types';
import { api } from '../../services/api';
import { GateBadge } from '../gate/GateBadge';
import { leadActionLabel, plainLeadRationale, stageDecision, stageName, withoutStageNumber } from '../gate/gateCopy';
import { GateApplicationModal } from '../gate/GateApplicationModal';

interface ProductGroup<T> {
  key: string;
  code: string;
  name: string;
  items: T[];
}

function groupByProduct<T>(
  items: T[],
  codeOf: (item: T) => string | undefined | null,
  products: Product[],
): ProductGroup<T>[] {
  const nameByCode = new Map(products.map((product) => [product.code, product.name]));
  const order = new Map(products.map((product, index) => [product.code, index]));
  const buckets = new Map<string, T[]>();
  for (const item of items) {
    const code = (codeOf(item) || '').trim();
    const key = code || '__initiative__';
    const list = buckets.get(key);
    if (list) list.push(item);
    else buckets.set(key, [item]);
  }
  return [...buckets.entries()]
    .map(([key, groupItems]) => ({
      key,
      code: key === '__initiative__' ? '' : key,
      name: key === '__initiative__' ? '工程级' : (nameByCode.get(key) || key),
      items: groupItems,
    }))
    .sort((a, b) => {
      const rank = (group: ProductGroup<T>) => {
        if (!group.code) return 2000;
        return order.get(group.code) ?? 1000;
      };
      const diff = rank(a) - rank(b);
      if (diff !== 0) return diff;
      return a.code.localeCompare(b.code);
    });
}

function ProductGroupLabel({ code, name, count }: { code: string; name: string; count: number }) {
  return (
    <div className="flex items-center justify-between gap-3 px-1">
      <div className="flex items-center gap-2 min-w-0">
        <span className="font-mono text-[11px] font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-800 border border-slate-200 shrink-0">
          {code || '工程级'}
        </span>
        {code && name !== code && (
          <span className="text-xs font-semibold text-slate-700 truncate">{name}</span>
        )}
      </div>
      <span className="text-[11px] font-mono text-slate-400 shrink-0">{count} 项</span>
    </div>
  );
}

interface DecisionCenterTabProps {
  initiativeId: string;
  risks: ExecutiveRiskItem[];
  decisions: ExecutiveDecisionItem[];
  onDecisionUpdated: () => void;
}

export const DecisionCenterTab: React.FC<DecisionCenterTabProps> = ({
  initiativeId,
  risks,
  decisions,
  onDecisionUpdated,
}) => {
  const [actingId, setActingId] = useState<string | null>(null);
  const [resolvingRiskId, setResolvingRiskId] = useState<string | null>(null);
  const [showResolvedRisks, setShowResolvedRisks] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [pendingGates, setPendingGates] = useState<GateApplication[]>([]);
  const [selectedGateForReview, setSelectedGateForReview] = useState<GateApplication | null>(null);
  const [shadowReady, setShadowReady] = useState<Array<{ product: Product; stats: ShadowStats }>>([]);
  const [disablingShadowId, setDisablingShadowId] = useState<string | null>(null);
  const [scopeCodes, setScopeCodes] = useState<string[] | null>(null);
  const [matrixProducts, setMatrixProducts] = useState<Product[]>([]);
  const [inbox, setInbox] = useState<DecisionInboxItem[]>([]);
  const [inboxBusy, setInboxBusy] = useState<string | null>(null);

  const activeRisks = risks.filter((r) => !r.is_resolved);
  const resolvedRisks = risks.filter((r) => r.is_resolved);
  const visibleGates = scopeCodes
    ? pendingGates.filter((gate) => scopeCodes.includes(gate.product_code))
    : pendingGates;
  const operationalRisks = activeRisks.filter(
    (risk) => !risk.rule_code.startsWith('GATE_RED_') && !risk.rule_code.startsWith('COMPLIANCE_G5_')
  );

  const formatRiskTitle = (title: string, isResolved: boolean): string => {
    let res = title
      .replace(/🔴\s*红级关口待批:\s*\[G4 提审门禁\]/g, '🔴 待您亲自把关：应用商店提审发布')
      .replace(/🔴\s*红级关口待批:\s*\[prd_linter 规格门禁\]/g, '🔴 待您亲自把关：产品需求规格审核 (PRD)')
      .replace(/🔴\s*红级关口待批:\s*\[([^\]]+)\]/g, '🔴 待您亲自把关：$1');

    if (isResolved) {
      res = res.replace(/^[🔴🚨]\s*待您亲自把关：?/, '✅ 已确认放行：');
      res = res.replace(/^🚨\s*越权拦截：?/, '✅ 已处置拦截：');
      res = res.replace(/^🚨\s*/, '✅ 已处置：');
      if (!res.startsWith('✅')) {
        res = `✅ 已处置：${res}`;
      }
    }
    return res;
  };

  const formatRuleCode = (code: string): string => {
    if (code.startsWith('GATE_RED_') || code.startsWith('COMPLIANCE_G5_')) {
      const mod = code.replace('GATE_RED_', '').replace('COMPLIANCE_G5_', '');
      return stageDecision(mod);
    }
    if (code.startsWith('ORCH_STUCK_')) {
      return `${stageName(code.replace('ORCH_STUCK_', ''))}还不能往下走`;
    }
    if (code.startsWith('ORCH_DISPUTE_')) {
      return `${stageName(code.replace('ORCH_DISPUTE_', ''))}的评审意见还没定`;
    }
    if (code.includes('SECURITY_VIOLATION')) {
      return '安全写保护拦截';
    }
    if (code.includes('COMPLIANCE')) {
      return '合规风控拦截';
    }
    if (code.includes('BUDGET')) {
      return '财务预算超支';
    }
    return code;
  };

  const formatRiskDescription = (desc: string): string => {
    return desc
      .replace(/AI 主管研判建议/g, '项目总控建议')
      .replace(/申请 G4 提审发布审批！?/g, '申请商店提审发布。')
      .replace(/G4 提审门禁/g, '提交商店');
  };

  const formatRiskSuggestion = (suggestion: string | undefined, isResolved: boolean): string => {
    if (isResolved) {
      if (!suggestion || suggestion.includes('点击下方') || suggestion.includes('拍板') || suggestion.includes('审查拍板')) {
        return '已由负责人审核确认放行，流程已推进至下一阶段。';
      }
      return suggestion;
    }
    if (suggestion) {
      return suggestion
        .replace(/请点击下方「查看详情并拍板」[，,]?/g, '')
        .replace(/请人类负责人即时前往关口审批中心进行审查拍板 \(通过\/打回\/调整\)。?/g, '请核对合规审查材料与应急回滚预案后确认放行。')
        .trim();
    }
    return '请核对相关材料后确认放行。';
  };

  useEffect(() => {
    loadPendingGates();
    loadShadowReadiness();
    loadInbox();
  }, [initiativeId]);

  const loadShadowReadiness = async () => {
    try {
      const products = await api.getProducts(initiativeId);
      setMatrixProducts(products);
      setScopeCodes(products.map((product) => product.code));
      const candidates = products.filter((p) => p.shadow_mode !== false);
      const results = await Promise.all(
        candidates.map(async (product) => ({ product, stats: await api.getProductShadowStats(product.id) }))
      );
      setShadowReady(results.filter((r) => r.stats.ready_to_disable));
    } catch (e) {
      console.error('Failed to load shadow readiness:', e);
    }
  };

  const handleDisableShadow = async (productId: string) => {
    try {
      setDisablingShadowId(productId);
      setErrorMsg(null);
      await api.toggleProductShadowMode(productId, false);
      await loadShadowReadiness();
    } catch (err: any) {
      setErrorMsg(err.message || '关闭影子模式失败');
    } finally {
      setDisablingShadowId(null);
    }
  };

  const loadInbox = async () => {
    try {
      const data = await api.getDecisionInbox(initiativeId);
      setInbox(data.items);
    } catch (e) {
      console.error('Failed to load decision inbox:', e);
    }
  };

  const refreshLeaderQueue = async () => {
    await Promise.all([loadInbox(), loadPendingGates()]);
    onDecisionUpdated();
  };

  const handleInboxDecision = async (item: DecisionInboxItem, decision: 'accept_review' | 'override_review') => {
    try {
      setInboxBusy(`${item.module_id}:${decision}`);
      setErrorMsg(null);
      await api.resolveModuleDispute(item.module_id, decision);
      await refreshLeaderQueue();
    } catch (err: any) {
      setErrorMsg(err.message || '裁决失败');
    } finally {
      setInboxBusy(null);
    }
  };

  const waitForRecheck = async (jobId: string) => {
    const deadline = Date.now() + 10 * 60 * 1000;
    for (;;) {
      const job = await api.getOrchestrationJob(jobId);
      if (job.status !== 'queued' && job.status !== 'running') return;
      if (job.status === 'queued' && !job.runner_alive) {
        throw new Error('检查已排队，但执行器没在跑');
      }
      if (Date.now() > deadline) return;
      await new Promise((resolve) => window.setTimeout(resolve, 1000));
    }
  };

  const handleRecheck = async (item: DecisionInboxItem) => {
    try {
      setInboxBusy(`${item.module_id}:recheck`);
      setErrorMsg(null);
      const queued = await api.submitModuleForGate(item.module_id);
      if (queued.job_id) await waitForRecheck(queued.job_id);
      await refreshLeaderQueue();
    } catch (err: any) {
      setErrorMsg(err.message || '重新检查失败');
    } finally {
      setInboxBusy(null);
    }
  };

  const loadPendingGates = async () => {
    try {
      const gates = await api.listPendingGatesForBatch();
      setPendingGates(gates);
    } catch (e) {
      console.error('Failed to load pending gates:', e);
    }
  };

  const handleAction = async (decisionId: string, action: 'approve' | 'reject') => {
    try {
      setActingId(decisionId);
      setErrorMsg(null);
      await api.actOnDecision(initiativeId, decisionId, action, 'CEO / 总负责人');
      onDecisionUpdated();
    } catch (err: any) {
      console.error(err);
      setErrorMsg(err.message || '操作失败，请重试');
    } finally {
      setActingId(null);
    }
  };

  const handleResolveRisk = async (riskId: string) => {
    try {
      setResolvingRiskId(riskId);
      setErrorMsg(null);
      await api.resolveRisk(initiativeId, riskId);
      onDecisionUpdated();
    } catch (err: any) {
      console.error('Failed to resolve risk:', err);
      setErrorMsg(err.message || '操作失败，请重试');
    } finally {
      setResolvingRiskId(null);
    }
  };

  const handleOpenGateReviewFromRisk = (risk: ExecutiveRiskItem) => {
    const modCode = risk.rule_code.replace('GATE_RED_', '');
    const gate = pendingGates.find(
      (g) => g.product_code === risk.product_code && g.module_code === modCode
    );
    if (gate) {
      setSelectedGateForReview(gate);
    } else {
      const fallbackGate = pendingGates.find((g) => g.product_code === risk.product_code) || pendingGates[0];
      if (fallbackGate) {
        setSelectedGateForReview(fallbackGate);
      } else {
        const sec3 = document.getElementById('strategic-gates-section');
        if (sec3) {
          sec3.scrollIntoView({ behavior: 'smooth' });
        }
      }
    }
  };

  const activeRiskGroups = groupByProduct(operationalRisks, (risk) => risk.product_code, matrixProducts);
  const resolvedRiskGroups = groupByProduct(resolvedRisks, (risk) => risk.product_code, matrixProducts);
  const handoffItems = inbox.filter((item) => item.kind === 'handoff_gap');
  const handoffGroups = groupByProduct(handoffItems, (item) => item.product_code, matrixProducts);
  const gateGroups = groupByProduct(visibleGates, (gate) => gate.product_code, matrixProducts);
  const showActiveRiskGroups = activeRiskGroups.length > 1;
  const showResolvedRiskGroups = resolvedRiskGroups.length > 1;
  const showHandoffGroups = handoffGroups.length > 1;
  const showGateGroups = gateGroups.length > 1;

  return (
    <div className="space-y-6">
      {/* 顶部总盘 */}
      <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-emerald-600" />
              经营决策与审批中心
            </h2>
            <p className="text-xs text-slate-500">
              汇集关键经营风险与 AI 调配建议。重大决策与资金变动由您亲自确认，杜绝系统盲目自主变更。
            </p>
          </div>

          <div className="flex items-center gap-2 text-xs">
            <span className="px-2.5 py-1 rounded-lg bg-amber-50 text-amber-800 font-mono font-semibold border border-amber-200">
              待处理风险: {operationalRisks.length} 项
            </span>
            {resolvedRisks.length > 0 && (
              <span className="px-2.5 py-1 rounded-lg bg-slate-50 text-slate-600 font-mono font-medium border border-slate-200">
                已处置完成: {resolvedRisks.length} 项
              </span>
            )}
            <span className="px-2.5 py-1 rounded-lg bg-emerald-50 text-emerald-800 font-mono font-semibold border border-emerald-200">
              待决策: {decisions.filter((d) => d.status === 'proposed').length} 案
            </span>
          </div>
        </div>
      </div>

      {errorMsg && (
        <div className="p-3 rounded-xl bg-rose-50 text-rose-700 text-xs border border-rose-200 flex items-center justify-between">
          <span>{errorMsg}</span>
          <button onClick={() => setErrorMsg(null)} className="text-rose-500 hover:text-rose-700 font-bold">
            ✕
          </button>
        </div>
      )}

      {shadowReady.length > 0 && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-2xl p-4 space-y-2">
          <h3 className="text-xs font-bold text-emerald-950 flex items-center gap-2">
            <Bot className="w-4 h-4 text-emerald-700" />
            以下项目的 lead 建议已足够可靠，可以关闭影子模式
          </h3>
          <p className="text-[11px] text-emerald-800">关闭后，检查通过的普通阶段会自动继续。方向、花钱、发布，以及评审分歧，仍只在本页等您处理。</p>
          {shadowReady.map(({ product, stats }) => (
            <div
              key={product.id}
              className="p-3 bg-white border border-emerald-200 rounded-xl flex items-center justify-between gap-3 text-xs"
            >
              <div>
                <span className="font-mono font-bold text-emerald-900 mr-2">{product.code}</span>
                <span className="text-slate-700">{stats.readiness_reason}</span>
              </div>
              <button
                onClick={() => handleDisableShadow(product.id)}
                disabled={disablingShadowId === product.id}
                className="shrink-0 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-60 text-white rounded-lg font-semibold transition cursor-pointer"
              >
                {disablingShadowId === product.id ? '处理中...' : '关闭影子模式'}
              </button>
            </div>
          ))}
        </div>
      )}

      {/* 1. 经营风险预警 */}
      <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="space-y-0.5">
            <h3 className="text-xs font-bold text-slate-900 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-500" />
              <span>一、经营风险预警</span>
            </h3>
            <p className="text-[11px] text-slate-500">
              预算超支、安全拦截、修订卡住、评审分歧和交接缺口。需要您确认才能继续的阶段，只列在第三节。
            </p>
          </div>
          <span className="text-xs font-mono font-semibold px-2 py-0.5 rounded bg-slate-100 text-slate-600">
            {operationalRisks.length > 0 ? `待处理: ${operationalRisks.length} 项` : '全部指标安全'}
          </span>
        </div>

        {/* 待处理风险列表 */}
        {operationalRisks.length === 0 ? (
          <div className="py-6 px-4 text-center rounded-xl bg-emerald-50/50 border border-emerald-200/60 text-slate-600 text-xs flex flex-col items-center justify-center space-y-1.5">
            <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-600">
              <CheckCircle2 className="w-5 h-5" />
            </div>
            <span className="font-semibold text-slate-800 text-sm">当前无待处理风险预警</span>
            <span className="text-slate-500 text-xs">各项矩阵产品、资金支出与安全合规均处于基线内。</span>
          </div>
        ) : (
          <div className="space-y-4">
            {activeRiskGroups.map((group) => (
            <div key={group.key} className="space-y-3">
            {showActiveRiskGroups && (
              <ProductGroupLabel code={group.code} name={group.name} count={group.items.length} />
            )}
            {group.items.map((risk) => {
              const isGateRisk = risk.rule_code.startsWith('GATE_RED_');
              const isSecurity = risk.rule_code.includes('SECURITY_VIOLATION');
              const queueItem = inbox.find((item) => item.risk_id === risk.id);

              return (
                <div
                  key={risk.id}
                  className={`p-4 rounded-xl border transition space-y-3 ${
                    risk.severity === 'critical'
                      ? 'bg-rose-50/60 border-rose-300 shadow-2xs'
                      : 'bg-amber-50/60 border-amber-300 shadow-2xs'
                  }`}
                >
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider ${
                          isGateRisk
                            ? 'bg-rose-100 text-rose-800 border border-rose-200'
                            : isSecurity
                            ? 'bg-red-100 text-red-800 border border-red-200'
                            : 'bg-amber-100 text-amber-800 border border-amber-200'
                        }`}
                      >
                        {isGateRisk ? '🔴 待您亲自把关' : isSecurity ? '🚨 安全机制拦截' : '🟡 经营风险预警'}
                      </span>
                      <span className="text-xs font-semibold px-2 py-0.5 rounded bg-white text-slate-700 border border-slate-200">
                        {formatRuleCode(risk.rule_code)}
                      </span>
                      {risk.product_code && (
                        <span className="text-[11px] px-2 py-0.5 rounded bg-white text-slate-700 border border-slate-200 font-mono font-semibold">
                          关联: {risk.product_code}
                        </span>
                      )}
                    </div>

                    <span className="text-[11px] text-slate-400 font-mono">
                      {new Date(risk.created_at).toLocaleDateString()}
                    </span>
                  </div>

                  <h4 className="text-sm font-bold text-slate-900 leading-snug">
                    {withoutStageNumber(formatRiskTitle(risk.title, false))}
                  </h4>
                  <p className="text-xs text-slate-700 leading-relaxed font-medium">
                    {withoutStageNumber(formatRiskDescription(risk.description))}
                  </p>

                  <div className="pt-2 border-t border-rose-200/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="text-[11px] text-slate-700 flex items-center gap-1.5 font-medium">
                      <span className="text-slate-500 shrink-0">应对建议：</span>
                      <span>{formatRiskSuggestion(risk.action_suggestion, false)}</span>
                    </div>

                    <div className="shrink-0 flex items-center gap-2">
                      {queueItem?.kind === 'dispute' ? (
                        <>
                          <button
                            disabled={inboxBusy !== null}
                            onClick={() => handleInboxDecision(queueItem, 'accept_review')}
                            className="px-3.5 py-1.5 rounded-xl text-xs font-bold bg-indigo-600 hover:bg-indigo-500 text-white transition shadow-xs cursor-pointer disabled:opacity-50"
                          >
                            {inboxBusy === `${queueItem.module_id}:accept_review` ? '处理中...' : '采纳评审意见'}
                          </button>
                          <button
                            disabled={inboxBusy !== null}
                            onClick={() => handleInboxDecision(queueItem, 'override_review')}
                            className="px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-white hover:bg-slate-100 text-slate-700 border border-slate-300 transition shadow-xs cursor-pointer disabled:opacity-50"
                          >
                            按当前交付物继续
                          </button>
                        </>
                      ) : queueItem?.kind === 'stuck' ? (
                        <button
                          disabled={inboxBusy !== null}
                          onClick={() => handleRecheck(queueItem)}
                          className="px-3.5 py-1.5 rounded-xl text-xs font-bold bg-amber-600 hover:bg-amber-500 text-white transition shadow-xs cursor-pointer disabled:opacity-50"
                        >
                          {inboxBusy === `${queueItem.module_id}:recheck` ? '检查中...' : '重新检查'}
                        </button>
                      ) : risk.rule_code.startsWith('ORCH_DISPUTE_') || risk.rule_code.startsWith('ORCH_STUCK_') ? (
                        <span className="text-[11px] text-slate-500">正在读取可执行操作</span>
                      ) : isGateRisk ? (
                        <button
                          onClick={() => handleOpenGateReviewFromRisk(risk)}
                          className="px-3.5 py-1.5 rounded-xl text-xs font-bold bg-rose-600 hover:bg-rose-500 text-white transition shadow-xs flex items-center gap-1.5 cursor-pointer"
                        >
                          <FileCheck2 className="w-3.5 h-3.5" />
                          <span>前往签署放行</span>
                        </button>
                      ) : (
                        <button
                          disabled={resolvingRiskId === risk.id}
                          onClick={() => handleResolveRisk(risk.id)}
                          className="px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-white hover:bg-slate-100 text-slate-700 border border-slate-300 transition shadow-xs flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                          <span>{resolvingRiskId === risk.id ? '处理中...' : '标记已核查消除'}</span>
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
            </div>
            ))}
          </div>
        )}

        {handoffItems.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-xs font-bold text-slate-800">交接缺口：下游还不能开工</h4>
            {handoffGroups.map((group) => (
            <div key={group.key} className="space-y-2">
            {showHandoffGroups && (
              <ProductGroupLabel code={group.code} name={group.name} count={group.items.length} />
            )}
            {group.items.map((item) => (
              <div key={`${item.module_id}:${item.title}`} className="p-3 rounded-xl bg-orange-50 border border-orange-200 text-xs text-slate-700">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-mono font-bold">{item.product_code}</span>
                  <span>{stageName(item.module_code)}</span>
                </div>
                <p className="font-medium text-slate-900">{withoutStageNumber(item.title)}</p>
                <p className="mt-1 text-slate-600">{withoutStageNumber(item.detail)}</p>
              </div>
            ))}
            </div>
            ))}
          </div>
        )}

        {/* 已处置历史记录 (可折叠) */}
        {resolvedRisks.length > 0 && (
          <div className="pt-2">
            <button
              onClick={() => setShowResolvedRisks(!showResolvedRisks)}
              className="w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl bg-slate-50 hover:bg-slate-100 text-slate-600 text-xs font-medium border border-slate-200 transition cursor-pointer"
            >
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>已处置完成的历史记录 ({resolvedRisks.length} 项)</span>
              </div>
              {showResolvedRisks ? (
                <ChevronUp className="w-4 h-4 text-slate-400" />
              ) : (
                <ChevronDown className="w-4 h-4 text-slate-400" />
              )}
            </button>

            {showResolvedRisks && (
              <div className="mt-3 space-y-4">
                {resolvedRiskGroups.map((group) => (
                <div key={group.key} className="space-y-2.5">
                {showResolvedRiskGroups && (
                  <ProductGroupLabel code={group.code} name={group.name} count={group.items.length} />
                )}
                {group.items.map((risk) => (
                  <div
                    key={risk.id}
                    className="p-3.5 rounded-xl bg-slate-50/70 border border-slate-200 text-slate-600 space-y-1.5"
                  >
                    <div className="flex items-center justify-between flex-wrap gap-2 text-xs">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-200/80 text-slate-600 border border-slate-300">
                          ✅ 已处置完成
                        </span>
                        <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-white text-slate-600 border border-slate-200">
                          {formatRuleCode(risk.rule_code)}
                        </span>
                        {risk.product_code && (
                          <span className="text-[11px] px-2 py-0.2 rounded bg-white text-slate-600 border border-slate-200 font-mono">
                            关联: {risk.product_code}
                          </span>
                        )}
                      </div>
                      <span className="text-[11px] text-slate-400 font-mono">
                        {new Date(risk.created_at).toLocaleDateString()}
                      </span>
                    </div>

                    <h4 className="text-xs font-semibold text-slate-800">
                      {withoutStageNumber(formatRiskTitle(risk.title, true))}
                    </h4>
                    <p className="text-[11px] text-slate-500 leading-relaxed">
                      {withoutStageNumber(formatRiskDescription(risk.description))}
                    </p>

                    <div className="pt-1 text-[11px] text-emerald-700 font-medium flex items-center gap-1.5">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                      <span>处置结论：{formatRiskSuggestion(risk.action_suggestion, true)}</span>
                    </div>
                  </div>
                ))}
                </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* 2. AI 决策建议与审批 */}
      <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <h3 className="text-xs font-bold text-slate-900 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-emerald-600" />
            <span>二、AI 辅助调配建议与审批</span>
          </h3>
          <span className="text-xs text-slate-400">依据充分可查 · 确认后自动执行</span>
        </div>

        {decisions.length === 0 ? (
          <div className="py-8 text-center text-slate-400 text-xs">
            当前暂无待确认的建议方案。
          </div>
        ) : (
          <div className="space-y-5">
            {decisions.map((dec) => {
              const isProposed = dec.status === 'proposed';
              const isExecuted = dec.status === 'approved' || dec.status === 'executed';
              const isRejected = dec.status === 'rejected';

              return (
                <div
                  key={dec.id}
                  className="p-5 rounded-2xl bg-slate-50 border border-slate-200 hover:border-emerald-300 transition space-y-4"
                >
                  {/* 提议头部 */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-200 pb-3">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span
                          className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded uppercase tracking-wider ${
                            isProposed
                              ? 'bg-amber-100 text-amber-800 border border-amber-300'
                              : isExecuted
                              ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                              : 'bg-rose-100 text-rose-800 border border-rose-300'
                          }`}
                        >
                          {isProposed ? '待您确认' : isExecuted ? '已确认生效' : '已驳回'}
                        </span>
                        <span className="text-xs font-mono text-slate-400">ID: {dec.id}</span>
                      </div>
                      <h4 className="text-sm font-bold text-slate-900">{dec.title}</h4>
                    </div>

                    <div className="text-left sm:text-right text-[11px] text-slate-400 font-mono">
                      <span>幂等号: {dec.idempotency_key}</span>
                      {dec.approved_by && (
                        <div className="text-emerald-700 font-sans font-medium">
                          由 {dec.approved_by} 于 {dec.approved_at ? new Date(dec.approved_at).toLocaleTimeString() : ''} 审批
                        </div>
                      )}
                    </div>
                  </div>

                  {/* 核心建议卡片 */}
                  {dec.recommendation && (
                    <div className="p-3.5 bg-white rounded-xl border border-slate-200 space-y-1.5 text-xs">
                      <div className="font-semibold text-slate-800 flex items-center justify-between">
                        <span className="flex items-center gap-1.5 text-emerald-700">
                          <FileCheck2 className="w-4 h-4" />
                          建议调整方案
                        </span>
                        {dec.recommendation.amount && (
                          <span className="font-mono font-bold text-emerald-700 text-sm">
                            ¥{dec.recommendation.amount.toLocaleString()}
                          </span>
                        )}
                      </div>
                      <p className="text-slate-600 text-[11px] leading-relaxed">
                        {dec.recommendation.summary}
                      </p>
                      {dec.recommendation.from_product_code && dec.recommendation.to_product_code && (
                        <div className="flex items-center gap-2 text-[11px] text-slate-500 pt-1">
                          <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-800 font-mono font-semibold">
                            调出: {dec.recommendation.from_product_code}
                          </span>
                          <span>→</span>
                          <span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200 font-mono font-semibold">
                            调入: {dec.recommendation.to_product_code}
                          </span>
                        </div>
                      )}
                    </div>
                  )}

                  {/* 推导计算依据 & 预期经营影响 */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                    {/* 计算依据 */}
                    <div className="p-3 bg-white rounded-xl border border-slate-200 space-y-2">
                      <span className="font-semibold text-slate-800 flex items-center gap-1">
                        <Database className="w-3.5 h-3.5 text-blue-600" />
                        推导依据与数据支撑
                      </span>
                      {dec.evidence?.data_coverage && (
                        <p className="text-[11px] text-slate-500">
                          覆盖度: {dec.evidence.data_coverage}
                        </p>
                      )}
                      {dec.evidence?.assumptions && (
                        <ul className="text-[11px] text-slate-600 list-disc list-inside space-y-0.5 leading-relaxed">
                          {dec.evidence.assumptions.map((assump: string, idx: number) => (
                            <li key={idx}>{assump}</li>
                          ))}
                        </ul>
                      )}
                    </div>

                    {/* 预期影响与折衷风险 */}
                    <div className="p-3 bg-white rounded-xl border border-slate-200 space-y-2">
                      <span className="font-semibold text-slate-800 flex items-center gap-1">
                        <TrendingDown className="w-3.5 h-3.5 text-emerald-600" />
                        预期收益与潜在影响
                      </span>
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="text-slate-500">预计节省/提升资金：</span>
                        <span className="font-mono font-bold text-slate-800">
                          ¥{(dec.impact_projection?.expected_cost_savings || 0).toLocaleString()}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="text-slate-500">现金回本节点变动：</span>
                        <span className="font-mono font-bold text-emerald-700">
                          提早 {Math.abs(dec.impact_projection?.forecast_breakeven_variance_days || 0)} 天
                        </span>
                      </div>
                      {dec.impact_projection?.identified_risks && (
                        <div className="text-[10px] text-rose-600 bg-rose-50 p-1.5 rounded-lg border border-rose-200/60">
                          伴随折衷风险：{dec.impact_projection.identified_risks.join('；')}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* 审批操作按钮 */}
                  <div className="pt-2 border-t border-slate-200 flex items-center justify-between">
                    <span className="text-[11px] text-slate-400 flex items-center gap-1 font-mono">
                      <Lock className="w-3 h-3 text-slate-400" />
                      安全事务机制 · 防重复执行
                    </span>

                    {isProposed ? (
                      <div className="flex items-center gap-2">
                        <button
                          disabled={actingId === dec.id}
                          onClick={() => handleAction(dec.id, 'reject')}
                          className="px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-white hover:bg-slate-100 text-slate-700 border border-slate-300 transition cursor-pointer disabled:opacity-50"
                        >
                          打回修改
                        </button>
                        <button
                          disabled={actingId === dec.id}
                          onClick={() => handleAction(dec.id, 'approve')}
                          className="px-4 py-1.5 rounded-xl text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white transition shadow-xs cursor-pointer disabled:opacity-50 flex items-center gap-1.5"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          {actingId === dec.id ? '执行中...' : '确认并执行'}
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-1 text-xs text-slate-500 font-medium">
                        <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                        <span>已完成处理流程</span>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 3. 战略关口待审批池 */}
      <div id="strategic-gates-section" className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="space-y-0.5">
            <h3 className="text-xs font-bold text-slate-900 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-rose-600" />
              <span>三、请您确认才能继续的阶段</span>
            </h3>
            <p className="text-[11px] text-slate-500">
              方向、小额测试、发布、买量，以及涉及收款、隐私和密钥的变更，都在这里等您确认。
            </p>
          </div>
          <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-700">
            待您确认: {visibleGates.length} 个阶段
          </span>
        </div>

        {visibleGates.length === 0 ? (
          <div className="py-8 text-center text-slate-400 text-xs">
            <CheckCircle2 className="w-8 h-8 mx-auto mb-2 text-emerald-500" />
            当前无待确认的重大阶段，所有矩阵产品流水线均在正常流转中。
          </div>
        ) : (
          <div className="space-y-4">
            {gateGroups.map((group) => (
            <div key={group.key} className="space-y-3">
            {showGateGroups && (
              <ProductGroupLabel code={group.code} name={group.name} count={group.items.length} />
            )}
            {group.items.map((gate) => (
              <div
                key={gate.id}
                className={`p-4 rounded-xl border flex flex-col sm:flex-row sm:items-center justify-between gap-4 transition shadow-2xs ${
                  gate.effective_level === 'red'
                    ? 'bg-rose-50/60 border-rose-300'
                    : 'bg-amber-50/60 border-amber-300'
                }`}
              >
                <div className="space-y-1.5 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-white text-slate-800 border border-slate-200">
                      {gate.product_code}
                    </span>
                    <h4 className="font-bold text-slate-900 text-xs">{stageDecision(gate.module_code, gate.gate_name)}</h4>
                    <GateBadge
                      level={gate.effective_level}
                      isEscalated={gate.is_escalated}
                      size="sm"
                    />
                  </div>

                  <p className="text-xs text-slate-700 leading-relaxed font-medium">
                    {gate.recommendation}
                  </p>

                  {gate.lead_recommendation && (
                    <div className="text-[11px] text-purple-900 flex items-center gap-1.5 pt-0.5">
                      <Bot className="w-3.5 h-3.5 text-purple-600 shrink-0" />
                      <span>
                        项目总控：<strong>{leadActionLabel(gate.lead_recommendation)}</strong>
                        {gate.lead_rationale && `。${plainLeadRationale(gate.lead_rationale)}`}
                      </span>
                    </div>
                  )}

                  {gate.is_escalated && gate.escalation_reasons?.length > 0 && (
                    <div className="text-[11px] text-rose-700 flex items-center gap-1 pt-0.5">
                      <AlertTriangle className="w-3.5 h-3.5 text-rose-500 shrink-0" />
                      <span>特别提示：{gate.escalation_reasons.join('；')}</span>
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
                  <button
                    onClick={() => setSelectedGateForReview(gate)}
                    className="px-4 py-2 rounded-xl text-xs font-bold bg-slate-900 hover:bg-slate-800 text-white transition shadow-xs flex items-center gap-1.5 cursor-pointer"
                  >
                    <FileCheck2 className="w-3.5 h-3.5" />
                    <span>查看详情并确认</span>
                  </button>
                </div>
              </div>
            ))}
            </div>
            ))}
          </div>
        )}
      </div>

      {/* 关口一页纸审批弹窗 */}
      {selectedGateForReview && (
        <GateApplicationModal
          isOpen={Boolean(selectedGateForReview)}
          moduleId={selectedGateForReview.module_id}
          moduleCode={selectedGateForReview.module_code}
          moduleName={selectedGateForReview.gate_name}
          onClose={() => setSelectedGateForReview(null)}
          onApproved={() => {
            loadPendingGates();
            onDecisionUpdated();
            setSelectedGateForReview(null);
          }}
        />
      )}
    </div>
  );
};
