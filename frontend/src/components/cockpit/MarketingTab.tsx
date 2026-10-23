import React, { useState } from 'react';
import {
  TrendingUp,
  DollarSign,
  Users,
  Target,
  ArrowUpRight,
  ArrowDownRight,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Share2,
  Tv,
  Megaphone,
  ArrowRight,
  CornerDownRight
} from 'lucide-react';
import { MarketingCockpitData } from '../../types';
import { MetricTooltip } from './MetricTooltip';

interface MarketingTabProps {
  marketing: MarketingCockpitData;
  onNavigateToDecisions?: () => void;
}

export const MarketingTab: React.FC<MarketingTabProps> = ({
  marketing,
  onNavigateToDecisions,
}) => {
  const { total_spend, effective_new_users, blended_cac, categories } = marketing;
  const [expandedCategories, setExpandedCategories] = useState<Record<string, boolean>>({
    paid_acquisition: true,
    partnerships: true,
    organic_referral: true,
  });

  const toggleCategory = (code: string) => {
    setExpandedCategories((prev) => ({ ...prev, [code]: !prev[code] }));
  };

  const toggleAll = (expand: boolean) => {
    const next: Record<string, boolean> = {};
    categories.forEach((c) => {
      next[c.category_code] = expand;
    });
    setExpandedCategories(next);
  };

  const getCategoryIcon = (code: string) => {
    switch (code) {
      case 'paid_acquisition':
        return <Megaphone className="w-4 h-4 text-blue-600" />;
      case 'partnerships':
        return <Tv className="w-4 h-4 text-purple-600" />;
      case 'organic_referral':
        return <Share2 className="w-4 h-4 text-emerald-600" />;
      default:
        return <Target className="w-4 h-4 text-slate-600" />;
    }
  };

  const allExpanded = categories.every((c) => expandedCategories[c.category_code]);

  return (
    <div className="space-y-6">
      {/* 顶部总盘说明 */}
      <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-emerald-600" />
              推广增长与渠道获客 (Marketing & Acquisition)
            </h2>
            <p className="text-xs text-slate-500">
              按「一级获客机制」结构化归因，回答 CEO 核心三问：<strong>钱花在哪里、用户从哪里来、哪种获客机制最值得继续投入？</strong>
            </p>
          </div>

          <div className="flex items-center gap-2">
            {onNavigateToDecisions && (
              <button
                onClick={onNavigateToDecisions}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white transition shadow-xs cursor-pointer"
              >
                <span>审批渠道预算调配</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* 战役营销总盘 3 大顶层核心指标 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs mb-1">
            <span className="flex items-center gap-1">
              推广累计实际消耗
              <MetricTooltip
                title="推广累计支出 (Total Marketing Spend)"
                definition="核算期内向付费广告、达人合作与用户裂变激励实际支付的营销资金总额。"
                accountingType="收付实现制 (Cash Basis)"
              />
            </span>
            <DollarSign className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-2xl font-bold text-slate-900 font-mono">
            ¥{total_spend.toLocaleString()}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">
            占战略工程实付总额约 {((total_spend / 215000) * 100).toFixed(0)}%
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs mb-1">
            <span className="flex items-center gap-1">
              全渠道有效新增用户
              <MetricTooltip
                title="有效新增用户 (Effective New Users)"
                definition="已剔除刷量作弊，完成真实注册并产生首次有效记账或交易的商业用户总数。"
                accountingType="业务统计口径"
              />
            </span>
            <Users className="w-4 h-4 text-blue-600" />
          </div>
          <div className="text-2xl font-bold text-slate-900 font-mono">
            {effective_new_users.toLocaleString()} 人
          </div>
          <div className="text-[11px] text-emerald-600 font-medium mt-1 flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3" />
            自然与推荐贡献达 65.1%
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs mb-1">
            <span className="flex items-center gap-1">
              战役综合加权 CAC
              <MetricTooltip
                title="综合获客成本 (Blended CAC)"
                definition="推广总支出除以全渠道有效新增用户数所得的加权平均成本。"
                formula="BlendedCAC = TotalSpend / EffectiveNewUsers"
                accountingType="业务统计口径"
              />
            </span>
            <Target className="w-4 h-4 text-purple-600" />
          </div>
          <div className="text-2xl font-bold text-slate-900 font-mono">
            ¥{blended_cac.toFixed(2)}
          </div>
          <div className={`text-[11px] font-medium mt-1 flex items-center gap-1 ${
            blended_cac === 0 ? 'text-slate-400' : blended_cac <= 15 ? 'text-emerald-600' : 'text-rose-600'
          }`}>
            <CheckCircle2 className="w-3 h-3" />
            {blended_cac === 0 ? '暂无投放支出数据' : blended_cac <= 15 ? '优于预警基线 (≤ ¥15.00)' : '超出预警基线 (≤ ¥15.00)'}
          </div>
        </div>
      </div>

      {/* 合并后的单一综合对照与明细表 (Unified Executive Acquisition & Channel Matrix) */}
      <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-3">
          <div>
            <h3 className="text-xs font-bold text-slate-900 flex items-center gap-2">
              <span>一级获客机制经营成效与二级渠道展开对照</span>
            </h3>
            <span className="text-[11px] text-slate-400">
              一级按获客机制汇总成本与 ROI，点击行即可展开查看二级具体平台/渠道明细
            </span>
          </div>

          <div className="flex items-center gap-3 text-xs">
            <button
              onClick={() => toggleAll(!allExpanded)}
              className="text-[11px] text-emerald-700 hover:text-emerald-800 font-semibold cursor-pointer"
            >
              {allExpanded ? '全部折叠' : '全部展开'}
            </button>
            <span className="text-slate-300">|</span>
            <span className="text-slate-400 text-[11px]">
              {categories.length} 大一级机制 · {categories.reduce((acc, c) => acc + (c.sub_channels?.length || 0), 0)} 个二级渠道
            </span>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-200 text-slate-400 bg-slate-50/70 text-[11px]">
                <th className="py-2.5 px-3 font-medium">获客机制 / 二级具体渠道</th>
                <th className="py-2.5 px-3 font-medium">投入成本/费用</th>
                <th className="py-2.5 px-3 font-medium">有效新增 (占比)</th>
                <th className="py-2.5 px-3 font-medium">单客 CAC</th>
                <th className="py-2.5 px-3 font-medium">转化率</th>
                <th className="py-2.5 px-3 font-medium">贡献收入 (回本期)</th>
                <th className="py-2.5 px-3 font-medium text-right">CEO 经营决策建议</th>
              </tr>
            </thead>
            <tbody>
              {categories.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-400 text-xs">
                    暂无推广获客渠道数据。各渠道数据可在工序交付与实际经营投放后自动归集。
                  </td>
                </tr>
              ) : (
                categories.map((cat) => {
                  const isExpanded = expandedCategories[cat.category_code] ?? true;
                  const isOverCAC = cat.cac > 20.0;

                  return (
                    <React.Fragment key={cat.category_code}>
                    {/* 一级机制主行（可整行点击展开/折叠） */}
                    <tr
                      onClick={() => toggleCategory(cat.category_code)}
                      className="border-t border-slate-200 bg-slate-50/60 hover:bg-slate-100/70 transition cursor-pointer font-medium"
                    >
                      <td className="py-3 px-3 font-semibold text-slate-900 flex items-center gap-2">
                        <span className="text-slate-400">
                          {isExpanded ? (
                            <ChevronDown className="w-3.5 h-3.5" />
                          ) : (
                            <ChevronRight className="w-3.5 h-3.5" />
                          )}
                        </span>
                        {getCategoryIcon(cat.category_code)}
                        <span>{cat.category_name}</span>
                        <span className="text-[10px] text-slate-400 font-mono font-normal">
                          ({cat.sub_channels.length}个渠道)
                        </span>
                      </td>
                      <td className="py-3 px-3 font-mono font-bold text-slate-800">
                        ¥{cat.spend.toLocaleString()}
                      </td>
                      <td className="py-3 px-3 font-mono text-slate-700">
                        <span className="font-semibold">{cat.acquired_users.toLocaleString()} 人</span>{' '}
                        <span className="text-slate-400 font-normal">({cat.user_share_percent}%)</span>
                      </td>
                      <td className="py-3 px-3 font-mono font-bold">
                        <span className={isOverCAC ? 'text-rose-600' : 'text-slate-900'}>
                          ¥{cat.cac.toFixed(2)}
                        </span>
                      </td>
                      <td className="py-3 px-3 font-mono text-slate-700">
                        {cat.conversion_rate}%
                      </td>
                      <td className="py-3 px-3 font-mono text-slate-700">
                        ¥{(cat.revenue_contribution / 1000).toFixed(0)}k ({cat.payback_days ? `${cat.payback_days}天` : '-'})
                      </td>
                      <td className="py-3 px-3 text-right">
                        <span
                          className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold ${
                            cat.decision_recommendation.includes('扩大') || cat.decision_recommendation.includes('追加')
                              ? 'bg-purple-50 text-purple-700 border border-purple-200'
                              : cat.decision_recommendation.includes('优化')
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : 'bg-rose-50 text-rose-700 border border-rose-200'
                          }`}
                        >
                          {cat.decision_recommendation.includes('扩大') || cat.decision_recommendation.includes('追加') ? (
                            <ArrowUpRight className="w-3 h-3 text-purple-600" />
                          ) : cat.decision_recommendation.includes('优化') ? (
                            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                          ) : (
                            <ArrowDownRight className="w-3 h-3 text-rose-600" />
                          )}
                          {cat.decision_recommendation}
                        </span>
                      </td>
                    </tr>

                    {/* 二级细分渠道展开行 */}
                    {isExpanded && (
                      <>
                        {cat.sub_channels.map((sub, idx) => (
                          <tr key={idx} className="bg-white hover:bg-slate-50/60 transition border-b border-slate-50">
                            <td className="py-2.5 px-3 pl-8 text-slate-700 flex items-center gap-2">
                              <CornerDownRight className="w-3 h-3 text-slate-400 shrink-0" />
                              <span className="font-normal">{sub.name}</span>
                            </td>
                            <td className="py-2.5 px-3 font-mono text-slate-600 text-[11px]">
                              {sub.spend > 0 ? `¥${sub.spend.toLocaleString()}` : '—'}
                            </td>
                            <td className="py-2.5 px-3 font-mono text-slate-600 text-[11px]">
                              {sub.acquired_users > 0 ? `${sub.acquired_users.toLocaleString()} 人` : '—'}
                            </td>
                            <td className="py-2.5 px-3 font-mono text-slate-600 text-[11px]">
                              {sub.cac > 0 ? `¥${sub.cac.toFixed(2)}` : '—'}
                            </td>
                            <td className="py-2.5 px-3 font-mono text-slate-500 text-[11px]">
                              {sub.status === 'active' ? '正常转化' : '—'}
                            </td>
                            <td className="py-2.5 px-3 font-mono text-slate-500 text-[11px]">
                              {sub.status === 'active' ? '已计入总额' : '—'}
                            </td>
                            <td className="py-2.5 px-3 text-right">
                              <span
                                className={`text-[10px] px-2 py-0.2 rounded font-mono font-medium ${
                                  sub.status === 'active'
                                    ? 'bg-emerald-50 text-emerald-700 border border-emerald-100'
                                    : 'bg-slate-100 text-slate-400'
                                }`}
                              >
                                {sub.status === 'active' ? '● 投放运行中' : '○ 储备规划中'}
                              </span>
                            </td>
                          </tr>
                        ))}

                        {/* CEO 洞察提示行 */}
                        <tr className="bg-slate-50/40 border-b border-slate-100">
                          <td colSpan={7} className="py-2 px-8 text-[11px] text-slate-600">
                            <div className="flex items-center gap-2">
                              <span className="font-semibold text-slate-700">💡 决策要点：</span>
                              <span>{cat.decision_recommendation || '根据获客成效动态研判中。'}</span>
                            </div>
                          </td>
                        </tr>
                      </>
                    )}
                  </React.Fragment>
                );
              }))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
