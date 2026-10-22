import React, { useState } from 'react';
import {
  Compass,
  Plus,
  Settings,
  Pencil,
  Trash2,
  Check,
  X,
  Layers,
  Building2,
  AlertTriangle
} from 'lucide-react';
import { StrategicInitiative } from '../types';

interface SidebarProps {
  isOpen: boolean;
  initiatives: StrategicInitiative[];
  currentInitiative: StrategicInitiative | null;
  onSelectInitiative: (initId: string) => void;
  onOpenNewInitiativeModal: () => void;
  onRenameInitiative: (initId: string, newName: string) => Promise<void>;
  onDeleteInitiative: (initId: string) => Promise<void>;
  onOpenSettingsModal: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  isOpen,
  initiatives,
  currentInitiative,
  onSelectInitiative,
  onOpenNewInitiativeModal,
  onRenameInitiative,
  onDeleteInitiative,
  onOpenSettingsModal
}) => {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState('');
  const [isSubmittingRename, setIsSubmittingRename] = useState(false);

  // Delete confirmation state
  const [deletingInit, setDeletingInit] = useState<StrategicInitiative | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  if (!isOpen) return null;

  const handleStartRename = (e: React.MouseEvent, init: StrategicInitiative) => {
    e.stopPropagation();
    setEditingId(init.id);
    setEditingName(init.name);
  };

  const handleSaveRename = async (e?: React.MouseEvent | React.FormEvent) => {
    if (e) e.stopPropagation();
    if (!editingId || !editingName.trim() || isSubmittingRename) return;

    try {
      setIsSubmittingRename(true);
      await onRenameInitiative(editingId, editingName.trim());
      setEditingId(null);
    } catch (err: any) {
      alert(`重命名失败: ${err.message}`);
    } finally {
      setIsSubmittingRename(false);
    }
  };

  const handleCancelRename = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(null);
    setEditingName('');
  };

  const handleConfirmDelete = async () => {
    if (!deletingInit || isDeleting) return;
    try {
      setIsDeleting(true);
      await onDeleteInitiative(deletingInit.id);
      setDeletingInit(null);
    } catch (err: any) {
      alert(`删除失败: ${err.message}`);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <>
      <aside className="w-64 bg-white border-r border-slate-200 flex flex-col h-screen shrink-0 transition-all duration-300 z-30 select-none">
        {/* 顶部 Logo 品牌 - 纯净无多余入口 */}
        <div className="h-16 px-4 flex items-center gap-2.5 border-b border-slate-200 bg-white">
          <div className="w-7 h-7 rounded-lg bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-600">
            <Layers className="w-4 h-4 text-emerald-600" />
          </div>
          <span className="font-bold text-sm text-slate-900 tracking-tight">
            ModuFlow
          </span>
        </div>

        {/* 战略工程列表容器 (左侧界面仅包含战略工程列表) */}
        <div className="flex-1 overflow-y-auto p-3 space-y-3">
          <div className="flex items-center justify-between px-1">
            <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
              <Compass className="w-3.5 h-3.5 text-emerald-600" />
              战略工程列表
              <span className="text-[10px] text-slate-400 font-mono">({initiatives.length})</span>
            </span>
          </div>

          {/* 唯一的新增战略工程入口 */}
          <button
            onClick={onOpenNewInitiativeModal}
            className="w-full flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg border border-dashed border-slate-300 hover:border-emerald-500 bg-slate-50 hover:bg-emerald-50/50 text-slate-600 hover:text-emerald-700 text-xs font-medium transition cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5 text-emerald-600" />
            <span>新建战略工程</span>
          </button>

          {/* 工程卡片列表 */}
          <div className="space-y-1.5">
            {initiatives.length === 0 ? (
              <div className="py-10 text-center text-slate-400 space-y-2">
                <Building2 className="w-8 h-8 mx-auto text-slate-300" />
                <p className="text-xs">暂无战略工程</p>
                <p className="text-[11px] text-slate-400">点击上方按钮创建首个战略工程</p>
              </div>
            ) : (
              initiatives.map(init => {
                const isActive = currentInitiative?.id === init.id;
                const isEditing = editingId === init.id;

                return (
                  <div
                    key={init.id}
                    onClick={() => !isEditing && onSelectInitiative(init.id)}
                    className={`group relative p-2.5 rounded-xl border transition cursor-pointer ${
                      isActive
                        ? 'bg-emerald-50/80 border-emerald-300 text-slate-900 shadow-xs'
                        : 'bg-white hover:bg-slate-50/80 border-slate-200 hover:border-slate-300 text-slate-700'
                    }`}
                  >
                    {isEditing ? (
                      /* 交互 2: 重命名输入状态 */
                      <div className="space-y-2" onClick={e => e.stopPropagation()}>
                        <input
                          type="text"
                          autoFocus
                          value={editingName}
                          onChange={e => setEditingName(e.target.value)}
                          onKeyDown={e => {
                            if (e.key === 'Enter') handleSaveRename();
                            if (e.key === 'Escape') setEditingId(null);
                          }}
                          placeholder="输入战略工程名称..."
                          className="w-full bg-white border border-emerald-500 rounded-md px-2 py-1 text-xs text-slate-900 font-semibold focus:outline-none focus:ring-1 focus:ring-emerald-500"
                        />
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            type="button"
                            onClick={handleCancelRename}
                            className="px-2 py-0.5 rounded text-[11px] text-slate-500 hover:bg-slate-100"
                          >
                            取消
                          </button>
                          <button
                            type="button"
                            disabled={isSubmittingRename || !editingName.trim()}
                            onClick={handleSaveRename}
                            className="px-2 py-0.5 rounded text-[11px] bg-emerald-600 hover:bg-emerald-500 text-white font-medium flex items-center gap-1 disabled:opacity-50"
                          >
                            <Check className="w-3 h-3" />
                            {isSubmittingRename ? '保存中' : '保存'}
                          </button>
                        </div>
                      </div>
                    ) : (
                      /* 常规工程卡片展示 */
                      <div>
                        <div className="flex items-start justify-between gap-1.5">
                          <div className="flex-1 min-w-0 pr-1">
                            <h4 className="text-xs font-bold truncate leading-snug">
                              {init.name}
                            </h4>
                          </div>

                          {/* 悬浮/激活操作按钮：重命名与删除 */}
                          <div
                            className={`flex items-center gap-0.5 shrink-0 transition-opacity ${
                              isActive ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
                            }`}
                          >
                            <button
                              type="button"
                              onClick={e => handleStartRename(e, init)}
                              title="重命名工程"
                              className="p-1 rounded hover:bg-white text-slate-400 hover:text-emerald-700 transition"
                            >
                              <Pencil className="w-3 h-3" />
                            </button>
                            <button
                              type="button"
                              onClick={e => {
                                e.stopPropagation();
                                setDeletingInit(init);
                              }}
                              title="删除工程"
                              className="p-1 rounded hover:bg-white text-slate-400 hover:text-rose-600 transition"
                            >
                              <Trash2 className="w-3 h-3" />
                            </button>
                          </div>
                        </div>

                        {/* 次级信息：预算、产品数与状态 */}
                        <div className="mt-1.5 flex items-center justify-between text-[11px] text-slate-500">
                          <div className="flex items-center gap-1.5">
                            <span className="font-mono text-[10px] text-slate-600">
                              ¥{(init.budget / 10000).toFixed(0)}万
                            </span>
                            <span>•</span>
                            <span className="text-[10px] text-slate-500">
                              {init.product_count || 0} 产品
                            </span>
                          </div>

                          <span
                            className={`text-[10px] font-mono px-1 py-0.2 rounded border ${
                              isActive
                                ? 'bg-emerald-100 text-emerald-800 border-emerald-300'
                                : 'bg-slate-100 text-slate-500 border-slate-200'
                            }`}
                          >
                            {init.status}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* 底部设置入口 */}
        <div className="p-3 border-t border-slate-200 bg-slate-50/50">
          <button
            onClick={onOpenSettingsModal}
            className="w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-xs font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition group cursor-pointer"
          >
            <div className="flex items-center gap-2">
              <Settings className="w-4 h-4 text-slate-400 group-hover:text-emerald-600 transition" />
              <span>设置</span>
            </div>
            <span className="font-mono text-[10px] text-slate-400 group-hover:text-slate-600">v0.1</span>
          </button>
        </div>
      </aside>

      {/* 交互 3: 删除工程二次确认弹窗 */}
      {deletingInit && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 w-full max-w-sm rounded-2xl p-5 shadow-2xl space-y-4 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-xl bg-rose-50 border border-rose-200 flex items-center justify-center text-rose-600 shrink-0">
                <AlertTriangle className="w-5 h-5 text-rose-600" />
              </div>
              <div className="space-y-1">
                <h3 className="font-bold text-slate-900 text-sm">
                  确认删除战略工程？
                </h3>
                <p className="text-xs text-slate-500 leading-relaxed">
                  即将删除 <strong className="text-slate-800 font-semibold">【{deletingInit.name}】</strong>。
                  工程下包含的所有矩阵产品、产研模块及交付物数据将一并清理，此操作不可撤销。
                </p>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
              <button
                type="button"
                disabled={isDeleting}
                onClick={() => setDeletingInit(null)}
                className="px-3 py-1.5 rounded-lg text-xs text-slate-600 hover:bg-slate-100 transition cursor-pointer"
              >
                取消
              </button>
              <button
                type="button"
                disabled={isDeleting}
                onClick={handleConfirmDelete}
                className="px-3.5 py-1.5 rounded-lg text-xs font-medium bg-rose-600 hover:bg-rose-500 text-white transition flex items-center gap-1 cursor-pointer disabled:opacity-50"
              >
                {isDeleting ? '正在删除...' : '确认彻底删除'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
