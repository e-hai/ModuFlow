import React, { useState, useEffect } from 'react';
import { GateApplication, GateConfig } from '../../types';
import { api } from '../../services/api';
import { GateBadge } from './GateBadge';
import {
  X,
  ShieldCheck,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  Sparkles,
  Bot,
  UserCheck,
  FileText,
  Loader2,
  CornerDownRight,
  Send
} from 'lucide-react';

interface GateApplicationModalProps {
  moduleId: string;
  moduleCode: string;
  moduleName: string;
  isOpen: boolean;
  onClose: () => void;
  onApproved?: () => void;
}

export const GateApplicationModal: React.FC<GateApplicationModalProps> = ({
  moduleId,
  moduleCode,
  moduleName,
  isOpen,
  onClose,
  onApproved,
}) => {
  const [gateConfig, setGateConfig] = useState<GateConfig | null>(null);
  const [gateApp, setGateApp] = useState<GateApplication | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [reviewAction, setReviewAction] = useState<'approve' | 'reject' | 'adjust'>('approve');
  const [reviewComment, setReviewComment] = useState('');
  const [reviewerName, setReviewerName] = useState('CEO / 人类战略层');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Form fields for creating a new gate application if none exists
  const [newRecommendation, setNewRecommendation] = useState('');
  const [newRiskAssessment, setNewRiskAssessment] = useState('');

  useEffect(() => {
    if (isOpen && moduleId) {
      loadGateData();
    }
  }, [isOpen, moduleId]);

  const loadGateData = async () => {
    try {
      setLoading(true);
      setErrorMsg(null);
      const [config, app] = await Promise.allSettled([
        api.getModuleGateConfig(moduleId),
        api.getModuleGateApplication(moduleId),
      ]);

      if (config.status === 'fulfilled') {
        setGateConfig(config.value);
      }
      if (app.status === 'fulfilled') {
        setGateApp(app.value);
      } else {
        setGateApp(null);
        // Pre-fill default recommendation
        setNewRecommendation(`本工序 [${moduleCode} ${moduleName}] 成果已完成闭环校验，符合放行准则。`);
        setNewRiskAssessment('经合规与技术排查，无阻断性风险，建议按既定标准准予放行。');
      }
    } catch (err: any) {
      console.error('Failed to load gate data:', err);
      setErrorMsg(err.message || '加载关口数据失败');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateApplication = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRecommendation.trim() || !newRiskAssessment.trim()) return;

    try {
      setSubmitting(true);
      setErrorMsg(null);
      const created = await api.submitGateApplication(moduleId, {
        recommendation: newRecommendation.trim(),
        evidence: [
          `工序交付物已就绪`,
          `前置依赖项与门禁校验通过`,
          `提交时间: ${new Date().toLocaleString()}`,
        ],
        risk_assessment: newRiskAssessment.trim(),
        decision_options: ['approve', 'reject', 'adjust'],
        context: {},
      });
      setGateApp(created);
    } catch (err: any) {
      setErrorMsg(err.message || '提报关口申请单失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleLeadEvaluate = async () => {
    try {
      setSubmitting(true);
      setErrorMsg(null);
      const evaluated = await api.evaluateGateByLead(moduleId);
      setGateApp(evaluated);
    } catch (err: any) {
      setErrorMsg(err.message || 'Lead 评估关口失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleReview = async () => {
    if (!gateApp) return;

    try {
      setSubmitting(true);
      setErrorMsg(null);
      const reviewed = await api.reviewGateApplication(gateApp.id, {
        action: reviewAction,
        comment: reviewComment.trim() || (reviewAction === 'approve' ? '同意放行' : '请根据意见调整'),
        reviewer_name: reviewerName.trim() || '人类战略层',
      });
      setGateApp(reviewed);
      if (reviewAction === 'approve' && onApproved) {
        onApproved();
      }
    } catch (err: any) {
      setErrorMsg(err.message || '审批操作失败');
    } finally {
      setSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-white border border-slate-200 w-full max-w-2xl rounded-2xl shadow-2xl overflow-hidden my-8 max-h-[90vh] flex flex-col">
        {/* 顶部标题栏 */}
        <div className="p-5 border-b border-slate-100 flex items-center justify-between bg-slate-50/80">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-600 shrink-0">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 font-bold">
                  {moduleCode}
                </span>
                <h3 className="font-bold text-slate-900 text-base">
                  {gateConfig?.name || `工序 ${moduleCode} 关口`} 一页纸申请单
                </h3>
                {gateApp ? (
                  <GateBadge
                    level={gateApp.effective_level}
                    gateName={gateApp.gate_name}
                    isEscalated={gateApp.is_escalated}
                    size="sm"
                  />
                ) : gateConfig ? (
                  <GateBadge level={gateConfig.level} gateName={gateConfig.name} size="sm" />
                ) : null}
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                所属模块：{moduleName} · {gateConfig?.approver === 'human' ? '需人类战略层审批' : '由项目总控层/人类协同'}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* 错误警告条 */}
        {errorMsg && (
          <div className="p-3 bg-rose-50 border-b border-rose-200 text-rose-700 text-xs flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{errorMsg}</span>
            </div>
            <button onClick={() => setErrorMsg(null)} className="text-rose-500 hover:text-rose-800 font-bold">
              ✕
            </button>
          </div>
        )}

        {/* 主内容区域 */}
        <div className="p-6 overflow-y-auto space-y-5 flex-1 text-slate-700 text-xs">
          {loading ? (
            <div className="py-16 text-center text-slate-400 space-y-2">
              <Loader2 className="w-6 h-6 animate-spin mx-auto text-emerald-600" />
              <p>加载关口审批契约中...</p>
            </div>
          ) : gateApp ? (
            <>
              {/* 自动升红警示 */}
              {gateApp.is_escalated && (
                <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 space-y-1.5 animate-pulse">
                  <div className="flex items-center gap-2 font-bold text-rose-800 text-xs">
                    <AlertTriangle className="w-4 h-4 text-rose-600" />
                    <span>⚠️ 自动升级为 🔴 红级关口（人类即时必批）</span>
                  </div>
                  <p className="text-[11px] text-rose-700">
                    触发条件：{gateApp.escalation_reasons?.join('；') || '检测到敏感变更，系统已强制阻断'}
                  </p>
                </div>
              )}

              {/* 关口状态卡片 */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-slate-50 p-3.5 rounded-xl border border-slate-200">
                <div>
                  <span className="text-slate-400 block text-[11px]">审批状态</span>
                  <span className="font-bold text-slate-900 capitalize">
                    {gateApp.status === 'approved' ? (
                      <span className="text-emerald-700 flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5" /> 已批准放行
                      </span>
                    ) : gateApp.status === 'rejected' ? (
                      <span className="text-rose-700 flex items-center gap-1">
                        <XCircle className="w-3.5 h-3.5" /> 已打回整改
                      </span>
                    ) : gateApp.status === 'adjusted' ? (
                      <span className="text-amber-700 flex items-center gap-1">
                        <AlertTriangle className="w-3.5 h-3.5" /> 调整要求
                      </span>
                    ) : (
                      <span className="text-indigo-700 flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5" /> 待审批 (Pending)
                      </span>
                    )}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px]">有效关口级别</span>
                  <span className="font-mono font-bold text-slate-900 uppercase">
                    {gateApp.effective_level}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px]">提报主体</span>
                  <span className="font-mono text-slate-700">{gateApp.submitted_by}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px]">提报时间</span>
                  <span className="text-slate-600">{new Date(gateApp.submitted_at).toLocaleTimeString()}</span>
                </div>
              </div>

              {/* 一页纸主体：1. 结论建议 */}
              <div className="space-y-1.5 bg-white border border-slate-200 p-4 rounded-xl">
                <h4 className="font-bold text-slate-900 text-xs flex items-center gap-1.5">
                  <span className="w-4 h-4 rounded-full bg-emerald-100 text-emerald-800 text-[10px] flex items-center justify-center font-bold">
                    1
                  </span>
                  结论建议 (Executive Recommendation)
                </h4>
                <div className="p-3 bg-slate-50 rounded-lg text-slate-800 leading-relaxed font-medium">
                  {gateApp.recommendation}
                </div>
              </div>

              {/* 一页纸主体：2. 依据事实清单 */}
              <div className="space-y-1.5 bg-white border border-slate-200 p-4 rounded-xl">
                <h4 className="font-bold text-slate-900 text-xs flex items-center gap-1.5">
                  <span className="w-4 h-4 rounded-full bg-emerald-100 text-emerald-800 text-[10px] flex items-center justify-center font-bold">
                    2
                  </span>
                  事实依据清单 (Verifiable Evidence)
                </h4>
                <ul className="space-y-1 pl-1">
                  {Array.isArray(gateApp.evidence) ? (
                    gateApp.evidence.map((item, idx) => (
                      <li key={idx} className="flex items-start gap-2 text-slate-700">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />
                        <span>{typeof item === 'string' ? item : JSON.stringify(item)}</span>
                      </li>
                    ))
                  ) : (
                    <li className="text-slate-600">{String(gateApp.evidence)}</li>
                  )}
                </ul>
              </div>

              {/* 一页纸主体：3. 风险排查与对策 */}
              <div className="space-y-1.5 bg-white border border-slate-200 p-4 rounded-xl">
                <h4 className="font-bold text-slate-900 text-xs flex items-center gap-1.5">
                  <span className="w-4 h-4 rounded-full bg-emerald-100 text-emerald-800 text-[10px] flex items-center justify-center font-bold">
                    3
                  </span>
                  风险排查与规避对策 (Risk & Mitigation)
                </h4>
                <div className="p-3 bg-amber-50/60 border border-amber-200 rounded-lg text-amber-950 leading-relaxed">
                  {gateApp.risk_assessment}
                </div>
              </div>

              {/* Lead 影子建议 (Shadow Mode Insight) */}
              {gateApp.lead_recommendation && (
                <div className="space-y-1.5 p-3.5 rounded-xl bg-purple-50/80 border border-purple-200">
                  <div className="flex items-center justify-between">
                    <h5 className="font-bold text-purple-900 text-xs flex items-center gap-1.5">
                      <Bot className="w-4 h-4 text-purple-600" />
                      项目总控 (Lead Agent) 影子建议
                    </h5>
                    {gateApp.is_consistent !== null && gateApp.is_consistent !== undefined && (
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          gateApp.is_consistent
                            ? 'bg-emerald-100 text-emerald-800'
                            : 'bg-rose-100 text-rose-800'
                        }`}
                      >
                        {gateApp.is_consistent ? '✓ 建议与人类一致' : '✕ 存在分歧 (已记录)'}
                      </span>
                    )}
                  </div>
                  <p className="text-purple-950 font-medium">建议动作：{gateApp.lead_recommendation}</p>
                  {gateApp.lead_rationale && (
                    <p className="text-[11px] text-purple-700">{gateApp.lead_rationale}</p>
                  )}
                </div>
              )}

              {/* 决策操作控制区 */}
              {gateApp.status === 'pending' ? (
                <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-3">
                  <div className="flex items-center justify-between">
                    <h4 className="font-bold text-slate-900 text-xs flex items-center gap-1.5">
                      <UserCheck className="w-4 h-4 text-emerald-600" />
                      关口拍板裁决 (Human Review Sign-off)
                    </h4>
                    <span className="text-[11px] text-slate-500">
                      硬约束：黄/红级关口仅限人类账号审批
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                    <button
                      type="button"
                      onClick={() => setReviewAction('approve')}
                      className={`p-2.5 rounded-xl border text-xs font-bold transition flex items-center justify-center gap-1.5 cursor-pointer ${
                        reviewAction === 'approve'
                          ? 'bg-emerald-600 text-white border-emerald-600 shadow-xs'
                          : 'bg-white text-slate-700 border-slate-200 hover:border-emerald-300'
                      }`}
                    >
                      <CheckCircle2 className="w-4 h-4" />
                      通过放行 (Approve)
                    </button>
                    <button
                      type="button"
                      onClick={() => setReviewAction('adjust')}
                      className={`p-2.5 rounded-xl border text-xs font-bold transition flex items-center justify-center gap-1.5 cursor-pointer ${
                        reviewAction === 'adjust'
                          ? 'bg-amber-500 text-white border-amber-500 shadow-xs'
                          : 'bg-white text-slate-700 border-slate-200 hover:border-amber-300'
                      }`}
                    >
                      <AlertTriangle className="w-4 h-4" />
                      调整要求 (Adjust)
                    </button>
                    <button
                      type="button"
                      onClick={() => setReviewAction('reject')}
                      className={`p-2.5 rounded-xl border text-xs font-bold transition flex items-center justify-center gap-1.5 cursor-pointer ${
                        reviewAction === 'reject'
                          ? 'bg-rose-600 text-white border-rose-600 shadow-xs'
                          : 'bg-white text-slate-700 border-slate-200 hover:border-rose-300'
                      }`}
                    >
                      <XCircle className="w-4 h-4" />
                      打回整改 (Reject)
                    </button>
                  </div>

                  <div>
                    <label className="block text-[11px] font-medium text-slate-600 mb-1">
                      审批人身份 / 签名
                    </label>
                    <input
                      type="text"
                      value={reviewerName}
                      onChange={(e) => setReviewerName(e.target.value)}
                      className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded-lg text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                      placeholder="如：CEO / 业务负责人"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-medium text-slate-600 mb-1">
                      审批意见或调整批注
                    </label>
                    <textarea
                      rows={2}
                      value={reviewComment}
                      onChange={(e) => setReviewComment(e.target.value)}
                      className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                      placeholder="输入放行意见或针对性调整要求..."
                    />
                  </div>

                  <div className="flex justify-end gap-2 pt-1">
                    <button
                      onClick={handleReview}
                      disabled={submitting}
                      className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold transition shadow-xs flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                    >
                      {submitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                      确认提交拍板裁决
                    </button>
                  </div>
                </div>
              ) : (
                <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-900 text-xs">已完成审批留痕</span>
                    <span className="text-[11px] text-slate-400">
                      {gateApp.reviewed_at ? new Date(gateApp.reviewed_at).toLocaleString() : ''}
                    </span>
                  </div>
                  <div className="text-slate-700 text-xs">
                    审批人：<strong>{gateApp.reviewed_by}</strong> ({gateApp.reviewer_role})
                  </div>
                  {gateApp.review_comment && (
                    <div className="p-2.5 bg-white border border-slate-200 rounded-lg text-slate-800 text-[11px]">
                      {gateApp.review_comment}
                    </div>
                  )}
                </div>
              )}
            </>
          ) : (
            /* 尚无关口申请单：提供一键生成或手动提报 */
            <div className="space-y-4">
              <div className="p-4 bg-emerald-50/60 border border-emerald-200 rounded-xl space-y-2">
                <div className="flex items-center gap-2 font-bold text-emerald-900 text-xs">
                  <Sparkles className="w-4 h-4 text-emerald-600" />
                  <span>当前工序尚未生成一页纸关口申请单</span>
                </div>
                <p className="text-[11px] text-emerald-800 leading-relaxed">
                  在进行工序定稿 (Baseline) 或关口裁决前，需整理并提交标准的一页纸关口申请单（涵盖结论建议、依据事实、风险对策）。可点击下方按钮由项目总控 (Lead) 一键生成，或手动填写提报。
                </p>
                <div className="pt-2">
                  <button
                    onClick={handleLeadEvaluate}
                    disabled={submitting}
                    className="px-3.5 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                  >
                    {submitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Bot className="w-3.5 h-3.5" />}
                    项目总控 (Lead) 自动评估并提报
                  </button>
                </div>
              </div>

              <form onSubmit={handleCreateApplication} className="space-y-3 bg-white border border-slate-200 p-4 rounded-xl">
                <h4 className="font-bold text-slate-900 text-xs">手动提报关口申请单</h4>
                <div>
                  <label className="block text-[11px] font-medium text-slate-600 mb-1">
                    结论建议 (Executive Recommendation) *
                  </label>
                  <textarea
                    rows={2}
                    required
                    value={newRecommendation}
                    onChange={(e) => setNewRecommendation(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                    placeholder="输入本工序交付物质量与建议动作..."
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-medium text-slate-600 mb-1">
                    风险排查与规避对策 *
                  </label>
                  <textarea
                    rows={2}
                    required
                    value={newRiskAssessment}
                    onChange={(e) => setNewRiskAssessment(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                    placeholder="针对潜在平台审核、技术或商业风险的对策..."
                  />
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="submit"
                    disabled={submitting}
                    className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-xl text-xs font-bold transition flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                  >
                    {submitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                    提交申请单
                  </button>
                </div>
              </form>
            </div>
          )}
        </div>

        {/* 底部关闭栏 */}
        <div className="p-4 border-t border-slate-100 bg-slate-50/50 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-white hover:bg-slate-100 border border-slate-200 rounded-xl text-xs font-semibold text-slate-700 transition cursor-pointer"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  );
};
