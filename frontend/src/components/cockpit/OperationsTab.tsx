import React from 'react';
import {
  Users,
  DollarSign,
  TrendingUp,
  Activity,
  Layers,
  CheckCircle2,
  HelpCircle,
  Percent
} from 'lucide-react';
import { OperationsCockpitData } from '../../types';
import { MetricTooltip } from './MetricTooltip';

interface OperationsTabProps {
  operations: OperationsCockpitData;
}

export const OperationsTab: React.FC<OperationsTabProps> = ({ operations }) => {
  const {
    dau,
    mau,
    retention_1d,
    retention_7d,
    retention_30d,
    paid_users,
    arpu,
    arppu,
    ltv,
    ltv_cac_ratio,
    funnel,
  } = operations;

  const dauMauRatio = mau > 0 ? (dau / mau) * 100 : 0;

  return (
    <div className="space-y-6">
      {/* 顶部总盘说明 */}
      <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs">
        <div className="space-y-1">
          <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <Users className="w-4 h-4 text-emerald-600" />
            运营活跃与商业变现
          </h2>
          <p className="text-xs text-slate-500">
            关注核心经营指标：用户留存、付费转化与单位经济模型 (LTV/CAC)。
          </p>
        </div>
      </div>

      {/* 活跃与变现关键指标带 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs mb-1">
            <span className="flex items-center gap-1">
              DAU / MAU 黏度
              <MetricTooltip
                title="日活 / 月活黏度比率"
                definition="每日活跃用户数占月活跃用户数的比例。一般工具类产品 > 20% 代表高频使用；金融记账类达 25%-30% 为顶级表现。"
                formula="Stickiness = DAU / MAU * 100%"
              />
            </span>
            <Activity className="w-4 h-4 text-blue-600" />
          </div>
          <div className="text-xl font-bold text-slate-900 font-mono">
            {dauMauRatio.toFixed(1)}%
          </div>
          <div className="text-[11px] text-slate-400 mt-1">
            DAU: {(dau / 1000).toFixed(1)}k · MAU: {(mau / 1000).toFixed(1)}k
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs mb-1">
            <span className="flex items-center gap-1">
              付费用户数
              <MetricTooltip
                title="付费转化用户 (Paying Users)"
                definition="已完成增值服务购买、聚合支付手续费结算或订阅签约的有效变现客户数。"
                accountingType="收付实现制 (Cash Basis)"
              />
            </span>
            <DollarSign className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-xl font-bold text-emerald-600 font-mono">
            {paid_users.toLocaleString()} 人
          </div>
          <div className="text-[11px] text-slate-400 mt-1">
            占活跃用户 {( (paid_users / (dau || 1)) * 100).toFixed(1)}%
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs mb-1">
            <span className="flex items-center gap-1">
              ARPU / ARPPU
              <MetricTooltip
                title="单客平均收入"
                definition="ARPU 为每活跃用户贡献收入，ARPPU 为每付费用户实际贡献收入。"
                formula="ARPU = Revenue / ActiveUsers; ARPPU = Revenue / PayingUsers"
              />
            </span>
            <Percent className="w-4 h-4 text-purple-600" />
          </div>
          <div className="text-xl font-bold text-slate-900 font-mono">
            ¥{arpu.toFixed(1)} / <span className="text-emerald-700">¥{arppu.toFixed(1)}</span>
          </div>
          <div className="text-[11px] text-slate-400 mt-1">
            付费客单价保持稳定
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs mb-1">
            <span className="flex items-center gap-1">
              LTV / CAC 倍数
              <MetricTooltip
                title="单位经济健康倍数 (LTV/CAC)"
                definition="行业黄金分水岭：3.0x 代表健康具备良好自造血能力；4.0x 以上代表可加大资金杠杆投入。"
                formula="LTV/CAC = LTV / BlendedCAC"
              />
            </span>
            <TrendingUp className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-xl font-bold text-emerald-600 font-mono">
            {ltv_cac_ratio.toFixed(2)}x
          </div>
          <div className="text-[11px] text-emerald-600 font-medium mt-1 flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3" />
            LTV: ¥{ltv.toFixed(1)} · 优于 3.0x
          </div>
        </div>
      </div>

      {/* 留存 Cohort 与 转化漏斗并列 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 留存分析 */}
        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold text-slate-900 flex items-center gap-2">
              <Activity className="w-4 h-4 text-emerald-600" />
              <span>用户留存走势</span>
            </h3>
            <span className="text-xs text-slate-400">次日 / 7日 / 30日 留存率</span>
          </div>

          <div className="space-y-4 pt-1">
            <div>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-slate-600 font-medium">次日留存 (Day 1)</span>
                <span className="font-mono font-bold text-slate-900">{retention_1d}% (标杆 ≥ 40%)</span>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                <div
                  className="bg-emerald-500 h-2 rounded-full"
                  style={{ width: `${retention_1d}%` }}
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-slate-600 font-medium">7 日留存 (Day 7)</span>
                <span className="font-mono font-bold text-slate-900">{retention_7d}% (标杆 ≥ 25%)</span>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                <div
                  className="bg-emerald-600 h-2 rounded-full"
                  style={{ width: `${retention_7d}%` }}
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-slate-600 font-medium">30 日留存 (Day 30)</span>
                <span className="font-mono font-bold text-slate-900">{retention_30d}% (标杆 ≥ 15%)</span>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                <div
                  className="bg-purple-600 h-2 rounded-full"
                  style={{ width: `${retention_30d}%` }}
                />
              </div>
            </div>
          </div>

          {retention_30d > 0 && (
            <p className="text-[11px] text-slate-500 bg-slate-50 p-3 rounded-xl border border-slate-200 leading-relaxed">
              💡 <strong className="text-slate-800">留存黏性洞察：</strong> 30日留存率达 {retention_30d}%，持续打磨核心场景体验是提升长期留存的关键。
            </p>
          )}
        </div>

        {/* 转化漏斗 */}
        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold text-slate-900 flex items-center gap-2">
              <Layers className="w-4 h-4 text-emerald-600" />
              <span>全链路商业转化漏斗</span>
            </h3>
            <span className="text-xs text-slate-400">各节点转化与流失</span>
          </div>

          {funnel.length === 0 ? (
            <div className="py-8 text-center text-slate-400 text-xs">
              暂无转化漏斗数据。可在各产品上线后采集各链路节点转化率。
            </div>
          ) : (
            <div className="space-y-3">
              {funnel.map((step, idx) => (
                <div key={idx} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium text-slate-700 flex items-center gap-1.5">
                      <span className="w-4 h-4 rounded-full bg-slate-100 text-slate-600 font-mono text-[10px] flex items-center justify-center font-bold">
                        {idx + 1}
                      </span>
                      {step.stage}
                    </span>
                    <div className="font-mono text-xs">
                      <span className="font-semibold text-slate-900">{step.count.toLocaleString()}</span>
                      <span className="text-slate-400 ml-1.5">({step.conversion_rate}%)</span>
                    </div>
                  </div>

                  <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                    <div
                      className="bg-emerald-500 h-2 rounded-full"
                      style={{ width: `${step.conversion_rate}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}

          {funnel.length > 0 && (
            <p className="text-[11px] text-slate-500 bg-slate-50 p-3 rounded-xl border border-slate-200 leading-relaxed">
              💡 <strong className="text-slate-800">变现转化分析：</strong> 关注漏斗各环节流失率，结合工序 07/08 优化核心转化流程。
            </p>
          )}
        </div>
      </div>
    </div>
  );
};
