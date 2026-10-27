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
  Bot
} from 'lucide-react';
import { ExecutiveDecisionItem, ExecutiveRiskItem, GateApplication } from '../../types';
import { api } from '../../services/api';
import { GateBadge } from '../gate/GateBadge';
import { GateApplicationModal } from '../gate/GateApplicationModal';

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
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [pendingGates, setPendingGates] = useState<GateApplication[]>([]);
  const [selectedGateForReview, setSelectedGateForReview] = useState<GateApplication | null>(null);

  const formatRiskTitle = (title: string): string => {
    return title
      .replace(/🔴\s*红级关口待批:\s*\[G4 提审门禁\]/g, '🔴 待您亲自把关：应用商店提审发布')
      .replace(/🔴\s*红级关口待批:\s*\[prd_linter 规格门禁\]/g, '🔴 待您亲自把关：产品需求规格审核 (PRD)')
      .replace(/🔴\s*红级关口待批:\s*\[([^\]]+)\]/g, '🔴 待您亲自把关：$1');
  };

  useEffect(() => {
    loadPendingGates();
  }, [initiativeId]);

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

  return (
    <div className="space-y-6">
      {/* 顶部总盘 */}
      <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-emerald-600" />
              经营决策中心 (Executive Decision & Risk Center)
            </h2>
            <p className="text-xs text-slate-500">
              面向 CEO / 总负责人的闭环管控：将宏观经营偏差与触发风险转化为结构化 AI 决策提议，严禁 AI 自主修改账本，由 CEO 最终拍板并执行原子事务。
            </p>
          </div>

          <div className="flex items-center gap-2 text-xs">
            <span className="px-2.5 py-1 rounded-lg bg-amber-50 text-amber-800 font-mono font-semibold border border-amber-200">
              触发风险: {risks.length} 项
            </span>
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

      {/* 1. 已触发的量化经营风险 */}
      <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <h3 className="text-xs font-bold text-slate-900 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-500" />
            <span>一、已触发的量化经营风险 (Triggered Business Risks)</span>
          </h3>
          <span className="text-xs text-slate-400">系统根据财务与埋点数据自动监控</span>
        </div>

        {risks.length === 0 ? (
          <div className="py-8 text-center text-slate-400 text-xs">
            <CheckCircle2 className="w-8 h-8 mx-auto mb-2 text-emerald-500" />
            暂无已触发的量化经营风险，各项指标均在安全基线范围内。
          </div>
        ) : (
          <div className="space-y-3">
            {risks.map((risk) => (
              <div
                key={risk.id}
                className={`p-4 rounded-xl border transition space-y-2 ${
                  risk.severity === 'critical'
                    ? 'bg-rose-50/50 border-rose-200'
                    : 'bg-amber-50/50 border-amber-200'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded uppercase tracking-wider ${
                        risk.is_resolved
                          ? 'bg-slate-100 text-slate-600 border border-slate-200'
                          : risk.severity === 'critical'
                          ? 'bg-rose-100 text-rose-800'
                          : 'bg-amber-100 text-amber-800'
                      }`}
                    >
                      {risk.is_resolved
                        ? '✅ 已处置完成'
                        : risk.severity === 'critical'
                        ? '🔴 必须亲自把关'
                        : '🟡 预警级风险'}
                    </span>
                    <span className="text-xs font-mono text-slate-500">{risk.rule_code}</span>
                    {risk.product_code && (
                      <span className="text-[11px] px-2 py-0.2 rounded bg-white text-slate-700 border border-slate-200 font-mono font-semibold">
                        关联: {risk.product_code}
                      </span>
                    )}
                  </div>

                  <span className="text-[11px] text-slate-400 font-mono">
                    {new Date(risk.created_at).toLocaleDateString()}
                  </span>
                </div>

                <h4 className="text-xs font-bold text-slate-900">{formatRiskTitle(risk.title)}</h4>
                <p className="text-xs text-slate-600 leading-relaxed">{risk.description}</p>

                {risk.action_suggestion && (
                  <div className="pt-1 text-[11px] text-slate-700 flex items-center gap-1 font-medium">
                    <span className="text-slate-500">应对举措建议：</span>
                    {risk.action_suggestion}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 2. 结构化 AI 决策提议与 CEO 拍板 */}
      <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <h3 className="text-xs font-bold text-slate-900 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-emerald-600" />
            <span>二、结构化 AI 决策建议与审批执行 (Executive Proposals)</span>
          </h3>
          <span className="text-xs text-slate-400">推导依据可验证 · 审批留存不可篡改审计流水</span>
        </div>

        {decisions.length === 0 ? (
          <div className="py-8 text-center text-slate-400 text-xs">
            暂无需要 CEO 审批的决策建议方案。
          </div>
        ) : (
          <div className="space-y-5">
            {decisions.map((dec) => {
              const isProposed = dec.status === 'proposed';
              const isExecuted = dec.status === 'executed' || dec.status === 'approved';
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
                          {isProposed ? '待拍板 (Proposed)' : isExecuted ? '已生效执行 (Executed)' : '已驳回 (Rejected)'}
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
                          调配执行内容与金额
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
                        计算与推导证据 (Evidence)
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
                        预测影响与折衷 (Impact Projection)
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

                  {/* CEO 审批操作按钮 */}
                  <div className="pt-2 border-t border-slate-200 flex items-center justify-between">
                    <span className="text-[11px] text-slate-400 flex items-center gap-1 font-mono">
                      <Lock className="w-3 h-3 text-slate-400" />
                      幂等事务写入 · 防止重复划转
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
                          {actingId === dec.id ? '执行中...' : '批准并生效执行'}
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

      {/* 3. 三层架构人类战略关口待审批池 */}
      <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="space-y-0.5">
            <h3 className="text-xs font-bold text-slate-900 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-rose-600" />
              <span>三、待您亲自把关确认的阶段成果 (审批待办池)</span>
            </h3>
            <p className="text-[11px] text-slate-500">
              为防止走偏或误操作，重大决策节点（如立项方向、假门外测决议、提审上架、价格与真实货币结算）必须由您亲自签署确认放行。
            </p>
          </div>
          <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-700">
            待您确认: {pendingGates.length} 个阶段
          </span>
        </div>

        {pendingGates.length === 0 ? (
          <div className="py-8 text-center text-slate-400 text-xs">
            <CheckCircle2 className="w-8 h-8 mx-auto mb-2 text-emerald-500" />
            当前无待确认的重大阶段，所有矩阵产品流水线均在正常流转中。
          </div>
        ) : (
          <div className="space-y-3">
            {pendingGates.map((gate) => (
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
                    <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-white text-slate-700 border border-slate-200">
                      工序 {gate.module_code}
                    </span>
                    <h4 className="font-bold text-slate-900 text-xs">{gate.gate_name}</h4>
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
                        AI主管预审建议：<strong>{gate.lead_recommendation}</strong>
                        {gate.lead_rationale && ` (${gate.lead_rationale})`}
                      </span>
                    </div>
                  )}

                  {gate.is_escalated && gate.escalation_reasons?.length > 0 && (
                    <div className="text-[11px] text-rose-700 flex items-center gap-1 pt-0.5">
                      <AlertTriangle className="w-3.5 h-3.5 text-rose-500 shrink-0" />
                      <span>重大变更原因：{gate.escalation_reasons.join('；')}</span>
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
                  <button
                    onClick={() => setSelectedGateForReview(gate)}
                    className="px-4 py-2 rounded-xl text-xs font-bold bg-slate-900 hover:bg-slate-800 text-white transition shadow-xs flex items-center gap-1.5 cursor-pointer"
                  >
                    <FileCheck2 className="w-3.5 h-3.5" />
                    <span>查看详情并拍板</span>
                  </button>
                </div>
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
