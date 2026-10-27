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
  FolderGit2,
  RefreshCw,
  Check,
  Bug,
  ArrowLeft,
  Package,
  Layers,
} from 'lucide-react';
import { StrategicInitiative, Product, ModuleInstance } from '../types';
import { api } from '../services/api';

interface NavbarProps {
  isSidebarOpen: boolean;
  onToggleSidebar: () => void;
  currentInitiative: StrategicInitiative | null;
  currentProduct?: Product | null;
  products?: Product[];
  currentView: 'dashboard' | 'workflow' | 'module' | 'issues';
  activeModule?: ModuleInstance | null;
  runModules?: ModuleInstance[];
  onNavigateToDashboard: () => void;
  onNavigateToWorkflow?: () => void;
  onNavigateToIssues?: () => void;
  onSelectProduct?: (product: Product) => void;
  onSelectModule?: (module: ModuleInstance) => void;
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
  activeModule,
  runModules = [],
  onNavigateToDashboard,
  onNavigateToWorkflow,
  onNavigateToIssues,
  onSelectProduct,
  onSelectModule,
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
      <header className="border-b border-slate-200 bg-white/95 backdrop-blur sticky top-0 z-20 h-16 px-4 flex items-center justify-between gap-3">
        {/* 左侧：展开收起按钮 + 智能多级联动面包屑导航 */}
        <div className="flex items-center space-x-2.5 min-w-0">
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

          {/* 多级联动面包屑导航 */}
          <nav className="flex items-center space-x-1.5 text-xs min-w-0" aria-label="Breadcrumb">
            {/* 1. 战略工程根节点 */}
            <button
              onClick={onNavigateToDashboard}
              title="返回战略驾驶舱"
              className={`flex items-center gap-1.5 font-bold tracking-tight transition cursor-pointer text-left truncate rounded-lg px-2 py-1 ${
                currentView === 'dashboard'
                  ? 'text-slate-900 bg-slate-100/90'
                  : 'text-slate-600 hover:text-emerald-700 hover:bg-slate-100'
              }`}
            >
              <Compass className="w-4 h-4 text-emerald-600 shrink-0" />
              <span className="truncate max-w-[130px] sm:max-w-[180px] md:max-w-[240px]">
                {currentInitiative?.name || '战略工程'}
              </span>
            </button>

            {/* 2. 产研工作台 / 产品节点 (在 workflow 或 module 视图时展示) */}
            {(currentView === 'workflow' || currentView === 'module') && currentProduct && (
              <>
                <ChevronRight className="w-3.5 h-3.5 text-slate-400 shrink-0" />

                {products && products.length > 1 && onSelectProduct ? (
                  /* 产品快速切换下拉 */
                  <div className="relative flex items-center">
                    <Package className="w-3.5 h-3.5 text-emerald-600 absolute left-2 pointer-events-none" />
                    <select
                      value={currentProduct.id}
                      onChange={(e) => {
                        const target = products.find((p) => p.id === e.target.value);
                        if (target) onSelectProduct(target);
                      }}
                      className="appearance-none font-semibold text-emerald-800 bg-emerald-50 hover:bg-emerald-100/80 border border-emerald-200 rounded-lg pl-7 pr-6 py-1 cursor-pointer text-xs focus:outline-none transition max-w-[140px] sm:max-w-[180px] truncate shadow-2xs"
                      title="点击切换当前战略下的矩阵产品"
                    >
                      {products.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                        </option>
                      ))}
                    </select>
                    <ChevronDown className="w-3 h-3 text-emerald-600 absolute right-1.5 pointer-events-none" />
                  </div>
                ) : (
                  <button
                    onClick={onNavigateToWorkflow}
                    className={`flex items-center gap-1 font-semibold rounded-lg px-2 py-1 transition cursor-pointer truncate ${
                      currentView === 'workflow'
                        ? 'text-emerald-800 bg-emerald-50 border border-emerald-200'
                        : 'text-slate-600 hover:text-emerald-700 hover:bg-slate-100'
                    }`}
                    title="产研工作台"
                  >
                    <Package className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                    <span className="truncate max-w-[120px] sm:max-w-[160px]">{currentProduct.name}</span>
                  </button>
                )}

                {currentView === 'workflow' && (
                  <span className="hidden sm:inline-block text-[11px] text-slate-400 font-medium ml-0.5">
                    / 产研工作台
                  </span>
                )}
              </>
            )}

            {/* 3. 子工序节点 (仅在 module 视图时展示) */}
            {currentView === 'module' && activeModule && (
              <>
                <ChevronRight className="w-3.5 h-3.5 text-slate-400 shrink-0" />

                {runModules && runModules.length > 1 && onSelectModule ? (
                  /* 工序快速切换下拉 */
                  <div className="relative flex items-center">
                    <Layers className="w-3.5 h-3.5 text-slate-500 absolute left-2 pointer-events-none" />
                    <select
                      value={activeModule.id}
                      onChange={(e) => {
                        const target = runModules.find((m) => m.id === e.target.value);
                        if (target) onSelectModule(target);
                      }}
                      className="appearance-none font-bold text-slate-800 bg-slate-100 hover:bg-slate-200/80 border border-slate-300 rounded-lg pl-7 pr-6 py-1 cursor-pointer text-xs focus:outline-none transition max-w-[150px] sm:max-w-[220px] truncate shadow-2xs"
                      title="点击快速跳转至同产品其他工序"
                    >
                      {runModules.map((m) => (
                        <option key={m.id} value={m.id}>
                          工序 {m.module_code} · {m.name} {m.phase === 'baselined' ? '✓' : ''}
                        </option>
                      ))}
                    </select>
                    <ChevronDown className="w-3 h-3 text-slate-500 absolute right-1.5 pointer-events-none" />
                  </div>
                ) : (
                  <div className="flex items-center gap-1 px-2 py-1 bg-slate-100 border border-slate-200 rounded-lg font-semibold text-slate-800 text-xs">
                    <Layers className="w-3.5 h-3.5 text-slate-500" />
                    <span>工序 {activeModule.module_code} · {activeModule.name}</span>
                  </div>
                )}
              </>
            )}

            {/* 4. 全局协同问题看板节点 */}
            {currentView === 'issues' && (
              <>
                <ChevronRight className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                <span className="font-semibold text-rose-700 bg-rose-50 border border-rose-200 px-2 py-0.5 rounded-md flex items-center gap-1">
                  <Bug className="w-3.5 h-3.5 text-rose-600" />
                  全局协同问题看板
                </span>
              </>
            )}
          </nav>
        </div>

        {/* 右侧功能操作区：根据不同视图场景精准展示，不常驻冗余信息 */}
        <div className="flex items-center space-x-2.5 shrink-0">
          {/* A. 战略驾驶舱专属：主体身份与战略底稿 + 周期核算切换 */}
          {currentView === 'dashboard' && currentInitiative && (
            <>
              {/* 1. 主体身份与战略底稿 */}
              <button
                onClick={() => setShowStrategyModal(true)}
                title="点击查看项目档案与战略目标"
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-50 hover:bg-emerald-50 text-slate-700 hover:text-emerald-700 border border-slate-200 hover:border-emerald-300 transition text-xs font-semibold cursor-pointer shadow-xs"
              >
                <FileText className="w-3.5 h-3.5 text-emerald-600" />
                <span className="hidden sm:inline">项目档案与战略目标</span>
              </button>

              {/* 2. 周期切换下拉列表（仅在驾驶舱控制指标核算周期） */}
              <div className="relative flex items-center">
                <Calendar className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 pointer-events-none" />
                <select
                  value={selectedPeriod}
                  onChange={(e) => onPeriodChange?.(e.target.value)}
                  className="pl-8 pr-7 py-1.5 bg-slate-50 hover:bg-slate-100/80 border border-slate-200 hover:border-slate-300 rounded-lg text-xs font-semibold text-slate-800 focus:outline-none focus:border-emerald-500 cursor-pointer appearance-none shadow-xs transition"
                  title="选择驾驶舱经营指标核算周期"
                >
                  <option value="MTD">本月 (MTD)</option>
                  <option value="QTD">本季 (QTD)</option>
                  <option value="YTD">本年 (YTD)</option>
                  <option value="lifetime">累计 (全部)</option>
                </select>
                <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-2 pointer-events-none" />
              </div>
            </>
          )}

          {/* B. 产研工作台专属：轻量战略参考 + 协同问题快捷入口 + 返回驾驶舱 */}
          {currentView === 'workflow' && (
            <>
              {currentInitiative && (
                <button
                  onClick={() => setShowStrategyModal(true)}
                  title="参考顶层战略背景与目标"
                  className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-white hover:bg-slate-50 text-slate-600 hover:text-slate-900 border border-slate-200 transition text-xs font-medium cursor-pointer shadow-2xs"
                >
                  <FileText className="w-3.5 h-3.5 text-slate-500" />
                  <span className="hidden md:inline">战略目标参考</span>
                </button>
              )}

              {onNavigateToIssues && (
                <button
                  onClick={onNavigateToIssues}
                  title="查看协同问题与卡点"
                  className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-white hover:bg-rose-50 text-slate-600 hover:text-rose-700 border border-slate-200 hover:border-rose-200 transition text-xs font-medium cursor-pointer shadow-2xs"
                >
                  <Bug className="w-3.5 h-3.5 text-rose-500" />
                  <span className="hidden md:inline">协同问题</span>
                </button>
              )}

              <button
                onClick={onNavigateToDashboard}
                className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 transition text-xs font-semibold cursor-pointer shadow-xs"
                title="返回战略驾驶舱"
              >
                <ArrowLeft className="w-3.5 h-3.5 text-slate-600" />
                <span className="hidden sm:inline">返回驾驶舱</span>
              </button>
            </>
          )}

          {/* C. 子工序空间专属：快速返回工作台 */}
          {currentView === 'module' && onNavigateToWorkflow && (
            <button
              onClick={onNavigateToWorkflow}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white transition text-xs font-semibold cursor-pointer shadow-xs"
              title="返回当前产品的产研工作台"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">返回工作台</span>
            </button>
          )}

          {/* D. 全局协同问题看板专属：返回战略驾驶舱 */}
          {currentView === 'issues' && (
            <button
              onClick={onNavigateToDashboard}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 transition text-xs font-semibold cursor-pointer shadow-xs"
              title="返回战略驾驶舱"
            >
              <ArrowLeft className="w-3.5 h-3.5 text-slate-600" />
              <span>返回驾驶舱</span>
            </button>
          )}
        </div>
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
                <h3 className="text-sm font-bold text-slate-900">项目档案与战略目标</h3>
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
              {/* 一、基本信息 */}
              <div className="space-y-2">
                <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block font-mono">
                  一、基本信息
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

              {/* 二、战略目标与定位 */}
              <div className="space-y-3">
                <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block font-mono">
                  二、战略目标与定位
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
                    三、本地代码与工作区
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
                    <span>{isSyncing ? '同步中...' : syncStatus || '刷新本地文件'}</span>
                  </button>
                </div>

                <div className="p-3.5 bg-slate-900 text-slate-100 rounded-xl border border-slate-800 space-y-2 text-xs font-mono">
                  <div className="flex items-center gap-1.5 text-emerald-400 font-bold">
                    <FolderGit2 className="w-3.5 h-3.5 shrink-0" />
                    <span className="truncate">data/workspaces/{currentInitiative.id}/</span>
                  </div>
                  <div className="text-[11px] text-slate-400 space-y-1 pl-1 border-l-2 border-slate-700">
                    <div>├── <span className="text-slate-300">00_战略工程底稿与公共资产/</span> (底稿/公共市场调研/生态闭环)</div>
                    <div>└── <span className="text-slate-300">products/</span> (子产品文件夹严格独立隔离)</div>
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
              <span className="text-[11px] text-slate-400">战略目标由负责人统一把控与校准</span>
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
