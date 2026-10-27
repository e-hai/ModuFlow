import React from 'react';
import { GateLevel } from '../../types';
import { ShieldCheck, AlertCircle, AlertTriangle } from 'lucide-react';

interface GateBadgeProps {
  level: GateLevel | string;
  gateName?: string;
  isEscalated?: boolean;
  size?: 'sm' | 'md';
}

export const GateBadge: React.FC<GateBadgeProps> = ({
  level,
  gateName,
  isEscalated,
  size = 'md',
}) => {
  const normLevel = (level || 'green').toLowerCase();

  let colorClass = 'bg-emerald-50 text-emerald-800 border-emerald-300';
  let dotClass = 'bg-emerald-500';
  let label = '🟢 绿级';
  let icon = <ShieldCheck className="w-3 h-3 text-emerald-600" />;

  if (normLevel === 'yellow') {
    colorClass = 'bg-amber-50 text-amber-800 border-amber-300';
    dotClass = 'bg-amber-500';
    label = '🟡 黄级 (人批)';
    icon = <AlertTriangle className="w-3 h-3 text-amber-600" />;
  } else if (normLevel === 'red') {
    colorClass = 'bg-rose-50 text-rose-800 border-rose-300 animate-pulse';
    dotClass = 'bg-rose-500';
    label = isEscalated ? '🔴 自动升红 (人必批)' : '🔴 红级 (人必批)';
    icon = <AlertCircle className="w-3 h-3 text-rose-600" />;
  }

  const paddingClass = size === 'sm' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2 py-0.5 text-xs';

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-semibold font-mono rounded-full border shadow-2xs ${colorClass} ${paddingClass}`}
      title={
        normLevel === 'green'
          ? '绿级关口：项目总控 (lead) 自批，事后人类抽查'
          : normLevel === 'yellow'
          ? '黄级关口：人类批量审批，由 lead 整理一页纸申请单'
          : '红级关口：人类即时必须审批，系统物理阻断工序流转'
      }
    >
      <span className={`w-1.5 h-1.5 rounded-full ${dotClass}`} />
      {gateName && <span className="font-sans font-bold">{gateName}</span>}
      <span>{label}</span>
    </span>
  );
};
