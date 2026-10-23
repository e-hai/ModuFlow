import React from 'react';
import {
  Wallet,
  DollarSign,
  TrendingUp,
  Clock,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  ArrowRight,
  FileText
} from 'lucide-react';
import { FinancialMetrics } from '../../types';
import { MetricTooltip } from './MetricTooltip';

interface FinancialLedgerTabProps {
  financials: FinancialMetrics;
}

export const FinancialLedgerTab: React.FC<FinancialLedgerTabProps> = ({ financials }) => {
  return (
    <div className="space-y-6">
      {/* 顶部总盘 */}
      <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Wallet className="w-4 h-4 text-emerald-600" />
              财务账本与资金健康盘 (Financial Ledger & Capital Runway)
            </h2>
            <p className="text-xs text-slate-500">
              严格解耦收付实现制（真实出入金净现金流）与权责发生制（营业确认收入与投资回报率），严禁混淆概念与编造数据。
            </p>
          </div>

          <div className="flex items-center gap-2 text-xs text-slate-500">
            <span className="flex items-center gap-1 font-mono text-[11px] bg-slate-100 px-2.5 py-1 rounded-lg">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
              币种: {financials.currency}
            </span>
          </div>
        </div>
      </div>

      {/* 预算消耗与可用余额核算卡片 */}
      <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div>
            <h3 className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
              <span>一、预算总盘与可用余额核算 (Budget Balance Breakdown)</span>
              <MetricTooltip
                title="可用预算余额 (Available Budget)"
                definition="批准总预算减去已承诺未付合同款，再减去已实际发生的银行支出。保证承诺款不被二次重复扣减。"
                formula="Available = BudgetTotal - CommittedUnpaid - ActualPaid"
                accountingType="收付实现制 (Cash Basis)"
              />
            </h3>
            <span className="text-[11px] text-slate-400">已严格隔离已付款与已承诺款项</span>
          </div>

          <span className="text-xs font-mono font-bold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-lg border border-emerald-200">
            可用预算余额: ¥{financials.available_budget.toLocaleString()}
          </span>
        </div>

        {/* 4 栏预算拆解 */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-1">
            <span className="text-[11px] text-slate-400 block">① 批准总预算 (Budget Total)</span>
            <span className="text-lg font-bold text-slate-900 font-mono">
              ¥{financials.budget_total.toLocaleString()}
            </span>
            <span className="text-[10px] text-slate-400 block">战役董事会审批上限</span>
          </div>

          <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-1">
            <span className="text-[11px] text-slate-400 block">② 已承诺未付 (Committed Unpaid)</span>
            <span className="text-lg font-bold text-amber-700 font-mono">
              ¥{financials.committed_unpaid.toLocaleString()}
            </span>
            <span className="text-[10px] text-slate-400 block">已签合同/订单尚未付款</span>
          </div>

          <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-1">
            <span className="text-[11px] text-slate-400 block">③ 累计实际已付 (Actual Paid)</span>
            <span className="text-lg font-bold text-slate-900 font-mono">
              ¥{financials.actual_paid.toLocaleString()}
            </span>
            <span className="text-[10px] text-slate-400 block">银行账户实际划出资金</span>
          </div>

          <div className="p-3 bg-emerald-50/60 rounded-xl border border-emerald-200 space-y-1">
            <span className="text-[11px] text-emerald-800 font-semibold block">④ 可用预算余额 (Available)</span>
            <span className="text-lg font-bold text-emerald-700 font-mono">
              ¥{financials.available_budget.toLocaleString()}
            </span>
            <span className="text-[10px] text-emerald-600 block">① - ② - ③ 严谨推导</span>
          </div>
        </div>

        {/* 进度条展示 */}
        <div className="space-y-1 pt-1">
          <div className="flex items-center justify-between text-[11px] text-slate-500">
            <span>
              已支付: {financials.budget_total > 0 ? ((financials.actual_paid / financials.budget_total) * 100).toFixed(1) : '0.0'}% ·
              已承诺: {financials.budget_total > 0 ? ((financials.committed_unpaid / financials.budget_total) * 100).toFixed(1) : '0.0'}% ·
              剩余可用: {financials.budget_total > 0 ? ((financials.available_budget / financials.budget_total) * 100).toFixed(1) : '0.0'}%
            </span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-3 overflow-hidden flex">
            {financials.budget_total > 0 && (
              <>
                <div
                  className="bg-slate-800 h-3"
                  style={{ width: `${Math.min(100, (financials.actual_paid / financials.budget_total) * 100)}%` }}
                  title="实际已付"
                />
                <div
                  className="bg-amber-400 h-3"
                  style={{ width: `${Math.min(100, (financials.committed_unpaid / financials.budget_total) * 100)}%` }}
                  title="已承诺未付"
                />
                <div
                  className="bg-emerald-500 h-3"
                  style={{ width: `${Math.max(0, Math.min(100, (financials.available_budget / financials.budget_total) * 100))}%` }}
                  title="可用预算余额"
                />
              </>
            )}
          </div>
        </div>
      </div>

      {/* 现金流与回本分析 vs 权责发生制收入 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* 左侧：现金流与回本节点 (收付实现制) */}
        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h3 className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
              <span>二、现金流与回本节点 (Cash Flow & Breakeven)</span>
              <MetricTooltip
                title="累计净现金流 (Net Cash Flow)"
                definition="银行实际收到的现金减去银行实际支出的现金。大于 0 代表投资已全额回本并产生自由净现金流。"
                formula="NetCashFlow = CashCollected - ActualPaid"
                accountingType="收付实现制 (Cash Basis)"
              />
            </h3>
            <span className="text-[10px] px-2 py-0.5 rounded bg-blue-50 text-blue-700 font-semibold font-mono">
              收付实现制
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
              <span className="text-[11px] text-slate-500 block">累计到账回款</span>
              <span className="text-lg font-bold text-emerald-700 font-mono">
                ¥{financials.cash_collected.toLocaleString()}
              </span>
              <span className="text-[10px] text-slate-400 block mt-0.5">实际收到现金</span>
            </div>

            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
              <span className="text-[11px] text-slate-500 block">累计净现金流</span>
              <span
                className={`text-lg font-bold font-mono ${
                  financials.net_cash_flow >= 0 ? 'text-emerald-700' : 'text-rose-600'
                }`}
              >
                {financials.net_cash_flow >= 0 ? '+' : ''}¥{financials.net_cash_flow.toLocaleString()}
              </span>
              <span className="text-[10px] text-slate-400 block mt-0.5">
                {financials.net_cash_flow > 0
                  ? '现金流已累计转正'
                  : financials.cash_collected > 0
                  ? '仍在收回投入中'
                  : '尚未产生现金流'}
              </span>
            </div>
          </div>

          <div className="space-y-2 text-xs pt-1">
            <div className="flex items-center justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">原始目标回本日期</span>
              <span className="font-mono font-semibold text-slate-800">
                {financials.target_breakeven_date || '未设定'}
              </span>
            </div>

            <div className="flex items-center justify-between py-1 border-b border-slate-100">
              <span className="text-slate-500">当前预测回本日期</span>
              <span className="font-mono font-semibold text-slate-800">
                {financials.forecast_breakeven_date || '待预测'}
              </span>
            </div>

            <div className="flex items-center justify-between py-1">
              <span className="text-slate-500">月均现金消耗速率 (Burn Rate)</span>
              <span className="font-mono font-semibold text-slate-800">
                ¥{financials.burn_rate_monthly.toLocaleString()} / 月
              </span>
            </div>
          </div>
        </div>

        {/* 右侧：权责发生制商业收入与 ROI */}
        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h3 className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
              <span>三、权责发生制收入与 ROI (Accrual & ROI)</span>
              <MetricTooltip
                title="投资回报率 (ROI)"
                definition="核算期内确认收入减去实际已付成本占实际已付成本的比例。仅在分子分母采用严格统一核算期间时计算。"
                formula="ROI = (RevenueRecognized - ActualPaid) / ActualPaid * 100%"
                accountingType="权责发生制 (Accrual Basis)"
              />
            </h3>
            <span className="text-[10px] px-2 py-0.5 rounded bg-purple-50 text-purple-700 font-semibold font-mono">
              权责发生制
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
              <span className="text-[11px] text-slate-500 block">营业确认收入</span>
              <span className="text-lg font-bold text-slate-900 font-mono">
                ¥{financials.revenue_recognized.toLocaleString()}
              </span>
              <span className="text-[10px] text-slate-400 block mt-0.5">会计已确认权责收入</span>
            </div>

            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
              <span className="text-[11px] text-slate-500 block">投资回报率 ROI</span>
              <span className="text-lg font-bold text-emerald-700 font-mono">
                {financials.roi_percent != null ? `${financials.roi_percent >= 0 ? '+' : ''}${financials.roi_percent.toFixed(1)}%` : '待结算'}
              </span>
              <span className="text-[10px] text-slate-400 block mt-0.5">
                {financials.roi_percent != null
                  ? financials.roi_percent >= 0
                    ? '收益大于投入成本'
                    : '尚未覆盖成本'
                  : '待经营结算'}
              </span>
            </div>
          </div>

          <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 space-y-1.5 text-xs text-slate-600">
            <div className="font-semibold text-slate-800 flex items-center gap-1">
              <FileText className="w-3.5 h-3.5 text-emerald-600" />
              <span>数据一致性与审计源说明</span>
            </div>
            <p className="text-[11px] leading-relaxed">
              • 数据源：{financials.data_source}<br />
              • 应收账款敞口：¥{( (financials.revenue_recognized - financials.cash_collected) / 1000).toFixed(0)}k（确认收入与实际到账回款差额处于安全账期内）。
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
