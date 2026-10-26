import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Product, WorkflowRun, ModuleInstance, WorkflowTemplate } from '../types';
import { PhaseBadge } from '../components/StatusBadge';
import {
  Lock,
  MessageSquare,
  FileText,
  AlertTriangle,
  ArrowRight,
  ShieldAlert,
  ChevronRight,
  RefreshCw,
  Plus,
  Play,
  Briefcase,
  Layers,
  ChevronDown,
  X,
  Archive,
  CheckCircle2,
  Ban,
  ArrowLeft,
  Edit3,
  AlertCircle
} from 'lucide-react';

interface WorkflowViewProps {
  currentProduct?: Product | null;
  allProducts: Product[];
  initialRunId?: string;
  onSelectProduct: (p: Product) => void;
  onSelectModule: (module: ModuleInstance, allModules: ModuleInstance[]) => void;
  onBackToDashboard: () => void;
}

export const WorkflowView: React.FC<WorkflowViewProps> = ({
  currentProduct,
  allProducts,
  initialRunId,
  onSelectProduct,
  onSelectModule,
  onBackToDashboard
}) => {
  const [productRuns, setProductRuns] = useState<WorkflowRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<WorkflowRun | null>(null);
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([]);
  const [loading, setLoading] = useState(true);

  // New run modal
  const [showNewRunModal, setShowNewRunModal] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState('fast-iteration');
  const [runName, setRunName] = useState('');

  // Rename modal
  const [showRenameModal, setShowRenameModal] = useState(false);
  const [renameValue, setRenameValue] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  const activeProduct = currentProduct || allProducts[0];

  const activeRun = productRuns.find(r => r.status === 'in_progress');
  const archivedRuns = productRuns.filter(r => r.status !== 'in_progress');
  const isActiveRunSelected = selectedRun?.status === 'in_progress';

  useEffect(() => {
    if (activeProduct) {
      loadProductRuns(activeProduct.id, initialRunId);
    }
  }, [activeProduct?.id, initialRunId]);

  const loadProductRuns = async (prodId: string, runIdToPick?: string) => {
    try {
      setLoading(true);
      const [runsList, tplList] = await Promise.all([
        api.getRuns(prodId),
        api.getTemplates()
      ]);
      setProductRuns(runsList);
      setTemplates(tplList);

      if (runsList.length > 0) {
        const inProgress = runsList.find(r => r.status === 'in_progress');
        const targetRun = runIdToPick
          ? runsList.find(r => r.id === runIdToPick) || inProgress || runsList[0]
          : inProgress || runsList[0];
        
        const detailedRun = await api.getRun(targetRun.id);
        setSelectedRun(detailedRun);
      } else {
        setSelectedRun(null);
      }
    } catch (e: any) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectRunTab = async (runId: string) => {
    try {
      setLoading(true);
      const detailedRun = await api.getRun(runId);
      setSelectedRun(detailedRun);
    } catch (e: any) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateRun = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProduct || !runName.trim()) return;

    if (activeRun) {
      alert(`当前已有进行中的活跃迭代「${activeRun.name}」，单产品不允许并行推进多个迭代。\n请在完成当前迭代封版或废弃后再开启新一期。`);
      return;
    }

    try {
      setActionLoading(true);
      const created = await api.createRun({
        product_id: activeProduct.id,
        template_id: selectedTemplateId,
        name: runName.trim()
      });
      setShowNewRunModal(false);
      setRunName('');
      await loadProductRuns(activeProduct.id, created.id);
    } catch (err: any) {
      alert(`创建迭代周期失败: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleRenameRun = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRun || !renameValue.trim()) return;
    try {
      setActionLoading(true);
      const updated = await api.updateRun(selectedRun.id, { name: renameValue.trim() });
      setSelectedRun(prev => prev ? { ...prev, name: updated.name } : null);
      setProductRuns(prev => prev.map(r => r.id === updated.id ? { ...r, name: updated.name } : r));
      setShowRenameModal(false);
    } catch (err: any) {
      alert(`重命名失败: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleCompleteRun = async () => {
    if (!selectedRun) return;
    const confirmMsg = `确认将当前迭代「${selectedRun.name}」正式完成并封版？\n\n封版后该迭代将归档锁定为历史只读快照，并解锁名额开启下一期新迭代。`;
    if (!window.confirm(confirmMsg)) return;

    try {
      setActionLoading(true);
      const updated = await api.updateRun(selectedRun.id, { status: 'completed' });
      await loadProductRuns(activeProduct.id, updated.id);
    } catch (err: any) {
      alert(`封版操作失败: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleAbandonRun = async () => {
    if (!selectedRun) return;
    const confirmMsg = `确认废弃当前迭代「${selectedRun.name}」？\n\n废弃后该迭代将终止并归档，释放名额允许重新立项新迭代。`;
    if (!window.confirm(confirmMsg)) return;

    try {
      setActionLoading(true);
      const updated = await api.updateRun(selectedRun.id, { status: 'abandoned' });
      await loadProductRuns(activeProduct.id, updated.id);
    } catch (err: any) {
      alert(`废弃操作失败: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  if (loading && !selectedRun && productRuns.length === 0) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-16 text-center text-slate-500">
        <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-2 text-emerald-600" />
        <p className="text-sm">加载产品迭代工作台中...</p>
      </div>
    );
  }

  if (!activeProduct) {
    return (
      <div className="max-w-4xl mx-auto py-12 text-center text-slate-500">
        <p>未指定产品，请先从战略驾驶舱选择产品。</p>
        <button
          onClick={onBackToDashboard}
          className="mt-4 px-4 py-2 bg-slate-900 text-white rounded-lg text-xs"
        >
          返回战略驾驶舱
        </button>
      </div>
    );
  }

  const baselinedCount = selectedRun?.modules?.filter(m => m.phase === 'baselined').length || 0;
  const totalModules = selectedRun?.modules?.length || 1;
  const progressPercent = Math.round((baselinedCount / totalModules) * 100);

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      {/* 工作台顶部：专一产品标识与状态 */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white border border-slate-200 rounded-2xl p-5 shadow-xs">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-600 shrink-0">
            <Briefcase className="w-5 h-5" />
          </div>

          <div>
            <div className="flex items-center gap-2 mb-0.5">
              <span className="px-2 py-0.5 rounded text-xs font-mono font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
                {activeProduct.code}
              </span>
              <h1 className="text-base font-bold text-slate-900">
                {activeProduct.name}
              </h1>
              <span className="text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-600 font-medium hidden sm:inline">
                产研协同工作台
              </span>
            </div>

            <p className="text-xs text-slate-500 line-clamp-1">
              {activeProduct.description || '当前产品全生命周期工序与定稿空间'}
            </p>
          </div>
        </div>

        {/* 右侧：如果没有进行中的活跃迭代，提供显眼的开启新一期迭代按钮 */}
        {!activeRun && (
          <button
            onClick={() => setShowNewRunModal(true)}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white transition shadow-xs self-start md:self-center cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            开启新一期迭代
          </button>
        )}
      </div>

      {/* 迭代周期主控条：单一活跃迭代 + 生命周期操作 + 历史归档回溯 */}
      <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-3 border-b border-slate-100">
          {/* 左侧：当前查看的迭代标题、状态标签、编辑重命名 */}
          <div className="space-y-1.5">
            <div className="flex items-center gap-2.5">
              {isActiveRunSelected ? (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  当前唯一活跃迭代 (Active)
                </span>
              ) : selectedRun?.status === 'completed' ? (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200">
                  <Archive className="w-3.5 h-3.5 text-slate-500" />
                  历史归档 (已封版发布 · 只读)
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200">
                  <AlertCircle className="w-3.5 h-3.5 text-amber-500" />
                  已废弃归档 (已终止 · 只读)
                </span>
              )}

              <span className="text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-600 font-mono">
                模板: {selectedRun?.template_id || '标准工序'}
              </span>
            </div>

            <div className="flex items-center gap-2 pt-0.5">
              <h2 className="text-base font-bold text-slate-900">
                {selectedRun?.name || '暂无迭代周期'}
              </h2>
              {isActiveRunSelected && selectedRun && (
                <button
                  onClick={() => {
                    setRenameValue(selectedRun.name);
                    setShowRenameModal(true);
                  }}
                  title="修改迭代名称与范围"
                  className="p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition cursor-pointer"
                >
                  <Edit3 className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>

          {/* 右侧：生命周期操作按钮（完成封版 / 废弃终止）与历史归档回溯下拉 */}
          <div className="flex flex-wrap items-center gap-2.5">
            {/* 如果正在查看历史归档，提供一键返回活跃迭代按钮 */}
            {!isActiveRunSelected && activeRun && (
              <button
                onClick={() => handleSelectRunTab(activeRun.id)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-200 transition cursor-pointer"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                返回进行中活跃迭代
              </button>
            )}

            {/* 如果当前是活跃迭代，提供封版与废弃闭环操作 */}
            {isActiveRunSelected && (
              <>
                <button
                  onClick={handleAbandonRun}
                  disabled={actionLoading}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium text-slate-600 hover:text-rose-700 hover:bg-rose-50 border border-slate-200 hover:border-rose-200 transition cursor-pointer disabled:opacity-50"
                  title="废弃当前迭代后，方可重新立项新迭代"
                >
                  <Ban className="w-3.5 h-3.5 text-rose-500" />
                  废弃此迭代
                </button>

                <button
                  onClick={handleCompleteRun}
                  disabled={actionLoading}
                  className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white transition shadow-xs cursor-pointer disabled:opacity-50"
                  title="所有工序就绪后封版归档，解锁下一期迭代"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  完成并封版
                </button>
              </>
            )}

            {/* 历史归档迭代回溯下拉列表 */}
            {archivedRuns.length > 0 && (
              <div className="relative">
                <select
                  value={selectedRun?.id || ''}
                  onChange={(e) => handleSelectRunTab(e.target.value)}
                  className="pl-3 pr-7 py-1.5 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-xl text-xs font-medium text-slate-700 focus:outline-none cursor-pointer appearance-none shadow-2xs"
                >
                  {activeRun && <option value={activeRun.id}>★ 当前活跃: {activeRun.name}</option>}
                  {archivedRuns.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.status === 'completed' ? '📦 已封版: ' : '🚫 已废弃: '} {r.name}
                    </option>
                  ))}
                </select>
                <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-2.5 top-2.5 pointer-events-none" />
              </div>
            )}
          </div>
        </div>

        {/* 底部基线达成率进度条 */}
        {selectedRun && (
          <div className="flex items-center justify-between text-xs text-slate-500">
            <div className="flex items-center gap-2">
              <span>工序定稿达成率:</span>
              <span className="font-mono font-bold text-slate-900">{baselinedCount}/{totalModules}</span>
              <span className="text-slate-400">({progressPercent}%)</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-36 sm:w-48 bg-slate-100 rounded-full h-2 overflow-hidden border border-slate-200">
                <div className="bg-emerald-500 h-2 transition-all duration-500" style={{ width: `${progressPercent}%` }} />
              </div>
              <button
                onClick={() => handleSelectRunTab(selectedRun.id)}
                className="p-1 text-slate-400 hover:text-slate-700 rounded hover:bg-slate-100 transition cursor-pointer"
                title="刷新"
              >
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 历史归档快照只读提示条 */}
      {!isActiveRunSelected && selectedRun && (
        <div className="p-3.5 rounded-xl bg-slate-100 border border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs text-slate-700">
          <div className="flex items-center gap-2">
            <Archive className="w-4 h-4 text-slate-500 shrink-0" />
            <span>
              <strong>历史归档快照模式：</strong> 当前查看的「{selectedRun.name}」已于{' '}
              {new Date(selectedRun.updated_at).toLocaleDateString()} 封版归档，所有工序已正式定稿只读，仅供追溯查阅。
            </span>
          </div>
          {activeRun && (
            <button
              onClick={() => handleSelectRunTab(activeRun.id)}
              className="px-2.5 py-1 rounded-lg bg-white border border-slate-300 hover:border-emerald-500 text-slate-800 text-xs font-semibold cursor-pointer shrink-0 self-start sm:self-auto"
            >
              返回当前活跃迭代
            </button>
          )}
        </div>
      )}

      {/* 工序流程看板 (11 模块 Pipeline) */}
      {selectedRun ? (
        <div className="space-y-3">
          <div className="text-xs text-slate-500 flex items-center justify-between px-1">
            <span>当前迭代工序链条 (按预设门禁与前置依赖依次解锁，点击进入人机协作室)：</span>
            <span className="text-slate-400 font-mono text-[11px]">
              {selectedRun.modules.length} 个工序节点
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {selectedRun.modules.map(mod => {
              const isLocked = !mod.is_unlocked;
              const hasBlockingIssues = (mod.blocking_issues_count || 0) > 0;
              const hasOpenIssues = (mod.open_issues_count || 0) > 0;
              const isBaselined = mod.phase === 'baselined';

              return (
                <div
                  key={mod.id}
                  onClick={() => !isLocked && onSelectModule(mod, selectedRun.modules)}
                  className={`border rounded-2xl p-4 transition-all flex flex-col justify-between space-y-3 shadow-xs ${
                    isLocked
                      ? 'bg-slate-50/80 border-slate-200 opacity-60 cursor-not-allowed'
                      : isBaselined
                      ? 'bg-white border-emerald-200 hover:border-emerald-400 hover:shadow-md cursor-pointer'
                      : 'bg-white border-slate-200 hover:border-emerald-300 hover:shadow-md cursor-pointer'
                  }`}
                >
                  <div className="space-y-2">
                    <div className="flex items-center justify-between gap-1 flex-wrap">
                      <div className="flex items-center gap-1.5">
                        <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-slate-100 text-slate-800">
                          工序 {mod.module_code}
                        </span>
                        {mod.execution_mode === 'human_driven' ? (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-50 text-blue-700 border border-blue-200" title="由人工专家使用专业工具作业，交付完整成果">
                            专家主导
                          </span>
                        ) : mod.execution_mode === 'hybrid' ? (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-teal-50 text-teal-700 border border-teal-200" title="人机协同联合执行">
                            人机协同
                          </span>
                        ) : (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-purple-50 text-purple-700 border border-purple-200" title="由专业 AI 智能体协同推演并生成成果">
                            AI 智能体主导
                          </span>
                        )}
                      </div>
                      <PhaseBadge phase={mod.phase} />
                    </div>

                    {mod.is_upstream_stale && (
                      <div className="px-2 py-1 rounded-md bg-amber-50 border border-amber-300 text-amber-800 text-[11px] font-medium flex items-center gap-1.5">
                        <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                        <span className="truncate">上游规范已更新 · 待同步</span>
                      </div>
                    )}

                    <h3 className="text-sm font-bold text-slate-900 flex items-center gap-1.5">
                      {isLocked && <Lock className="w-3.5 h-3.5 text-slate-400 shrink-0" />}
                      <span className="truncate">{mod.name}</span>
                    </h3>

                    {mod.dependencies.length > 0 && (
                      <p className="text-[11px] text-slate-400 font-mono">
                        依赖前置: {mod.dependencies.join(', ')}
                      </p>
                    )}
                  </div>

                  <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      {hasBlockingIssues ? (
                        <span className="flex items-center gap-1 text-rose-600 font-semibold font-mono text-[11px]">
                          <ShieldAlert className="w-3.5 h-3.5" />
                          {mod.blocking_issues_count} 阻断
                        </span>
                      ) : hasOpenIssues ? (
                        <span className="flex items-center gap-1 text-amber-600 font-mono text-[11px]">
                          <AlertTriangle className="w-3.5 h-3.5" />
                          {mod.open_issues_count}
                        </span>
                      ) : (
                        <span className="text-slate-400 text-[11px]">无阻断卡点</span>
                      )}
                    </div>

                    {!isLocked && (
                      <span className="text-emerald-700 hover:text-emerald-800 text-[11px] font-semibold flex items-center gap-0.5">
                        {isActiveRunSelected ? '进入协同' : '查看工序'}
                        <ArrowRight className="w-3 h-3" />
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        <div className="bg-white border border-slate-200 rounded-2xl p-12 text-center text-slate-500 space-y-3">
          <Layers className="w-10 h-10 mx-auto text-slate-400" />
          <p className="text-sm font-semibold text-slate-800">该产品暂无迭代运行</p>
          <p className="text-xs text-slate-400 max-w-sm mx-auto">
            每个产品同一时间只允许运行一个活跃迭代。点击下方按钮从模板实例化开启新一期迭代。
          </p>
          <button
            onClick={() => setShowNewRunModal(true)}
            className="mt-2 inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white transition cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            开启新一期迭代
          </button>
        </div>
      )}

      {/* 弹窗 1: 开启新一期迭代 */}
      {showNewRunModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 w-full max-w-md rounded-2xl p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-100">
              <h3 className="font-semibold text-slate-900 text-base flex items-center gap-2">
                <Plus className="w-5 h-5 text-emerald-600" />
                开启新一期迭代周期
              </h3>
              <button onClick={() => setShowNewRunModal(false)} className="text-slate-400 hover:text-slate-600 cursor-pointer">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateRun} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">所属矩阵产品</label>
                <input
                  disabled
                  value={`${activeProduct.name} (${activeProduct.code})`}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-500 cursor-not-allowed font-medium"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">选择工序模板 *</label>
                <select
                  value={selectedTemplateId}
                  onChange={e => setSelectedTemplateId(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 focus:bg-white focus:outline-none focus:border-emerald-500 cursor-pointer"
                >
                  {templates.map(t => (
                    <option key={t.id} value={t.id}>
                      {t.name} ({t.modules_config.length} 模块)
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">迭代周期名称 *</label>
                <input
                  type="text"
                  required
                  placeholder="例：v1.1 本地化支付功能迭代"
                  value={runName}
                  onChange={e => setRunName(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 focus:bg-white focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowNewRunModal(false)}
                  className="px-3 py-1.5 rounded-lg text-xs text-slate-600 hover:bg-slate-100 cursor-pointer"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-1.5 rounded-lg text-xs font-medium bg-emerald-600 hover:bg-emerald-500 text-white cursor-pointer disabled:opacity-50"
                >
                  {actionLoading ? '实例化中...' : '确认开启并实例化'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 弹窗 2: 修改活跃迭代名称 */}
      {showRenameModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 w-full max-w-sm rounded-2xl p-5 shadow-2xl">
            <div className="flex items-center justify-between mb-3 pb-2 border-b border-slate-100">
              <h3 className="font-semibold text-slate-900 text-sm flex items-center gap-1.5">
                <Edit3 className="w-4 h-4 text-emerald-600" />
                修改当前迭代名称
              </h3>
              <button onClick={() => setShowRenameModal(false)} className="text-slate-400 hover:text-slate-600 cursor-pointer">
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleRenameRun} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">迭代名称 *</label>
                <input
                  type="text"
                  required
                  value={renameValue}
                  onChange={e => setRenameValue(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 focus:bg-white focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowRenameModal(false)}
                  className="px-3 py-1.5 rounded-lg text-xs text-slate-600 hover:bg-slate-100 cursor-pointer"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-1.5 rounded-lg text-xs font-medium bg-emerald-600 hover:bg-emerald-500 text-white cursor-pointer disabled:opacity-50"
                >
                  保存修改
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
