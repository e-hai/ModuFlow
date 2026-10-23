import React, { useState } from 'react';
import {
  PanelLeftClose,
  PanelLeftOpen,
  Compass,
  ChevronRight,
  FileText,
  Calendar,
  ChevronDown,
  X,
  Target,
  MapPin,
  Lightbulb,
  User,
  ShieldCheck,
  FolderGit2,
  RefreshCw,
  Check
} from 'lucide-react';
import { StrategicInitiative, Product } from '../types';
import { api } from '../services/api';

interface NavbarProps {
  isSidebarOpen: boolean;
  onToggleSidebar: () => void;
  currentInitiative: StrategicInitiative | null;
  currentProduct?: Product | null;
  products?: Product[];
  currentView: 'dashboard' | 'workflow' | 'module' | 'issues';
  onNavigateToDashboard: () => void;
  selectedPeriod?: string;
  onPeriodChange?: (period: string) => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  isSidebarOpen,
  onToggleSidebar,
  currentInitiative,
  currentProduct,
  products = [],
  currentView,
  onNavigateToDashboard,
  selectedPeriod = 'lifetime',
  onPeriodChange,
}) => {
  const [showStrategyModal, setShowStrategyModal] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncStatus, setSyncStatus] = useState<string | null>(null);

  const handleSyncWorkspace = async () => {
    if (!currentInitiative || isSyncing) return;
    setIsSyncing(true);
    setSyncStatus(null);
    try {
      const res = await api.syncWorkspace(currentInitiative.id);
      if (res.success) {
        setSyncStatus('已同步至本地工作区');
      } else {
        setSyncStatus('同步失败');
      }
    } catch (e) {
      setSyncStatus('同步失败');
    } finally {
      setIsSyncing(false);
      setTimeout(() => setSyncStatus(null), 3000);
    }
  };

  return (
    <>
      <header className="border-b border-slate-200 bg-white/95 backdrop-blur sticky top-0 z-20 h-16 px-4 flex items-center justify-between">
        {/* 左侧：展开收起按钮 + 战略工程标题与工作台上下文 */}
        <div className="flex items-center space-x-3.5 min-w-0">
          <button
            onClick={onToggleSidebar}
            title={isSidebarOpen ? '收起侧边栏' : '展开侧边栏'}
            className="p-2 rounded-lg bg-slate-100 hover:bg-slate-200/80 text-slate-600 hover:text-slate-900 border border-slate-200 transition flex items-center justify-center cursor-pointer shadow-xs shrink-0"
          >
            {isSidebarOpen ? (
              <PanelLeftClose className="w-4 h-4 text-emerald-600" />
            ) : (
              <PanelLeftOpen className="w-4 h-4 text-emerald-600" />
            )}
          </button>

          <div className="flex items-center space-x-2 text-sm min-w-0">
            <button
              onClick={onNavigateToDashboard}
              title="返回战略驾驶舱"
              className="flex items-center gap-1.5 font-bold text-slate-900 hover:text-emerald-700 tracking-tight transition cursor-pointer text-left truncate"
            >
              <Compass className="w-4 h-4 text-emerald-600 shrink-0" />
              <span className="truncate max-w-[160px] sm:max-w-xs md:max-w-md">
                {currentInitiative?.name || '战略工程'}
              </span>
            </button>

            {currentView === 'workflow' && currentProduct && (
              <div className="hidden sm:flex items-center text-xs text-slate-500 shrink-0">
                <ChevronRight className="w-3.5 h-3.5 text-slate-400 mx-1" />
                <span className="text-emerald-700 font-semibold">{currentProduct.name}</span>
                <span className="ml-1 text-slate-500">产研工作台</span>
              </div>
            )}

            {currentView === 'issues' && (
              <div className="hidden sm:flex items-center text-xs text-slate-500 shrink-0">
                <ChevronRight className="w-3.5 h-3.5 text-slate-400 mx-1" />
                <span className="text-rose-600 font-semibold">全局 Issue 闭环流转</span>
              </div>
            )}
          </div>
        </div>

        {/* 右侧：主体身份与战略底稿 Icon 按钮 + 周期切换下拉列表 */}
        {currentInitiative && (
          <div className="flex items-center space-x-2.5 shrink-0 pl-3">
            {/* 1. 主体身份与战略底稿 Icon 按钮 */}
            <button
              onClick={() => setShowStrategyModal(true)}
              title="点击查看主体身份与战略底稿"
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-50 hover:bg-emerald-50 text-slate-700 hover:text-emerald-700 border border-slate-200 hover:border-emerald-300 transition text-xs font-semibold cursor-pointer shadow-xs"
            >
              <FileText className="w-3.5 h-3.5 text-emerald-600" />
              <span className="hidden sm:inline">主体身份与战略底稿</span>
            </button>

            {/* 2. 周期切换下拉列表 */}
            <div className="relative flex items-center">
              <Calendar className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 pointer-events-none" />
              <select
                value={selectedPeriod}
                onChange={(e) => onPeriodChange?.(e.target.value)}
                className="pl-8 pr-7 py-1.5 bg-slate-50 hover:bg-slate-100/80 border border-slate-200 hover:border-slate-300 rounded-lg text-xs font-semibold text-slate-800 focus:outline-none focus:border-emerald-500 cursor-pointer appearance-none shadow-xs transition"
              >
                <option value="MTD">本月 (MTD)</option>
                <option value="QTD">本季 (QTD)</option>
                <option value="YTD">本年 (YTD)</option>
                <option value="lifetime">战役累计 (Lifetime)</option>
              </select>
              <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-2 pointer-events-none" />
            </div>
          </div>
        )}
      </header>

      {/* 主体身份与战略底稿内容弹窗 (Modal) */}
      {showStrategyModal && currentInitiative && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4"
          onClick={() => setShowStrategyModal(false)}
        >
          <div
            className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-lg overflow-hidden animate-in fade-in zoom-in-95 duration-150"
            onClick={(e) => e.stopPropagation()}
          >
            {/* 弹窗头部 */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 bg-slate-50/70">
              <div className="flex items-center gap-2">
                <Compass className="w-4 h-4 text-emerald-600" />
                <h3 className="text-sm font-bold text-slate-900">主体身份与战略底稿</h3>
              </div>
              <button
                onClick={() => setShowStrategyModal(false)}
                className="p-1.5 rounded-lg hover:bg-slate-200 text-slate-400 hover:text-slate-700 transition cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* 弹窗内容 */}
            <div className="p-5 space-y-4 max-h-[75vh] overflow-y-auto">
              {/* 一、主体身份 */}
              <div className="space-y-2">
                <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block font-mono">
                  一、主体身份 (Entity Identity)
                </span>
                <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <span className="text-[10px] text-slate-400 block">战略工程名称</span>
                    <span className="font-bold text-slate-900">{currentInitiative.name}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-400 block">工程代号 ID</span>
                    <span className="font-mono font-bold text-slate-800">ID: {currentInitiative.id}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-400 block">总负责人</span>
                    <span className="font-medium text-slate-800 flex items-center gap-1">
                      <User className="w-3 h-3 text-slate-400" />
                      {currentInitiative.owner}
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-400 block">当前战略状态</span>
                    <span className="inline-flex items-center px-1.5 py-0.2 rounded text-[10px] font-mono font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                      {currentInitiative.status.toUpperCase()}
                    </span>
                  </div>
                </div>
              </div>

              {/* 二、战略底稿 */}
              <div className="space-y-3">
                <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block font-mono">
                  二、战略底稿 (Strategic Blueprint)
                </span>

                {/* 战略定性 */}
                <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 space-y-1">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800">
                    <Target className="w-3.5 h-3.5 text-emerald-600" />
                    <span>战略定性</span>
                  </div>
                  <p className="text-xs text-slate-700 leading-relaxed">
                    {currentInitiative.strategic_intent || '暂未设定战略定性'}
                  </p>
                </div>

                {/* 目标市场 */}
                <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 space-y-1">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800">
                    <MapPin className="w-3.5 h-3.5 text-blue-600" />
                    <span>目标市场</span>
                  </div>
                  <p className="text-xs text-slate-700 leading-relaxed">
                    {currentInitiative.target_market || '暂未设定目标市场'}
                  </p>
                </div>

                {/* 商业模式假设 */}
                <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 space-y-1">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800">
                    <Lightbulb className="w-3.5 h-3.5 text-amber-600" />
                    <span>商业模式假设</span>
                  </div>
                  <p className="text-xs text-slate-700 leading-relaxed">
                    {currentInitiative.business_model_hypothesis || '暂未设定商业模式假设'}
                  </p>
                </div>
              </div>

              {/* 三、物理文件工作区隔离 */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block font-mono">
                    三、本地物理工作区 (Physical Filesystem)
                  </span>
                  <button
                    onClick={handleSyncWorkspace}
                    disabled={isSyncing}
                    className="flex items-center gap-1 text-[11px] font-semibold text-emerald-700 hover:text-emerald-800 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200/80 px-2 py-0.5 rounded-md transition cursor-pointer disabled:opacity-50"
                  >
                    {isSyncing ? (
                      <RefreshCw className="w-3 h-3 animate-spin text-emerald-600" />
                    ) : syncStatus ? (
                      <Check className="w-3 h-3 text-emerald-600" />
                    ) : (
                      <FolderGit2 className="w-3 h-3 text-emerald-600" />
                    )}
                    <span>{isSyncing ? '同步中...' : syncStatus || '重新同步落盘'}</span>
                  </button>
                </div>

                <div className="p-3.5 bg-slate-900 text-slate-100 rounded-xl border border-slate-800 space-y-2 text-xs font-mono">
                  <div className="flex items-center gap-1.5 text-emerald-400 font-bold">
                    <FolderGit2 className="w-3.5 h-3.5 shrink-0" />
                    <span className="truncate">data/workspaces/{currentInitiative.id}/</span>
                  </div>
                  <div className="text-[11px] text-slate-400 space-y-1 pl-1 border-l-2 border-slate-700">
                    <div>├── <span className="text-slate-300">00_战略工程底稿与公共资产/</span> (底稿/公共市场调研/生态闭环)</div>
                    <div>└── <span className="text-slate-300">products/</span> (子产品文件夹严格物理隔离)</div>
                    {products && products.length > 0 ? (
                      products.map((p, idx) => {
                        const isLast = idx === products.length - 1;
                        return (
                          <div key={p.id} className="pl-4">
                            {isLast ? '└──' : '├──'} <span className="text-amber-300">{p.code}/</span> ({p.name})
                          </div>
                        );
                      })
                    ) : (
                      <div className="pl-4 text-slate-500">└── (暂无子产品目录)</div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* 弹窗底部 */}
            <div className="px-5 py-3 border-t border-slate-100 bg-slate-50/40 flex items-center justify-between">
              <span className="text-[11px] text-slate-400">战略底稿由董事会与总负责人统一校准</span>
              <button
                onClick={() => setShowStrategyModal(false)}
                className="px-4 py-1.5 rounded-xl text-xs font-semibold bg-slate-900 hover:bg-slate-800 text-white transition cursor-pointer"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
