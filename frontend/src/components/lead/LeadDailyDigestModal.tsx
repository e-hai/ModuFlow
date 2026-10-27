import React, { useState, useEffect } from 'react';
import { ProjectDailyDigest } from '../../types';
import { api } from '../../services/api';
import {
  X,
  Bot,
  Calendar,
  Layers,
  DollarSign,
  Clock,
  AlertCircle,
  CheckCircle2,
  FileText,
  Loader2,
  Sparkles
} from 'lucide-react';

interface LeadDailyDigestModalProps {
  productId: string;
  productCode: string;
  isOpen: boolean;
  onClose: () => void;
}

export const LeadDailyDigestModal: React.FC<LeadDailyDigestModalProps> = ({
  productId,
  productCode,
  isOpen,
  onClose,
}) => {
  const [digest, setDigest] = useState<ProjectDailyDigest | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && productId) {
      loadDigest();
    }
  }, [isOpen, productId]);

  const loadDigest = async () => {
    try {
      setLoading(true);
      setErrorMsg(null);
      const data = await api.getProjectDailyDigest(productId);
      setDigest(data);
    } catch (err: any) {
      console.error('Failed to load project daily digest:', err);
      setErrorMsg(err.message || '加载项目简报失败');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-white border border-slate-200 w-full max-w-2xl rounded-2xl shadow-2xl overflow-hidden my-8 max-h-[90vh] flex flex-col">
        {/* 顶部标题栏 */}
        <div className="p-5 border-b border-slate-100 flex items-center justify-between bg-purple-50/60">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-purple-100 border border-purple-200 flex items-center justify-center text-purple-700 shrink-0">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs px-2 py-0.5 rounded bg-purple-100 text-purple-900 font-bold">
                  {productCode}
                </span>
                <h3 className="font-bold text-slate-900 text-base">项目每日简报 (Lead Daily Digest)</h3>
              </div>
              <p className="text-xs text-purple-800 mt-0.5">
                由项目总控 Agent (lead) 自动汇总编排推进状况与风险预警
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

        {/* 错误提示 */}
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

        {/* 主内容 */}
        <div className="p-6 overflow-y-auto space-y-5 flex-1 text-xs text-slate-700">
          {loading ? (
            <div className="py-16 text-center text-slate-400 space-y-2">
              <Loader2 className="w-6 h-6 animate-spin mx-auto text-purple-600" />
              <p>项目总控 (Lead) 正在整理今日进展...</p>
            </div>
          ) : digest ? (
            <>
              {/* 元数据卡片 */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-slate-50 p-3.5 rounded-xl border border-slate-200">
                <div>
                  <span className="text-slate-400 block text-[11px]">简报日期</span>
                  <span className="font-bold text-slate-900 flex items-center gap-1">
                    <Calendar className="w-3.5 h-3.5 text-slate-500" />
                    {digest.date}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px]">编写主体</span>
                  <span className="font-mono font-bold text-purple-800">{digest.author}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px]">活跃迭代</span>
                  <span className="font-bold text-slate-900 truncate block">
                    {digest.active_run_name || '无活跃迭代'}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px]">模板工序</span>
                  <span className="font-mono text-slate-600">{digest.template_id || '标准工序'}</span>
                </div>
              </div>

              {/* 核心指标仪表 */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="p-4 rounded-xl bg-white border border-slate-200 space-y-2 shadow-2xs">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-900 text-xs flex items-center gap-1.5">
                      <Layers className="w-4 h-4 text-emerald-600" />
                      工序推进达成率
                    </span>
                    <span className="font-mono font-bold text-emerald-800">
                      {digest.stage_progress.completion_rate_percent}%
                    </span>
                  </div>
                  <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden border border-slate-200">
                    <div
                      className="bg-emerald-500 h-2 transition-all duration-500"
                      style={{ width: `${digest.stage_progress.completion_rate_percent}%` }}
                    />
                  </div>
                  <div className="text-[11px] text-slate-500 flex justify-between">
                    <span>已定稿基线: {digest.stage_progress.baselined_modules} 环节</span>
                    <span>全部工序: {digest.stage_progress.total_modules} 环节</span>
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-white border border-slate-200 space-y-2 shadow-2xs">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-900 text-xs flex items-center gap-1.5">
                      <DollarSign className="w-4 h-4 text-amber-600" />
                      预算额度消耗
                    </span>
                    <span className="font-mono font-bold text-amber-800">
                      {digest.budget_status.burn_percent}%
                    </span>
                  </div>
                  <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden border border-slate-200">
                    <div
                      className="bg-amber-500 h-2 transition-all duration-500"
                      style={{ width: `${Math.min(digest.budget_status.burn_percent, 100)}%` }}
                    />
                  </div>
                  <div className="text-[11px] text-slate-500 flex justify-between">
                    <span>已耗花费: ${digest.budget_status.spent.toLocaleString()}</span>
                    <span>授权总预算: ${digest.budget_status.budget.toLocaleString()}</span>
                  </div>
                </div>
              </div>

              {/* Lead 综合评估 */}
              <div className="p-4 bg-purple-50/70 border border-purple-200 rounded-xl space-y-1.5">
                <h4 className="font-bold text-purple-950 text-xs flex items-center gap-1.5">
                  <Sparkles className="w-4 h-4 text-purple-700" />
                  项目总控 (Lead) 今日核心研判
                </h4>
                <p className="text-purple-900 leading-relaxed font-medium">
                  {digest.lead_assessment}
                </p>
              </div>

              {/* 今日推进日志 */}
              <div className="space-y-2">
                <h4 className="font-bold text-slate-900 text-xs flex items-center gap-1.5">
                  <Clock className="w-4 h-4 text-slate-600" />
                  今日重点动态与产出 ({digest.today_events?.length || 0})
                </h4>
                {digest.today_events && digest.today_events.length > 0 ? (
                  <div className="space-y-1.5">
                    {digest.today_events.map((evt, idx) => (
                      <div
                        key={idx}
                        className="p-3 bg-white border border-slate-200 rounded-xl flex items-start gap-2.5 shadow-2xs"
                      >
                        <span className="font-mono text-[10px] text-slate-400 shrink-0 pt-0.5">
                          {evt.time}
                        </span>
                        <span className="font-mono text-[11px] px-1.5 py-0.5 bg-slate-100 text-slate-700 rounded font-semibold shrink-0">
                          {evt.module_code}
                        </span>
                        <div className="flex-1">
                          <span className="font-semibold text-slate-900 block">{evt.summary}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-slate-400 text-center py-4 bg-slate-50 rounded-xl border border-dashed border-slate-200">
                    今日暂无新发生的工序状态变更
                  </p>
                )}
              </div>

              {/* 待办风险事项 */}
              {digest.pending_items && digest.pending_items.length > 0 && (
                <div className="space-y-2">
                  <h4 className="font-bold text-slate-900 text-xs flex items-center gap-1.5">
                    <AlertCircle className="w-4 h-4 text-amber-600" />
                    需关注卡点与待决事项 ({digest.pending_items.length})
                  </h4>
                  <div className="space-y-1.5">
                    {digest.pending_items.map((item, idx) => (
                      <div
                        key={idx}
                        className="p-3 bg-amber-50/70 border border-amber-200 rounded-xl flex items-center justify-between gap-3 text-amber-950"
                      >
                        <div className="flex items-center gap-2">
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-200 text-amber-900">
                            {item.item_type}
                          </span>
                          <span className="font-medium text-xs">{item.title}</span>
                        </div>
                        <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-white text-amber-800 border border-amber-300">
                          {item.urgency}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : null}
        </div>

        {/* 底部按钮栏 */}
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
