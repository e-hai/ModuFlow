import React from 'react';
import {
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  DollarSign,
  Users,
  Target,
  ShieldAlert,
  HelpCircle,
  Briefcase
} from 'lucide-react';
import { ExecutiveCockpitResponse, FocusAlert } from '../../types';
import { MetricTooltip } from './MetricTooltip';
import { CockpitTabKey } from './CockpitHeader';

interface OverviewTabProps {
  cockpit: ExecutiveCockpitResponse;
  onNavigateTab: (tab: CockpitTabKey) => void;
  onEnterProductWorkbench: (productId: string) => void;
}

export const OverviewTab: React.FC<OverviewTabProps> = ({
  cockpit,
  onNavigateTab,
  onEnterProductWorkbench,
}) => {
  const { financials, focus_alerts, portfolio, marketing, operations } = cockpit;

  return (
    <div className="space-y-6">
      {/* 1. 经营核心指标带 (Top Ledger Ribbon) */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {/* 实际支出 */}
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs mb-1">
            <span className="flex items-center gap-1">
              累计实际支出
              <MetricTooltip
                title="累计实际支出 (Actual Paid)"
                definition="核算期内已实际向外部供应商、员工或服务商支付的真实银行现金流出，不包含尚未支付的合同承诺款。"
                accountingType="收付实现制 (Cash Basis)"
                formula="ActualPaid = 累计真实银行现金支付总额"
              />
            </span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-medium">实付现金</span>
          </div>
          <div className="text-xl font-bold text-slate-900 font-mono">
            ¥{financials.actual_paid.toLocaleString()}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">
            月消耗速率约 ¥{(financials.burn_rate_monthly / 1000).toFixed(1)}k
          </div>
        </div>

        {/* 实际回款 */}
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs mb-1">
            <span className="flex items-center gap-1">
              累计实际回款
              <MetricTooltip
                title="累计实际回款 (Cash Collected)"
                definition="银行账户已实际收到的现金流水，不含应收未收账款、尚未结算的在途资金。"
                accountingType="收付实现制 (Cash Basis)"
                formula="CashCollected = 累计银行现金实际入账总额"
              />
            </span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 font-medium">到账资金</span>
          </div>
          <div className="text-xl font-bold text-emerald-600 font-mono">
            ¥{financials.cash_collected.toLocaleString()}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">
            权责收入 ¥{(financials.revenue_recognized / 10000).toFixed(1)}万
          </div>
        </div>

        {/* 净现金流 */}
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs mb-1">
            <span className="flex items-center gap-1">
              累计净现金流
              <MetricTooltip
                title="累计净现金流 (Net Cash Flow)"
                definition="实际回款现金减去实际支出后沉淀的真实净资金。当此值大于等于 0 时，代表该战役在现金流层面已累计回本。"
                accountingType="收付实现制 (Cash Basis)"
                formula="NetCashFlow = CashCollected - ActualPaid"
              />
            </span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 font-medium">回本指标</span>
          </div>
          <div
            className={`text-xl font-bold font-mono ${
              financials.net_cash_flow >= 0 ? 'text-emerald-600' : 'text-rose-600'
            }`}
          >
            {financials.net_cash_flow >= 0 ? '+' : ''}¥{financials.net_cash_flow.toLocaleString()}
          </div>
          <div className="text-[11px] text-emerald-600 font-medium mt-1 flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3" />
            现金流已累计转正
          </div>
        </div>

        {/* 经营预警数 */}
        <div
          onClick={() => onNavigateTab('decisions')}
          className="bg-white border border-slate-200 hover:border-amber-300 rounded-xl p-4 shadow-xs cursor-pointer transition group"
        >
          <div className="flex items-center justify-between text-slate-500 text-xs mb-1">
            <span>量化经营预警</span>
            <AlertTriangle className="w-4 h-4 text-amber-500" />
          </div>
          <div className="text-xl font-bold text-amber-600 font-mono">
            {cockpit.risks.length} 项
          </div>
          <div className="text-[11px] text-slate-400 group-hover:text-amber-700 mt-1 flex items-center justify-between transition">
            <span>需关注业务偏差</span>
            <span>查看 &gt;</span>
          </div>
        </div>

        {/* 待拍板决策 */}
        <div
          onClick={() => onNavigateTab('decisions')}
          className="bg-white border border-slate-200 hover:border-emerald-300 rounded-xl p-4 shadow-xs cursor-pointer transition group"
        >
          <div className="flex items-center justify-between text-slate-500 text-xs mb-1">
            <span>待 CEO 拍板</span>
            <ShieldAlert className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-xl font-bold text-slate-900 font-mono">
            {cockpit.decisions.filter((d) => d.status === 'proposed').length} 件
          </div>
          <div className="text-[11px] text-slate-400 group-hover:text-emerald-700 mt-1 flex items-center justify-between transition">
            <span>结构化 AI 决策方案</span>
            <span>审批 &gt;</span>
          </div>
        </div>
      </div>

      {/* 2. CEO 本期 3 大焦点卡片 (Focus Cards) */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <Target className="w-4 h-4 text-emerald-600" />
            CEO 本期焦点经营议题 (Focus Issues)
          </h2>
          <span className="text-xs text-slate-400">基于最新经营数据自动研判并触发</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {focus_alerts.map((alert) => {
            const isWarning = alert.severity === 'warning';
            const isCritical = alert.severity === 'critical';
            return (
              <div
                key={alert.id}
                className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs flex flex-col justify-between space-y-3 hover:shadow-md transition"
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span
                      className={`text-[10px] font-semibold px-2 py-0.5 rounded uppercase tracking-wider font-mono ${
                        isCritical
                          ? 'bg-rose-50 text-rose-700 border border-rose-200'
                          : isWarning
                          ? 'bg-amber-50 text-amber-700 border border-amber-200'
                          : 'bg-blue-50 text-blue-700 border border-blue-200'
                      }`}
                    >
                      {alert.type}
                    </span>
                    <span className="text-[11px] text-slate-400 font-mono">{alert.id}</span>
                  </div>

                  <h3 className="text-xs font-bold text-slate-900 leading-snug">{alert.title}</h3>
                  <p className="text-[11px] text-slate-600 leading-relaxed">{alert.summary}</p>
                </div>

                <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
                  <span className="text-[11px] text-slate-500 font-medium">
                    {alert.action_hint || '建议进入模块评估'}
                  </span>
                  <button
                    onClick={() => {
                      if (alert.type === 'cac_spike') onNavigateTab('marketing');
                      else if (alert.type === 'breakeven_delayed') onNavigateTab('finance');
                      else onNavigateTab('decisions');
                    }}
                    className="text-xs text-emerald-700 hover:text-emerald-800 font-semibold flex items-center gap-1 group cursor-pointer"
                  >
                    处理
                    <ArrowRight className="w-3 h-3 group-hover:translate-x-0.5 transition" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 3. 核心经营结果矩阵 (Core Business Results Matrix) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 产品组合投资与 KPI */}
        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
              <Briefcase className="w-4 h-4 text-emerald-600" />
              产品组合投资与表现
            </h3>
            <button
              onClick={() => onNavigateTab('portfolio')}
              className="text-[11px] text-emerald-700 hover:text-emerald-800 font-semibold"
            >
              全部 {portfolio.length} 款 &gt;
            </button>
          </div>

          <div className="space-y-3">
            {portfolio.map((prod) => (
              <div
                key={prod.id}
                className="p-3 rounded-xl bg-slate-50 border border-slate-200 hover:border-emerald-300 transition space-y-2"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-slate-900">{prod.code}</span>
                    <span className="text-xs text-slate-700">{prod.name}</span>
                  </div>
                  <span className="text-[10px] px-1.5 py-0.2 rounded font-medium bg-emerald-100 text-emerald-800">
                    {prod.strategic_role === 'acquisition'
                      ? '获客前端'
                      : prod.strategic_role === 'monetization'
                      ? '商业变现'
                      : '战略底座'}
                  </span>
                </div>

                {prod.kpi_name && (
                  <div className="text-[11px] text-slate-600 flex items-center justify-between">
                    <span>
                      {prod.kpi_name}: <span className="font-mono font-semibold text-slate-800">{prod.kpi_actual?.toLocaleString()}</span> / {prod.kpi_target?.toLocaleString()} {prod.kpi_unit}
                    </span>
                    <span className="font-mono font-bold text-emerald-700">{prod.kpi_completion_rate}%</span>
                  </div>
                )}

                <div className="w-full bg-slate-200 rounded-full h-1.5 overflow-hidden">
                  <div
                    className="bg-emerald-500 h-1.5 rounded-full"
                    style={{ width: `${Math.min(100, prod.kpi_completion_rate || 0)}%` }}
                  />
                </div>

                <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1">
                  <span>
                    支出: <span className="font-mono text-slate-800">¥{(prod.actual_spent / 1000).toFixed(0)}k</span>
                  </span>
                  <span>
                    贡献: <span className="font-mono text-emerald-700 font-semibold">¥{(prod.revenue_contribution / 1000).toFixed(0)}k</span>
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 推广获客效率 */}
        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
              <TrendingUp className="w-4 h-4 text-emerald-600" />
              推广增长与渠道转化
            </h3>
            <button
              onClick={() => onNavigateTab('marketing')}
              className="text-[11px] text-emerald-700 hover:text-emerald-800 font-semibold"
            >
              明细分析 &gt;
            </button>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
              <span className="text-[11px] text-slate-500 block">有效新增用户</span>
              <span className="text-lg font-bold text-slate-900 font-mono">
                {marketing.effective_new_users.toLocaleString()}
              </span>
              <span className="text-[10px] text-slate-400 block mt-0.5">真实验真留存用户</span>
            </div>
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
              <span className="text-[11px] text-slate-500 block">加权综合 CAC</span>
              <span className="text-lg font-bold text-slate-900 font-mono">
                ¥{marketing.blended_cac.toFixed(2)}
              </span>
              <span className="text-[10px] text-emerald-600 block mt-0.5">基准目标 ≤ ¥15.0</span>
            </div>
          </div>

          <div className="space-y-2">
            <span className="text-[11px] font-semibold text-slate-700 block">三大获客机制表现</span>
            {marketing.categories?.map((cat) => (
              <div key={cat.category_code} className="flex items-center justify-between text-xs py-1 border-b border-slate-100 last:border-0">
                <div className="flex items-center gap-1.5 truncate max-w-[140px]">
                  <span className="text-slate-800 font-medium truncate">{cat.category_name.split(' ')[0]}</span>
                  <span className="text-[10px] text-slate-400 font-mono">({cat.user_share_percent}%)</span>
                </div>
                <span className="font-mono text-slate-900 text-[11px]">CAC: ¥{cat.cac.toFixed(1)}</span>
                <span
                  className={`text-[10px] font-semibold px-1.5 py-0.2 rounded ${
                    cat.decision_recommendation.includes('扩大') || cat.decision_recommendation.includes('分享')
                      ? 'bg-emerald-50 text-emerald-700'
                      : 'bg-rose-50 text-rose-700'
                  }`}
                >
                  {cat.decision_recommendation.split('，')[0]}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* 运营黏性与商业健康度 */}
        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
              <Users className="w-4 h-4 text-emerald-600" />
              运营黏性与商业健康度
            </h3>
            <button
              onClick={() => onNavigateTab('operations')}
              className="text-[11px] text-emerald-700 hover:text-emerald-800 font-semibold"
            >
              漏斗详情 &gt;
            </button>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
              <span className="text-[11px] text-slate-500 block">DAU / MAU</span>
              <span className="text-lg font-bold text-slate-900 font-mono">
                {(operations.dau / 1000).toFixed(1)}k / {(operations.mau / 1000).toFixed(1)}k
              </span>
              <span className="text-[10px] text-slate-400 block mt-0.5">
                黏度 {((operations.dau / (operations.mau || 1)) * 100).toFixed(1)}%
              </span>
            </div>

            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
              <span className="text-[11px] text-slate-500 flex items-center gap-1">
                LTV / CAC 倍数
                <MetricTooltip
                  title="LTV / CAC 倍数"
                  definition="用户生命周期价值 (LTV) 与获取该用户的成本 (CAC) 的比值。国际通用标准：> 3.0x 代表商业模式具备自造血并可规模化扩量；< 1.0x 代表买量亏损。"
                  formula="LTV / CAC = LTV / BlendedCAC"
                />
              </span>
              <span className="text-lg font-bold text-emerald-600 font-mono">
                {operations.ltv_cac_ratio.toFixed(2)}x
              </span>
              <span className="text-[10px] text-emerald-600 block mt-0.5">健康强劲 (&gt; 3.0x)</span>
            </div>
          </div>

          <div className="space-y-1.5">
            <span className="text-[11px] font-semibold text-slate-700 block">留存 Cohort 达成</span>
            <div className="grid grid-cols-3 gap-2 text-center text-xs">
              <div className="p-2 bg-slate-50 rounded-lg border border-slate-200">
                <span className="text-[10px] text-slate-400 block">次日留存</span>
                <span className="font-mono font-bold text-slate-900">{operations.retention_1d}%</span>
              </div>
              <div className="p-2 bg-slate-50 rounded-lg border border-slate-200">
                <span className="text-[10px] text-slate-400 block">7日留存</span>
                <span className="font-mono font-bold text-slate-900">{operations.retention_7d}%</span>
              </div>
              <div className="p-2 bg-slate-50 rounded-lg border border-slate-200">
                <span className="text-[10px] text-slate-400 block">30日留存</span>
                <span className="font-mono font-bold text-slate-900">{operations.retention_30d}%</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
