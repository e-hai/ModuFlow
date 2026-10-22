import React, { useState } from 'react';
import { X, AlertTriangle, Bug } from 'lucide-react';
import { ModuleInstance } from '../types';

interface NewIssueModalProps {
  currentModule: ModuleInstance;
  allModules: ModuleInstance[];
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (issueData: any) => Promise<void>;
}

export const NewIssueModal: React.FC<NewIssueModalProps> = ({
  currentModule,
  allModules,
  isOpen,
  onClose,
  onSubmit
}) => {
  if (!isOpen) return null;

  const [title, setTitle] = useState('');
  const [targetModuleId, setTargetModuleId] = useState(
    allModules.find(m => m.id !== currentModule.id)?.id || currentModule.id
  );
  const [severity, setSeverity] = useState('critical');
  const [priority, setPriority] = useState('P0');
  const [steps, setSteps] = useState('1. 打开页面\n2. 点击按钮');
  const [expected, setExpected] = useState('正常完成操作');
  const [actual, setActual] = useState('发生异常报错');
  const [osEnv, setOsEnv] = useState('Android 11 / Chrome 122');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;

    setIsSubmitting(true);
    try {
      await onSubmit({
        title,
        source_module_id: currentModule.id,
        target_module_id: targetModuleId,
        reporter: 'QA 测试员',
        reporter_role: 'tester',
        category: 'bug',
        severity,
        priority,
        description: {
          summary: title,
          steps_to_reproduce: steps.split('\n').filter(s => s.trim()),
          expected,
          actual,
          environment: { os: osEnv }
        }
      });
      onClose();
    } catch (err: any) {
      alert(`创建失败: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white border border-slate-200 w-full max-w-xl rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50/50">
          <div className="flex items-center gap-2 text-rose-600">
            <Bug className="w-5 h-5" />
            <h3 className="font-semibold text-slate-900">提报结构化反馈 / 跨模块缺陷 (Issue)</h3>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 cursor-pointer">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4 overflow-y-auto">
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">问题标题 *</label>
            <input
              type="text"
              required
              placeholder="例：登录页面在 Android 11 下点击登录后闪退"
              value={title}
              onChange={e => setTitle(e.target.value)}
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-900 focus:bg-white focus:outline-none focus:border-rose-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">发现模块 (来源)</label>
              <input
                disabled
                value={currentModule.name}
                className="w-full bg-slate-100 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-500 cursor-not-allowed"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-rose-700 mb-1">责任/修复模块 (目标) *</label>
              <select
                value={targetModuleId}
                onChange={e => setTargetModuleId(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 focus:bg-white focus:outline-none focus:border-rose-500"
              >
                {allModules.map(m => (
                  <option key={m.id} value={m.id}>
                    {m.module_code} {m.name} {m.id === currentModule.id ? '(本模块)' : ''}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">严重度 (Severity)</label>
              <select
                value={severity}
                onChange={e => setSeverity(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900"
              >
                <option value="critical">Critical (阻断发布/基线)</option>
                <option value="major">Major (严重缺陷)</option>
                <option value="minor">Minor (次要优化)</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">优先级 (Priority)</label>
              <select
                value={priority}
                onChange={e => setPriority(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900"
              >
                <option value="P0">P0 (最高)</option>
                <option value="P1">P1 (高)</option>
                <option value="P2">P2 (中)</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">复现步骤 (Steps)</label>
            <textarea
              rows={3}
              value={steps}
              onChange={e => setSteps(e.target.value)}
              className="w-full bg-slate-50 border border-slate-300 rounded-lg p-2.5 text-xs text-slate-900 font-mono focus:bg-white focus:outline-none focus:border-rose-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">预期行为</label>
              <input
                value={expected}
                onChange={e => setExpected(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 focus:bg-white focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">实际行为</label>
              <input
                value={actual}
                onChange={e => setActual(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 focus:bg-white focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">测试环境</label>
            <input
              value={osEnv}
              onChange={e => setOsEnv(e.target.value)}
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 focus:bg-white focus:outline-none"
            />
          </div>

          <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-[11px] text-amber-800 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-amber-600" />
            <span>
              若选择 Critical/Major 级别，目标模块如果已处于基线锁定（baselined）状态，将自动触发**回退至协作研讨（discussing）**，以确保缺陷彻底关闭前不会带病上线。
            </span>
          </div>

          <div className="pt-2 flex justify-end gap-2 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-xs font-medium text-slate-600 hover:bg-slate-100 transition cursor-pointer"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-4 py-2 rounded-lg text-xs font-medium bg-rose-600 hover:bg-rose-500 text-white transition disabled:opacity-50 cursor-pointer"
            >
              {isSubmitting ? '提交中...' : '确认提报并派发'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
