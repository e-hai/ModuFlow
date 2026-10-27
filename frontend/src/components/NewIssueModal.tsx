import React, { useState } from 'react';
import { X, AlertTriangle, Bug, GitPullRequest, ArrowLeftRight } from 'lucide-react';
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

  // If current is 06 (Design) or 07 (Dev), default to requirement_cr targeting 05 (PRD)
  const isDownstream = ['06', '07', '08'].includes(currentModule.module_code);
  const prdModule = allModules.find(m => m.module_code === '05');

  const [category, setCategory] = useState<'requirement_cr' | 'bug'>(
    isDownstream ? 'requirement_cr' : 'bug'
  );
  const [title, setTitle] = useState('');
  const [targetModuleId, setTargetModuleId] = useState(
    isDownstream && prdModule
      ? prdModule.id
      : (allModules.find(m => m.id !== currentModule.id)?.id || currentModule.id)
  );
  const [severity, setSeverity] = useState('major');
  const [priority, setPriority] = useState('P1');

  // Bug specific fields
  const [steps, setSteps] = useState('1. 打开页面\n2. 点击按钮');
  const [expected, setExpected] = useState('正常完成操作');
  const [actual, setActual] = useState('发生异常报错');
  const [osEnv, setOsEnv] = useState('Android 11 / iOS 17 / Chrome 122');

  // Requirement CR specific fields
  const [unreasonablePoint, setUnreasonablePoint] = useState('');
  const [constraint, setConstraint] = useState('');
  const [suggestedChange, setSuggestedChange] = useState('');
  const [affectedModulesText, setAffectedModulesText] = useState('工序 05 产品需求定义, 工序 06 设计实现, 工序 07 开发实现');

  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;

    setIsSubmitting(true);
    try {
      const reporterRole = currentModule.module_code === '06'
        ? 'ux'
        : currentModule.module_code === '07'
          ? 'eng'
          : currentModule.module_code === '08'
            ? 'qa'
            : 'pm';

      const description = category === 'requirement_cr'
        ? {
            summary: title,
            unreasonable_point: unreasonablePoint,
            constraint: constraint,
            suggested_change: suggestedChange,
            affected_modules: affectedModulesText.split(',').map(s => s.trim()).filter(Boolean)
          }
        : {
            summary: title,
            steps_to_reproduce: steps.split('\n').filter(s => s.trim()),
            expected,
            actual,
            environment: { os: osEnv }
          };

      await onSubmit({
        title,
        source_module_id: currentModule.id,
        target_module_id: targetModuleId,
        reporter: `${currentModule.name} 团队`,
        reporter_role: reporterRole,
        category,
        severity,
        priority,
        description
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
          <div className="flex items-center gap-2 text-indigo-600">
            {category === 'requirement_cr' ? (
              <GitPullRequest className="w-5 h-5 text-indigo-600" />
            ) : (
              <Bug className="w-5 h-5 text-rose-600" />
            )}
            <h3 className="font-semibold text-slate-900">
              {category === 'requirement_cr' ? '发起需求变更请求 (CR · 逆向反馈)' : '发起协同缺陷与问题反馈'}
            </h3>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 cursor-pointer">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* 类别切换 Tab */}
        <div className="px-6 pt-4 pb-1">
          <div className="grid grid-cols-2 p-1 bg-slate-100 rounded-xl">
            <button
              type="button"
              onClick={() => {
                setCategory('requirement_cr');
                if (prdModule) setTargetModuleId(prdModule.id);
              }}
              className={`flex items-center justify-center gap-1.5 py-1.5 text-xs font-semibold rounded-lg transition cursor-pointer ${
                category === 'requirement_cr'
                  ? 'bg-white text-indigo-700 shadow-xs'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              <GitPullRequest className="w-3.5 h-3.5" />
              需求变更单 (CR · 反馈上游修订 PRD)
            </button>
            <button
              type="button"
              onClick={() => setCategory('bug')}
              className={`flex items-center justify-center gap-1.5 py-1.5 text-xs font-semibold rounded-lg transition cursor-pointer ${
                category === 'bug'
                  ? 'bg-white text-rose-700 shadow-xs'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              <Bug className="w-3.5 h-3.5" />
              质量缺陷 / 阻断 Bug
            </button>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4 overflow-y-auto">
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">
              {category === 'requirement_cr' ? '变更申请主题 *' : '问题标题 *'}
            </label>
            <input
              type="text"
              required
              placeholder={
                category === 'requirement_cr'
                  ? '例：建议将 PRD 中的全屏翻页动画调整为瀑布流分页，降低低端机渲染负载'
                  : '例：PRD 登录方案在弱网或多端场景下缺少重试与降级说明'
              }
              value={title}
              onChange={e => setTitle(e.target.value)}
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-900 focus:bg-white focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">提出工序 (发起方)</label>
              <input
                disabled
                value={`${currentModule.module_code} ${currentModule.name}`}
                className="w-full bg-slate-100 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-500 cursor-not-allowed"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-indigo-700 mb-1">
                目标工序 (指派修订方) *
              </label>
              <select
                value={targetModuleId}
                onChange={e => setTargetModuleId(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 focus:bg-white focus:outline-none focus:border-indigo-500"
              >
                {allModules.map(m => (
                  <option key={m.id} value={m.id}>
                    {m.module_code} {m.name} {m.id === currentModule.id ? '(本环节)' : ''}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">严重级别 / 紧迫度</label>
              <select
                value={severity}
                onChange={e => setSeverity(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900"
              >
                <option value="critical">Critical · 严重阻断 (必须在定稿前修订)</option>
                <option value="major">Major · 核心变更 (建议本轮修订基线)</option>
                <option value="minor">Minor · 轻微建议 (可纳入下轮演进)</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">处理优先级</label>
              <select
                value={priority}
                onChange={e => setPriority(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900"
              >
                <option value="P0">P0 (紧急优先)</option>
                <option value="P1">P1 (高)</option>
                <option value="P2">P2 (中)</option>
              </select>
            </div>
          </div>

          {category === 'requirement_cr' ? (
            /* 需求变更单专用表单 */
            <div className="space-y-3.5">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  1. 需求不合理点 / 体验或技术冲突说明 *
                </label>
                <textarea
                  rows={2}
                  required
                  placeholder="说明在设计或开发过程中发现的矛盾（如：双列瀑布流与分页按钮空间冲突，导致单手操作热区严重受挤压）"
                  value={unreasonablePoint}
                  onChange={e => setUnreasonablePoint(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg p-2.5 text-xs text-slate-900 focus:bg-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  2. 体验/设计/技术约束条件
                </label>
                <input
                  placeholder="例：iOS 灵动岛顶部安全区 ≥ 71pt / 客户端零推理成本原则 / 弱网离线不可连接"
                  value={constraint}
                  onChange={e => setConstraint(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 focus:bg-white focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  3. 建议修订方案 (供上游 Agent 参考) *
                </label>
                <textarea
                  rows={2}
                  required
                  placeholder="建议修改为：采用预加载 20 条的下拉无限瀑布流，底部仅保留触底加载提示，同步将分页状态机移出 PRD 契约"
                  value={suggestedChange}
                  onChange={e => setSuggestedChange(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg p-2.5 text-xs text-slate-900 focus:bg-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  4. 连带受影响工序环节
                </label>
                <input
                  value={affectedModulesText}
                  onChange={e => setAffectedModulesText(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 focus:bg-white focus:outline-none"
                />
              </div>
            </div>
          ) : (
            /* 传统缺陷表单 */
            <div className="space-y-3.5">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">重现步骤说明</label>
                <textarea
                  rows={3}
                  value={steps}
                  onChange={e => setSteps(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg p-2.5 text-xs text-slate-900 focus:bg-white focus:outline-none focus:border-rose-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">预期效果 / 规范要求</label>
                  <input
                    value={expected}
                    onChange={e => setExpected(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 focus:bg-white focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">实际现状 / 矛盾问题</label>
                  <input
                    value={actual}
                    onChange={e => setActual(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 focus:bg-white focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">关联环境 / 平台端</label>
                <input
                  value={osEnv}
                  onChange={e => setOsEnv(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 focus:bg-white focus:outline-none"
                />
              </div>
            </div>
          )}

          <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-3 text-[11px] text-indigo-900 flex items-start gap-2">
            <ArrowLeftRight className="w-4 h-4 shrink-0 mt-0.5 text-indigo-600" />
            <span>
              {category === 'requirement_cr'
                ? '提示：需求变更请求 (CR) 将派发至目标工序（如工序 05 产品需求定义）。目标工序工作台会显示专有采纳卡片，责任人可一键采纳并由 Agent 自动修订 PRD 生成新基线。'
                : '提示：若选择严重阻断级别，目标工序如果已正式定稿，将自动触发回退至研讨状态，以确保问题彻底解决前不会带病推进。'}
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
              className={`px-4 py-2 rounded-lg text-xs font-medium text-white transition disabled:opacity-50 cursor-pointer ${
                category === 'requirement_cr'
                  ? 'bg-indigo-600 hover:bg-indigo-500'
                  : 'bg-rose-600 hover:bg-rose-500'
              }`}
            >
              {isSubmitting
                ? '提交中...'
                : category === 'requirement_cr'
                  ? '发起需求变更单 (CR)'
                  : '确认提交并派发'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
