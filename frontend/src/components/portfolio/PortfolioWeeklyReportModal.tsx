import React, { useState, useEffect } from 'react';
import { PortfolioWeeklyReport } from '../../types';
import { api } from '../../services/api';
import {
  X,
  Layers,
  DollarSign,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  ShieldAlert,
  Loader2,
  FileText,
  AlertCircle
} from 'lucide-react';

interface PortfolioWeeklyReportModalProps {
  initiativeId?: string;
  isOpen: boolean;
  onClose: () => void;
}

export const PortfolioWeeklyReportModal: React.FC<PortfolioWeeklyReportModalProps> = ({
  initiativeId,
  isOpen,
  onClose,
}) => {
  const [report, setReport] = useState<PortfolioWeeklyReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadReport();
    }
  }, [isOpen, initiativeId]);

  const loadReport = async () => {
    try {
      setLoading(true);
      setErrorMsg(null);
      const data = await api.getPortfolioWeeklyReport(initiativeId);
      setReport(data);
    } catch (err: any) {
      console.error('Failed to load portfolio weekly report:', err);
      setErrorMsg(err.message || '加载投资周报失败');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-white border border-slate-200 w-full max-w-4xl rounded-2xl shadow-2xl overflow-hidden my-8 max-h-[90vh] flex flex-col">
        {/* 顶部标题栏 */}
        <div className="p-5 border-b border-slate-100 flex items-center justify-between bg-emerald-50/70">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-100 border border-emerald-200 flex items-center justify-center text-emerald-700 shrink-0">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs px-2 py-0.5 rounded bg-emerald-200 text-emerald-900 font-bold">
                  Portfolio Weekly
                </span>
                <h3 className="font-bold text-slate-900 text-base">
                  CEO 一页纸投资组合周报 (Executive Portfolio Digest)
                </h3>
              </div>
              <p className="text-xs text-emerald-800 mt-0.5">
                自下而上聚合各产品花费、生命周期阶段、生死假设与经营建议
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
            <div className="py-20 text-center text-slate-400 space-y-2">
              <Loader2 className="w-6 h-6 animate-spin mx-auto text-emerald-600" />
              <p>正在自下而上聚合矩阵产品投资数据...</p>
            </div>
          ) : report ? (
            <>
              {/* ⚠️ 绝对红线告知栏 */}
              <div className="p-3.5 rounded-xl bg-slate-900 text-white flex items-center gap-3">
                <ShieldAlert className="w-5 h-5 text-amber-400 shrink-0" />
                <div className="text-[11px] leading-relaxed">
                  <span className="font-bold text-amber-400">人类战略层硬红线保护：</span>{' '}
                  {report.redline_notice ||
                    '投资组合分析器仅具备建议权，严格禁止自主调拨项目资金或自主执行项目关闭！所有注资与关停决策严格归属人类战略层。'}
                </div>
              </div>

              {/* 顶层宏观大盘 */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-slate-50 p-4 rounded-xl border border-slate-200">
                <div>
                  <span className="text-slate-400 block text-[11px]">矩阵产品总数</span>
                  <span className="font-bold text-slate-900 text-base">{report.total_products} 款</span>
                  <span className="text-[10px] text-slate-500 block">
                    健康: <strong className="text-emerald-700">{report.healthy_count}</strong> · 预警: <strong className="text-amber-700">{report.risky_count}</strong>
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px]">投资组合总预算</span>
                  <span className="font-mono font-bold text-slate-900 text-base">
                    ${report.total_budget_usd?.toLocaleString()}
                  </span>
                  <span className="text-[10px] text-slate-500 block">各产品授权包注资总和</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px]">累计实际已支出</span>
                  <span className="font-mono font-bold text-amber-900 text-base">
                    ${report.total_spent_usd?.toLocaleString()}
                  </span>
                  <span className="text-[10px] text-slate-500 block">包含研发/买量/基础设施</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px]">总体资金消耗率</span>
                  <span className="font-mono font-bold text-emerald-800 text-base">
                    {report.budget_utilization_rate}%
                  </span>
                  <span className="text-[10px] text-slate-500 block">总花费 / 总预算</span>
                </div>
              </div>

              {/* 矩阵产品横向对比表 */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="font-bold text-slate-900 text-xs">矩阵产品健康度与建议矩阵</h4>
                  <span className="text-[11px] text-slate-400">
                    生成时间: {new Date(report.generated_at).toLocaleString()}
                  </span>
                </div>

                <div className="border border-slate-200 rounded-xl overflow-hidden">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-slate-100/75 border-b border-slate-200 text-[11px] text-slate-600 font-semibold">
                        <th className="py-2.5 px-3">产品代号</th>
                        <th className="py-2.5 px-3">产品名称</th>
                        <th className="py-2.5 px-3">阶段</th>
                        <th className="py-2.5 px-3 text-right">已耗 / 预算</th>
                        <th className="py-2.5 px-3 text-right">消耗率</th>
                        <th className="py-2.5 px-3">止损触发</th>
                        <th className="py-2.5 px-3">决策建议</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 text-[11px]">
                      {report.products_summary?.map((prod) => (
                        <tr key={prod.product_code} className="hover:bg-slate-50/80 transition">
                          <td className="py-2.5 px-3 font-mono font-bold text-slate-900">
                            {prod.product_code}
                          </td>
                          <td className="py-2.5 px-3 font-medium text-slate-800">{prod.name}</td>
                          <td className="py-2.5 px-3">
                            <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 text-[10px] font-semibold">
                              {prod.stage}
                            </span>
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono">
                            ${prod.spent?.toLocaleString()} / ${prod.budget?.toLocaleString()}
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono font-bold">
                            <span
                              className={
                                prod.burn_percent > 90
                                  ? 'text-rose-600'
                                  : prod.burn_percent > 70
                                  ? 'text-amber-600'
                                  : 'text-emerald-600'
                              }
                            >
                              {prod.burn_percent}%
                            </span>
                          </td>
                          <td className="py-2.5 px-3">
                            {prod.kill_criteria_hit ? (
                              <span className="px-1.5 py-0.5 rounded bg-rose-100 text-rose-800 font-bold text-[10px]">
                                命中退出条件
                              </span>
                            ) : (
                              <span className="text-slate-400 text-[10px]">正常</span>
                            )}
                          </td>
                          <td className="py-2.5 px-3 font-medium text-slate-900">
                            {prod.recommendation}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* CEO 战略建议清单 */}
              {report.strategic_recommendations && report.strategic_recommendations.length > 0 && (
                <div className="p-4 rounded-xl bg-emerald-50/70 border border-emerald-200 space-y-2">
                  <h4 className="font-bold text-emerald-950 text-xs flex items-center gap-1.5">
                    <TrendingUp className="w-4 h-4 text-emerald-700" />
                    CEO 战略推进与投资组合建议
                  </h4>
                  <ul className="space-y-1 pl-1">
                    {report.strategic_recommendations.map((rec, idx) => (
                      <li key={idx} className="flex items-start gap-2 text-emerald-900 text-xs">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />
                        <span>{rec}</span>
                      </li>
                    ))}
                  </ul>
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
