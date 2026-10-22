import React from 'react';

interface PhaseBadgeProps {
  phase: 'draft' | 'discussing' | 'reviewing' | 'baselined' | string;
}

export const PhaseBadge: React.FC<PhaseBadgeProps> = ({ phase }) => {
  const configs: Record<string, { label: string; bg: string; text: string; border: string }> = {
    draft: { label: '草稿待定', bg: 'bg-slate-100', text: 'text-slate-700', border: 'border-slate-300' },
    discussing: { label: '协作研讨中', bg: 'bg-amber-50', text: 'text-amber-800', border: 'border-amber-200' },
    reviewing: { label: '评审门禁', bg: 'bg-blue-50', text: 'text-blue-800', border: 'border-blue-200' },
    baselined: { label: '基线已锁定', bg: 'bg-emerald-50', text: 'text-emerald-800', border: 'border-emerald-200' },
  };

  const c = configs[phase] || configs.draft;
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium border ${c.bg} ${c.text} ${c.border}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current mr-1.5 animate-pulse" />
      {c.label}
    </span>
  );
};

interface SeverityBadgeProps {
  severity: 'critical' | 'major' | 'minor' | 'trivial' | string;
}

export const SeverityBadge: React.FC<SeverityBadgeProps> = ({ severity }) => {
  const configs: Record<string, { label: string; color: string }> = {
    critical: { label: 'P0 阻断性 (Critical)', color: 'bg-rose-50 text-rose-700 border-rose-200' },
    major: { label: 'P1 严重 (Major)', color: 'bg-orange-50 text-orange-700 border-orange-200' },
    minor: { label: 'P2 一般 (Minor)', color: 'bg-amber-50 text-amber-700 border-amber-200' },
    trivial: { label: 'P3 轻微 (Trivial)', color: 'bg-slate-100 text-slate-600 border-slate-200' },
  };
  const c = configs[severity] || configs.major;
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono border ${c.color}`}>
      {c.label}
    </span>
  );
};
