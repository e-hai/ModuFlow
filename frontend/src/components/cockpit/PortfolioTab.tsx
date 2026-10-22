import React from 'react';
import {
  Layers,
  Plus,
  ArrowRight,
  TrendingUp,
  DollarSign,
  AlertCircle,
  CheckCircle2,
  Sliders,
  ShieldAlert,
  HelpCircle
} from 'lucide-react';
import { PortfolioProductItem, Product } from '../../types';
import { MetricTooltip } from './MetricTooltip';

interface PortfolioTabProps {
  portfolio: PortfolioProductItem[];
  products: Product[];
  onOpenNewProductModal: () => void;
  onEnterProductWorkbench: (product: Product) => void;
}

export const PortfolioTab: React.FC<PortfolioTabProps> = ({
  portfolio,
  products,
  onOpenNewProductModal,
  onEnterProductWorkbench,
}) => {
  const getStrategicRoleBadge = (role: string) => {
    switch (role) {
      case 'acquisition':
        return { label: '获客前端 (流量入口)', bg: 'bg-blue-50 text-blue-700 border-blue-200' };
      case 'monetization':
        return { label: '变现中枢 (商业盈利)', bg: 'bg-emerald-50 text-emerald-700 border-emerald-200' };
      case 'retention':
        return { label: '留存底座 (长期黏性)', bg: 'bg-purple-50 text-purple-700 border-purple-200' };
      case 'validation':
        return { label: '模式验证 (探索试验)', bg: 'bg-amber-50 text-amber-700 border-amber-200' };
      case 'infra':
        return { label: '公共基建 (共性底座)', bg: 'bg-slate-50 text-slate-700 border-slate-200' };
      default:
        return { label: '矩阵产品', bg: 'bg-slate-50 text-slate-700 border-slate-200' };
    }
  };

  const getStageBadge = (stage: string) => {
    switch (stage) {
      case 'validating':
        return { label: '论证阶段', color: 'bg-blue-100 text-blue-800' };
      case 'building':
        return { label: '研发冲刺', color: 'bg-amber-100 text-amber-800' };
      case 'growth':
        return { label: '快速增长', color: 'bg-emerald-100 text-emerald-800' };
      case 'profitable':
        return { label: '规模盈利', color: 'bg-purple-100 text-purple-800' };
      case 'paused':
        return { label: '暂停待审', color: 'bg-slate-100 text-slate-600' };
      default:
        return { label: stage, color: 'bg-slate-100 text-slate-700' };
    }
  };

  const totalAllocated = portfolio.reduce((sum, p) => sum + (p.budget_allocated || 0), 0);
  const totalSpent = portfolio.reduce((sum, p) => sum + (p.actual_spent || 0), 0);
  const totalRevenue = portfolio.reduce((sum, p) => sum + (p.revenue_contribution || 0), 0);

  return (
    <div className="space-y-6">
      {/* 顶部控制栏与汇总数据 */}
      <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Layers className="w-4 h-4 text-emerald-600" />
              战略产品矩阵与分工 (Portfolio Management)
            </h2>
            <p className="text-xs text-slate-500">
              各产品聚焦独立业务场景与商业职责，评估单品投入产出、KPI 达成与是否值得继续投资。
            </p>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <div className="text-right pr-3 border-r border-slate-100 text-xs">
              <span className="text-slate-400 block text-[11px]">组合总支出 / 确认贡献</span>
              <span className="font-mono font-bold text-slate-900">
                ¥{(totalSpent / 1000).toFixed(0)}k /{' '}
                <span className="text-emerald-700">¥{(totalRevenue / 1000).toFixed(0)}k</span>
              </span>
            </div>

            <button
              onClick={onOpenNewProductModal}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white transition shadow-xs cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              新增矩阵产品
            </button>
          </div>
        </div>
      </div>

      {/* 产品矩阵卡片列表 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {portfolio.map((prod) => {
          const matchingProduct = products.find((p) => p.code === prod.code || p.id === prod.id) || {
            id: prod.id,
            name: prod.name,
            code: prod.code,
            description: '',
            created_at: '',
            updated_at: '',
          };

          const roleInfo = getStrategicRoleBadge(prod.strategic_role);
          const stageInfo = getStageBadge(prod.stage);
          const budgetUsage = prod.budget_allocated > 0 ? (prod.actual_spent / prod.budget_allocated) * 100 : 0;

          return (
            <div
              key={prod.id}
              className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs hover:border-emerald-300 hover:shadow-md transition flex flex-col justify-between space-y-4"
            >
              {/* 头部信息 */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded text-xs font-mono font-bold bg-slate-100 text-slate-800 border border-slate-200">
                      {prod.code}
                    </span>
                    <span className={`text-[11px] px-2 py-0.5 rounded-full font-semibold border ${roleInfo.bg}`}>
                      {roleInfo.label}
                    </span>
                  </div>

                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${stageInfo.color}`}>
                    {stageInfo.label}
                  </span>
                </div>

                <div>
                  <h3 className="text-sm font-bold text-slate-900">{prod.name}</h3>
                  <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                    {matchingProduct.description || '为本战略工程提供核心业务支持与场景覆盖。'}
                  </p>
                </div>

                {/* 核心指标 KPI 完成进度 */}
                {prod.kpi_name && (
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-slate-700">
                        {prod.kpi_name}
                      </span>
                      <span className="font-mono text-xs font-bold text-emerald-700">
                        {prod.kpi_actual?.toLocaleString()} / {prod.kpi_target?.toLocaleString()} {prod.kpi_unit} ({prod.kpi_completion_rate}%)
                      </span>
                    </div>

                    <div className="w-full bg-slate-200 rounded-full h-2 overflow-hidden">
                      <div
                        className="bg-emerald-500 h-2 rounded-full transition-all duration-500"
                        style={{ width: `${Math.min(100, prod.kpi_completion_rate || 0)}%` }}
                      />
                    </div>
                  </div>
                )}

                {/* 投入产出财务概览 */}
                <div className="grid grid-cols-3 gap-2 p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs">
                  <div>
                    <span className="text-[10px] text-slate-400 block">已分配预算</span>
                    <span className="font-mono font-bold text-slate-800">
                      ¥{(prod.budget_allocated / 1000).toFixed(0)}k
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-400 block">实际已支出</span>
                    <span className="font-mono font-bold text-slate-800">
                      ¥{(prod.actual_spent / 1000).toFixed(0)}k ({budgetUsage.toFixed(0)}%)
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-400 block">贡献商业收入</span>
                    <span className="font-mono font-bold text-emerald-700">
                      ¥{(prod.revenue_contribution / 1000).toFixed(0)}k
                    </span>
                  </div>
                </div>

                {/* 风险与管理建议 */}
                <div className="space-y-1.5 text-xs">
                  {prod.key_risk && (
                    <div className="flex items-start gap-1.5 text-amber-700 text-[11px] bg-amber-50/60 p-2 rounded-lg border border-amber-200/60">
                      <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5 text-amber-600" />
                      <span>
                        <strong className="font-semibold">关键风险：</strong>
                        {prod.key_risk}
                      </span>
                    </div>
                  )}

                  <div className="flex items-center justify-between text-[11px] pt-1">
                    <span className="text-slate-500">
                      管理建议：<strong className="text-slate-800">{prod.recommendation}</strong>
                    </span>
                    <span className="text-slate-400 font-mono">
                      {prod.active_runs_count} 个活跃发布周期
                    </span>
                  </div>
                </div>
              </div>

              {/* 底部下潜通道 */}
              <div className="pt-3 border-t border-slate-100 flex items-center justify-between">
                <span className="text-[11px] text-slate-400">
                  微观 PRD/架构/研发/测试细节已隔离
                </span>

                <button
                  onClick={() => onEnterProductWorkbench(matchingProduct)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-200 text-xs font-semibold transition group cursor-pointer"
                >
                  进入产品 13 模块工作台
                  <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition" />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
