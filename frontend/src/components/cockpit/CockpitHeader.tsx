import React from 'react';
import {
  Layers,
  TrendingUp,
  Users,
  Wallet,
  ShieldAlert,
  LayoutDashboard
} from 'lucide-react';
import { ExecutiveCockpitResponse } from '../../types';

export type CockpitTabKey = 'overview' | 'portfolio' | 'marketing' | 'operations' | 'finance' | 'decisions';

interface CockpitHeaderProps {
  cockpit: ExecutiveCockpitResponse;
  activeTab: CockpitTabKey;
  onTabChange: (tab: CockpitTabKey) => void;
  pendingDecisionsCount: number;
  activeRisksCount: number;
}

export const CockpitHeader: React.FC<CockpitHeaderProps> = ({
  cockpit,
  activeTab,
  onTabChange,
  pendingDecisionsCount,
  activeRisksCount,
}) => {
  const tabs: Array<{
    key: CockpitTabKey;
    label: string;
    icon: React.ReactNode;
    badge?: number;
    badgeColor?: string;
  }> = [
    { key: 'overview', label: '01. 经营总览', icon: <LayoutDashboard className="w-3.5 h-3.5" /> },
    { key: 'portfolio', label: '02. 产品组合', icon: <Layers className="w-3.5 h-3.5" />, badge: cockpit.portfolio.length },
    { key: 'marketing', label: '03. 推广增长', icon: <TrendingUp className="w-3.5 h-3.5" /> },
    { key: 'operations', label: '04. 运营变现', icon: <Users className="w-3.5 h-3.5" /> },
    { key: 'finance', label: '05. 财务账本', icon: <Wallet className="w-3.5 h-3.5" /> },
    {
      key: 'decisions',
      label: '06. 经营决策中心',
      icon: <ShieldAlert className="w-3.5 h-3.5" />,
      badge: pendingDecisionsCount + activeRisksCount > 0 ? pendingDecisionsCount + activeRisksCount : undefined,
      badgeColor: pendingDecisionsCount > 0 ? 'bg-amber-500 text-white' : 'bg-rose-500 text-white',
    },
  ];

  return (
    <div className="border-b border-slate-200 pb-2">
      {/* 6 大业务模块 Tab 导航栏 */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none">
        {tabs.map((tab) => {
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => onTabChange(tab.key)}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold transition shrink-0 cursor-pointer ${
                isActive
                  ? 'bg-slate-900 text-white shadow-xs'
                  : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200 hover:text-slate-900'
              }`}
            >
              <span className={isActive ? 'text-emerald-400' : 'text-slate-500'}>{tab.icon}</span>
              <span>{tab.label}</span>
              {tab.badge !== undefined && (
                <span
                  className={`px-1.5 py-0.2 rounded-full text-[10px] font-mono font-bold ${
                    tab.badgeColor || (isActive ? 'bg-slate-700 text-slate-200' : 'bg-slate-100 text-slate-600')
                  }`}
                >
                  {tab.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
};
