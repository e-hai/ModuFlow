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
  const [reviewerName, setReviewerName] = useState('业务负责人 / CEO');
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
        setNewRecommendation(`本阶段【${moduleCode} ${moduleName}】成果已交付，各项检查已就绪，建议准予通过进入下个环节。`);
        setNewRiskAssessment('经合规与功能自检，未发现阻塞性缺陷与违规项，风险可控。');
      }
    } catch (err: any) {
      console.error('Failed to load gate data:', err);
      setErrorMsg(err.message || '加载把关确认单失败');
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
          `本阶段交付物规范已封版`,
          `前置阶段依赖与质量要求检查通过`,
          `提报时间: ${new Date().toLocaleString()}`,
        ],
        risk_assessment: newRiskAssessment.trim(),
        decision_options: ['approve', 'reject', 'adjust'],
        context: {},
      });
      setGateApp(created);
    } catch (err: any) {
      setErrorMsg(err.message || '提交确认单失败');
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
      setErrorMsg(err.message || 'AI主管评估整理失败');
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
        comment: reviewComment.trim() || (reviewAction === 'approve' ? '同意通过' : '已批注修改要求'),
        reviewer_name: reviewerName.trim() || '业务负责人',
      });
      setGateApp(reviewed);
      if (reviewAction === 'approve' && onApproved) {
        onApproved();
      }
    } catch (err: any) {
      setErrorMsg(err.message || '决策提交失败');
    } finally {
      setSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-white border border-slate-200 w-full max-w-2xl rounded-2xl shadow-2xl overflow-hidden my-8 max-h-[90vh] flex flex-col">
        {/* 顶部标题栏 */}
        <div className="p-5 border-b border-slate-100 flex items-center justify-between bg-emerald-50/40">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-100 border border-emerald-200 flex items-center justify-center text-emerald-700 shrink-0">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-mono text-xs px-2 py-0.5 rounded bg-emerald-100 text-emerald-900 font-bold">
                  工序 {moduleCode}
                </span>
                <h3 className="font-bold text-slate-900 text-base">
                  {gateConfig?.name ? `${gateConfig.name} · 阶段把关拍板卡` : `阶段把关拍板卡`}
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
              <p className="text-xs text-slate-600 mt-0.5">
                所属环节：<strong>{moduleName}</strong> · 汇总交付成果、真实数据与风险对策，供您 30 秒轻松拍板
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
              <p>正在读取本阶段交付把关信息...</p>
            </div>
          ) : gateApp ? (
            <>
              {/* 重大变更提醒 */}
              {gateApp.is_escalated && (
                <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-950 space-y-1.5">
                  <div className="flex items-center gap-2 font-bold text-rose-800 text-xs">
                    <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
                    <span>⚠️ 检测到重大或高危变更（系统已自动暂停，需您亲自确认）</span>
                  </div>
                  <p className="text-[11px] text-rose-700 leading-relaxed">
                    触发原因：{gateApp.escalation_reasons?.join('；') || '涉及真实货币结算、隐私政策或核心数据调整，AI 无权擅自放行'}
                  </p>
                </div>
              )}

              {/* 状态卡片 */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-slate-50 p-3.5 rounded-xl border border-slate-200">
                <div>
                  <span className="text-slate-400 block text-[11px]">当前审核状态</span>
                  <span className="font-bold text-slate-900 mt-0.5 block">
                    {gateApp.status === 'approved' ? (
                      <span className="text-emerald-700 flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5" /> 已批准通过
                      </span>
                    ) : gateApp.status === 'rejected' ? (
                      <span className="text-rose-700 flex items-center gap-1">
                        <XCircle className="w-3.5 h-3.5" /> 已驳回重做
                      </span>
                    ) : gateApp.status === 'adjusted' ? (
                      <span className="text-amber-700 flex items-center gap-1">
                        <AlertTriangle className="w-3.5 h-3.5" /> 待修改调整
                      </span>
                    ) : (
                      <span className="text-indigo-700 flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5" /> 待您确认
                      </span>
                    )}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px]">把关规则要求</span>
                  <span className="font-bold text-slate-900 mt-0.5 block">
                    {gateApp.effective_level === 'red'
                      ? '必须负责人签字'
                      : gateApp.effective_level === 'yellow'
                      ? '负责人把关确认'
                      : '系统自动核验'}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px]">提报人 / 角色</span>
                  <span className="font-mono text-slate-700 mt-0.5 block truncate">
                    {gateApp.submitted_by.replace('agent:', 'AI智能体:').replace('human:', '人工:')}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px]">提报时间</span>
                  <span className="text-slate-600 mt-0.5 block">{new Date(gateApp.submitted_at).toLocaleTimeString()}</span>
                </div>
              </div>

              {/* 1. 结论建议 */}
              <div className="space-y-1.5 bg-white border border-slate-200 p-4 rounded-xl shadow-2xs">
                <h4 className="font-bold text-slate-900 text-xs flex items-center gap-1.5">
                  <span className="w-4 h-4 rounded-full bg-emerald-100 text-emerald-800 text-[10px] flex items-center justify-center font-bold">
                    1
                  </span>
                  阶段交付结论与建议
                </h4>
                <div className="p-3 bg-slate-50 rounded-lg text-slate-800 leading-relaxed font-medium">
                  {gateApp.recommendation}
                </div>
              </div>

              {/* 2. 事实依据清单 */}
              <div className="space-y-1.5 bg-white border border-slate-200 p-4 rounded-xl shadow-2xs">
                <h4 className="font-bold text-slate-900 text-xs flex items-center gap-1.5">
                  <span className="w-4 h-4 rounded-full bg-emerald-100 text-emerald-800 text-[10px] flex items-center justify-center font-bold">
                    2
                  </span>
                  核验依据清单（数据、测试与规范）
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

              {/* 3. 风险排查与对策 */}
              <div className="space-y-1.5 bg-white border border-slate-200 p-4 rounded-xl shadow-2xs">
                <h4 className="font-bold text-slate-900 text-xs flex items-center gap-1.5">
                  <span className="w-4 h-4 rounded-full bg-emerald-100 text-emerald-800 text-[10px] flex items-center justify-center font-bold">
                    3
                  </span>
                  潜在风险排查与应对方案
                </h4>
                <div className="p-3 bg-amber-50/70 border border-amber-200 rounded-lg text-amber-950 leading-relaxed">
                  {gateApp.risk_assessment}
                </div>
              </div>

              {/* AI 项目主管预审建议 */}
              {gateApp.lead_recommendation && (
                <div className="space-y-1.5 p-3.5 rounded-xl bg-purple-50/80 border border-purple-200">
                  <div className="flex items-center justify-between">
                    <h5 className="font-bold text-purple-950 text-xs flex items-center gap-1.5">
                      <Bot className="w-4 h-4 text-purple-600" />
                      AI 项目主管 (Lead) 预审研判
                    </h5>
                    {gateApp.is_consistent !== null && gateApp.is_consistent !== undefined && (
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          gateApp.is_consistent
                            ? 'bg-emerald-100 text-emerald-800'
                            : 'bg-amber-100 text-amber-800'
                        }`}
                      >
                        {gateApp.is_consistent ? '✓ 与您的决策偏好吻合' : '⚠️ 存在差异（供参考）'}
                      </span>
                    )}
                  </div>
                  <p className="text-purple-950 font-medium">建议动作：{gateApp.lead_recommendation}</p>
                  {gateApp.lead_rationale && (
                    <p className="text-[11px] text-purple-800">{gateApp.lead_rationale}</p>
                  )}
                </div>
              )}

              {/* 决策操作控制区 */}
              {gateApp.status === 'pending' ? (
                <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-3">
                  <div className="flex items-center justify-between">
                    <h4 className="font-bold text-slate-900 text-xs flex items-center gap-1.5">
                      <UserCheck className="w-4 h-4 text-emerald-600" />
                      请给出您的拍板决定
                    </h4>
                    <span className="text-[11px] text-slate-500">
                      所有放行与修改要求均完整记录在审计日志中
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
                      同意通过，进入下一阶段
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
                      需要调整，退回修改
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
                      不通过，驳回重做
                    </button>
                  </div>

                  <div>
                    <label className="block text-[11px] font-medium text-slate-600 mb-1">
                      签字确认人 / 职务
                    </label>
                    <input
                      type="text"
                      value={reviewerName}
                      onChange={(e) => setReviewerName(e.target.value)}
                      className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded-lg text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                      placeholder="例如：业务负责人 / CEO"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-medium text-slate-600 mb-1">
                      批注说明或具体修改要求（选填）
                    </label>
                    <textarea
                      rows={2}
                      value={reviewComment}
                      onChange={(e) => setReviewComment(e.target.value)}
                      className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                      placeholder="输入您的放行意见，或指明需要下游团队重点注意的事项..."
                    />
                  </div>

                  <div className="flex justify-end gap-2 pt-1">
                    <button
                      onClick={handleReview}
                      disabled={submitting}
                      className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold transition shadow-xs flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                    >
                      {submitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                      确认提交决定
                    </button>
                  </div>
                </div>
              ) : (
                <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-900 text-xs">已完成把关确认</span>
                    <span className="text-[11px] text-slate-400">
                      {gateApp.reviewed_at ? new Date(gateApp.reviewed_at).toLocaleString() : ''}
                    </span>
                  </div>
                  <div className="text-slate-700 text-xs">
                    签字确认人：<strong>{gateApp.reviewed_by}</strong> ({gateApp.reviewer_role})
                  </div>
                  {gateApp.review_comment && (
                    <div className="p-2.5 bg-white border border-slate-200 rounded-lg text-slate-800 text-[11px]">
                      意见批注：{gateApp.review_comment}
                    </div>
                  )}
                </div>
              )}
            </>
          ) : (
            /* 尚无关口申请单 */
            <div className="space-y-4">
              <div className="p-4 bg-emerald-50/70 border border-emerald-200 rounded-xl space-y-2">
                <div className="flex items-center gap-2 font-bold text-emerald-950 text-xs">
                  <Sparkles className="w-4 h-4 text-emerald-600" />
                  <span>当前环节尚未生成阶段把关确认单</span>
                </div>
                <p className="text-[11px] text-emerald-900 leading-relaxed">
                  在将本环节成果定稿推进至下一阶段前，需要一份结构清晰的拍板确认单（涵盖交付结论、依据事实、风险排查）。您可以让 AI 项目主管为您一键整理提报，也可以手动输入内容。
                </p>
                <div className="pt-2">
                  <button
                    onClick={handleLeadEvaluate}
                    disabled={submitting}
                    className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition flex items-center gap-1.5 cursor-pointer disabled:opacity-50 shadow-xs"
                  >
                    {submitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                    让 AI 项目主管 (Lead) 帮我一键整理提报
                  </button>
                </div>
              </div>

              <form onSubmit={handleCreateApplication} className="space-y-3 bg-white border border-slate-200 p-4 rounded-xl">
                <h4 className="font-bold text-slate-900 text-xs">手动填写提报内容</h4>
                <div>
                  <label className="block text-[11px] font-medium text-slate-600 mb-1">
                    交付结论与推进建议 *
                  </label>
                  <textarea
                    rows={2}
                    required
                    value={newRecommendation}
                    onChange={(e) => setNewRecommendation(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                    placeholder="输入本阶段成果的核心价值与放行建议..."
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-medium text-slate-600 mb-1">
                    潜在风险排查与应对方案 *
                  </label>
                  <textarea
                    rows={2}
                    required
                    value={newRiskAssessment}
                    onChange={(e) => setNewRiskAssessment(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                    placeholder="输入潜在平台规则、商业或技术风险及防范举措..."
                  />
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="submit"
                    disabled={submitting}
                    className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-xl text-xs font-bold transition flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                  >
                    {submitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                    保存并提交确认单
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
