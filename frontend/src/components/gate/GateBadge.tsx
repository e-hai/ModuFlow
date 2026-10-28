import React from 'react';
import { GateLevel } from '../../types';
import { ShieldCheck, AlertCircle, AlertTriangle } from 'lucide-react';

interface GateBadgeProps {
  level: GateLevel | string;
  gateName?: string;
  isEscalated?: boolean;
  resolved?: boolean;
  size?: 'sm' | 'md';
}

export const GateBadge: React.FC<GateBadgeProps> = ({
  level,
  gateName,
  isEscalated,
  resolved = false,
  size = 'md',
}) => {
  const normLevel = (level || 'green').toLowerCase();

  let colorClass = 'bg-emerald-50 text-emerald-800 border-emerald-300';
  let dotClass = 'bg-emerald-500';
  let label = '🟢 自动核验';
  let tooltip = '常规阶段：系统与AI主管自动核验，指标达标自动放行，事后可随时查阅';

  if (resolved && normLevel !== 'green') {
    colorClass = 'bg-emerald-50 text-emerald-800 border-emerald-200';
    dotClass = 'bg-emerald-500';
    label = '已通过';
    tooltip = '这一关已经放行';
  } else if (normLevel === 'yellow') {
    colorClass = 'bg-amber-50 text-amber-800 border-amber-300';
    dotClass = 'bg-amber-500';
    label = '🟡 待您确认';
    tooltip = '关键节点：AI已整理好交付成果与数据依据，请负责人确认';
  } else if (normLevel === 'red') {
    colorClass = 'bg-rose-50 text-rose-800 border-rose-300 animate-pulse';
    dotClass = 'bg-rose-500';
    label = isEscalated ? '🔴 需亲自确认 (重大变动)' : '🔴 必须亲自把关';
    tooltip = isEscalated
      ? '系统检测到涉及真实货币、用户隐私或预算超限等高危变动，已强制暂停等待您亲自确认'
      : '重大关键决策（如对外发布、提审上架、价格与账号权限），必须由您亲自签字放行';
  }

  const paddingClass = size === 'sm' ? 'px-2 py-0.5 text-[10px]' : 'px-2.5 py-1 text-xs';

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-semibold rounded-full border shadow-2xs transition ${colorClass} ${paddingClass}`}
      title={tooltip}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${dotClass}`} />
      {gateName && <span className="font-bold">{gateName}</span>}
      <span className="font-medium">{label}</span>
    </span>
  );
};
