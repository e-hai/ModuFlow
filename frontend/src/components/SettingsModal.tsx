import React, { useState, useEffect } from 'react';
import {
  X,
  Layers,
  Info,
  Cpu,
  ShieldCheck,
  CheckCircle2,
  Terminal,
  Bot,
  Sliders,
  Check,
  AlertCircle,
  RefreshCw,
  Zap,
  FolderGit2
} from 'lucide-react';
import { api } from '../services/api';
import { AgentSettings } from '../types';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState<'agent' | 'platform'>('agent');
  const [loading, setLoading] = useState<boolean>(false);
  const [saving, setSaving] = useState<boolean>(false);
  const [testing, setTesting] = useState<boolean>(false);
  const [saveSuccess, setSaveSuccess] = useState<boolean>(false);
  const [testResult, setTestResult] = useState<string | null>(null);

  const [agentSettings, setAgentSettings] = useState<AgentSettings | null>(null);
  const [selectedAdapter, setSelectedAdapter] = useState<'cli' | 'simulator'>('cli');
  const [selectedCommand, setSelectedCommand] = useState<string>('claude');
  const [customCommand, setCustomCommand] = useState<string>('');
  const [timeoutSeconds, setTimeoutSeconds] = useState<number>(120);

  useEffect(() => {
    if (isOpen) {
      loadSettings();
    }
  }, [isOpen]);

  const loadSettings = async () => {
    setLoading(true);
    try {
      const data = await api.getAgentSettings();
      setAgentSettings(data);
      setSelectedAdapter(data.adapter_type);
      setSelectedCommand(data.cli_command);
      setTimeoutSeconds(data.timeout);
      if (!['claude', 'agy', 'codex', 'simulator'].includes(data.cli_command)) {
        setCustomCommand(data.cli_command);
        setSelectedCommand('custom');
      }
    } catch (e) {
      console.error('Failed to load agent settings', e);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveSuccess(false);
    try {
      const commandToSave = selectedCommand === 'custom' ? (customCommand || 'claude') : selectedCommand;
      const updated = await api.updateAgentSettings({
        adapter_type: selectedAdapter,
        cli_command: commandToSave,
        timeout: timeoutSeconds,
      });
      setAgentSettings(updated);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (e) {
      console.error('Failed to save agent settings', e);
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      // First save current selection so test runs against current settings
      const commandToSave = selectedCommand === 'custom' ? (customCommand || 'claude') : selectedCommand;
      await api.updateAgentSettings({
        adapter_type: selectedAdapter,
        cli_command: commandToSave,
        timeout: timeoutSeconds,
      });

      const res = await api.testAgentSettings();
      if (res.success) {
        setTestResult(`✓ 探测成功：适配器 (${res.adapter_type}) / 命令 [${res.cli_command}] 调度正常，已捕获 ${res.events_count} 条事件流`);
      } else {
        setTestResult('⚠️ 探测未返回成功状态');
      }
    } catch (e: any) {
      setTestResult(`❌ 连通测试失败: ${e.message || '未知错误'}`);
    } finally {
      setTesting(false);
      setTimeout(() => setTestResult(null), 5000);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white border border-slate-200 w-full max-w-2xl rounded-2xl p-6 shadow-2xl space-y-5 animate-in fade-in zoom-in-95 duration-150 flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-200 pb-3 shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-600">
              <Bot className="w-5 h-5 text-emerald-600" />
            </div>
            <div>
              <h3 className="font-bold text-slate-900 text-base tracking-tight flex items-center gap-2">
                ModuFlow 系统与智能体配置
                <span className="text-[10px] bg-emerald-50 text-emerald-700 font-mono px-2 py-0.5 rounded-full border border-emerald-200">
                  v0.1.0-alpha
                </span>
              </h3>
              <p className="text-xs text-slate-500">管理 AI 智能体适配器、项目工作区与平台规格</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-700 p-1.5 rounded-lg hover:bg-slate-100 transition cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Switcher */}
        <div className="flex items-center space-x-2 border-b border-slate-200 pb-2 shrink-0">
          <button
            onClick={() => setActiveTab('agent')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
              activeTab === 'agent'
                ? 'bg-slate-900 text-white shadow-xs'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <Bot className="w-3.5 h-3.5" />
            <span>智能体引擎配置 (AI 引擎)</span>
          </button>
          <button
            onClick={() => setActiveTab('platform')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
              activeTab === 'platform'
                ? 'bg-slate-900 text-white shadow-xs'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <Info className="w-3.5 h-3.5" />
            <span>平台概况与设计原则</span>
          </button>
        </div>

        {/* Content Body */}
        <div className="space-y-4 overflow-y-auto pr-1 flex-1 text-xs">
          {activeTab === 'agent' && (
            <div className="space-y-4">
              {/* 1. 运行模式选择 */}
              <div className="space-y-2">
                <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wider block font-mono">
                  ① 智能体运行适配模式 (Runtime Adapter)
                </label>
                <div className="grid grid-cols-2 gap-2.5">
                  <div
                    onClick={() => setSelectedAdapter('cli')}
                    className={`p-3 rounded-xl border transition cursor-pointer ${
                      selectedAdapter === 'cli'
                        ? 'border-emerald-600 bg-emerald-50/60 ring-2 ring-emerald-500/20'
                        : 'border-slate-200 bg-white hover:bg-slate-50'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-bold text-slate-900 flex items-center gap-1.5">
                        <Terminal className="w-4 h-4 text-emerald-600" />
                        命令行工具适配器 (CLI)
                      </span>
                      {selectedAdapter === 'cli' && <Check className="w-4 h-4 text-emerald-600" />}
                    </div>
                    <p className="text-[11px] text-slate-500 leading-normal">
                      连接至各单品项目工作区目录执行，支持真实工程文件读写与终端能力。（推荐）
                    </p>
                  </div>

                  <div
                    onClick={() => setSelectedAdapter('simulator')}
                    className={`p-3 rounded-xl border transition cursor-pointer ${
                      selectedAdapter === 'simulator'
                        ? 'border-emerald-600 bg-emerald-50/60 ring-2 ring-emerald-500/20'
                        : 'border-slate-200 bg-white hover:bg-slate-50'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-bold text-slate-900 flex items-center gap-1.5">
                        <Sliders className="w-4 h-4 text-slate-600" />
                        内置高保真沙箱
                      </span>
                      {selectedAdapter === 'simulator' && <Check className="w-4 h-4 text-emerald-600" />}
                    </div>
                    <p className="text-[11px] text-slate-500 leading-normal">
                      无需外部 CLI 安装或任何 API Key，供快速演示、离线演练与回归测试。
                    </p>
                  </div>
                </div>
              </div>

              {/* 2. 底层 CLI 预设选择 */}
              {selectedAdapter === 'cli' && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wider block font-mono">
                      ② 底层 AI 引擎工具预设
                    </label>
                    <span className="text-[11px] text-slate-400">已自动探测本机 PATH 环境</span>
                  </div>

                  <div className="space-y-2">
                    {agentSettings?.available_presets
                      .filter((p) => p.id !== 'simulator')
                      .map((preset) => {
                        const isSelected = selectedCommand === preset.command;
                        return (
                          <div
                            key={preset.id}
                            onClick={() => setSelectedCommand(preset.command)}
                            className={`p-3 rounded-xl border flex items-start justify-between transition cursor-pointer ${
                              isSelected
                                ? 'border-emerald-600 bg-emerald-50/50 ring-1 ring-emerald-500/20'
                                : 'border-slate-200 bg-white hover:bg-slate-50'
                            }`}
                          >
                            <div className="space-y-1 pr-2">
                              <div className="flex items-center gap-2">
                                <span className="font-bold text-slate-900 text-xs">{preset.name}</span>
                                <code className="text-[10px] font-mono bg-slate-100 text-slate-700 px-1.5 py-0.5 rounded border border-slate-200">
                                  {preset.command}
                                </code>
                                {preset.installed ? (
                                  <span className="inline-flex items-center gap-1 text-[10px] font-medium text-emerald-700 bg-emerald-100/70 px-1.5 py-0.2 rounded-full">
                                    <Check className="w-3 h-3 text-emerald-600" />
                                    已检测到安装
                                  </span>
                                ) : (
                                  <span className="inline-flex items-center text-[10px] font-medium text-slate-400 bg-slate-100 px-1.5 py-0.2 rounded-full">
                                    未在 PATH 中
                                  </span>
                                )}
                              </div>
                              <p className="text-[11px] text-slate-500 leading-normal">{preset.description}</p>
                              {preset.path && (
                                <p className="text-[10px] font-mono text-slate-400 truncate max-w-md">
                                  路径: {preset.path}
                                </p>
                              )}
                            </div>
                            <input
                              type="radio"
                              name="cli_preset"
                              checked={isSelected}
                              onChange={() => setSelectedCommand(preset.command)}
                              className="mt-1 text-emerald-600 cursor-pointer"
                            />
                          </div>
                        );
                      })}

                    {/* 自定义命令行选项 */}
                    <div
                      onClick={() => setSelectedCommand('custom')}
                      className={`p-3 rounded-xl border transition cursor-pointer space-y-2 ${
                        selectedCommand === 'custom'
                          ? 'border-emerald-600 bg-emerald-50/50 ring-1 ring-emerald-500/20'
                          : 'border-slate-200 bg-white hover:bg-slate-50'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-slate-900 text-xs">自定义命令行 (Custom Command)</span>
                          <span className="text-[10px] text-slate-400">支持接入团队自研 Agent 或可执行脚本</span>
                        </div>
                        <input
                          type="radio"
                          name="cli_preset"
                          checked={selectedCommand === 'custom'}
                          onChange={() => setSelectedCommand('custom')}
                          className="text-emerald-600 cursor-pointer"
                        />
                      </div>
                      {selectedCommand === 'custom' && (
                        <div className="pt-1">
                          <input
                            type="text"
                            placeholder="例如: /usr/local/bin/my-agent-cli 或 python3 -m runner"
                            value={customCommand}
                            onChange={(e) => setCustomCommand(e.target.value)}
                            className="w-full px-3 py-1.5 text-xs font-mono bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                          />
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* 3. 超时保护配置 */}
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 flex items-center justify-between">
                <div>
                  <span className="font-semibold text-slate-800 text-xs block">单次工序执行超时保护 (Timeout)</span>
                  <span className="text-[11px] text-slate-500">超时后系统将自动停止该任务并安全处理，防止长时间等待</span>
                </div>
                <select
                  value={timeoutSeconds}
                  onChange={(e) => setTimeoutSeconds(Number(e.target.value))}
                  className="bg-white border border-slate-300 rounded-lg px-2.5 py-1 text-xs font-mono text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                >
                  <option value={60}>60 秒 (快速问答)</option>
                  <option value={120}>120 秒 (常规分析)</option>
                  <option value={180}>180 秒 (推荐: AI 深度调研与推演)</option>
                  <option value={300}>300 秒 (推荐: agy 成果全量生成)</option>
                  <option value={600}>600 秒 (全量单测与复杂构建)</option>
                </select>
              </div>

              {/* 探测结果提示 */}
              {testResult && (
                <div className="p-2.5 rounded-lg bg-slate-900 text-slate-100 font-mono text-[11px] animate-in fade-in duration-150">
                  {testResult}
                </div>
              )}
            </div>
          )}

          {activeTab === 'platform' && (
            <div className="space-y-4">
              {/* 1. 应用介绍 */}
              <div className="bg-slate-50 rounded-xl p-4 border border-slate-200 space-y-2">
                <div className="flex items-center gap-1.5 font-semibold text-slate-800 text-xs">
                  <Info className="w-4 h-4 text-emerald-600" />
                  应用简介与定位
                </div>
                <p className="text-slate-600">
                  ModuFlow 专为多产品矩阵体系设计，以顶层<strong className="text-emerald-700 font-medium">“战略工程 (Strategic Initiative)”</strong>为牵引，将宏观业务目标下沉为矩阵子产品的端到端研发流水线。
                </p>
                <p className="text-slate-600">
                  平台覆盖从市场机会识别、PRD、交互设计、架构、开发、QA 测试到灰度发布与运营复盘等 <strong className="text-slate-900 font-medium">13 个产研生命周期工序</strong>，通过多轮人机协同会话、成果交付物正式定稿基准（Baseline Gate）与协同问题反向穿透，保障全矩阵交付质量。
                </p>
              </div>

              {/* 2. 界面设计原则 */}
              <div className="bg-slate-50 rounded-xl p-4 border border-slate-200 space-y-2">
                <div className="flex items-center gap-1.5 font-semibold text-slate-800 text-xs">
                  <ShieldCheck className="w-4 h-4 text-emerald-600" />
                  设计原则：极简低干扰
                </div>
                <ul className="space-y-1.5 text-slate-600">
                  <li className="flex items-start gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />
                    <span><strong>无事不打扰</strong>：主界面与侧边栏剔除冗余修饰，收敛信息密度，仅呈现当前战略决策与产品产研任务。</span>
                  </li>
                  <li className="flex items-start gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />
                    <span><strong>战略与执行解耦</strong>：战略驾驶舱只关注战略大盘与多产品协同拓扑；具体迭代执行全部收敛于各产品的工作台中。</span>
                  </li>
                </ul>
              </div>

              {/* 3. 系统技术规格 */}
              <div className="bg-slate-50 rounded-xl p-4 border border-slate-200 space-y-2">
                <div className="flex items-center gap-1.5 font-semibold text-slate-800 text-xs">
                  <Cpu className="w-4 h-4 text-emerald-600" />
                  技术栈与系统规格
                </div>
                <div className="grid grid-cols-2 gap-2 pt-1 font-mono text-[11px]">
                  <div className="bg-white p-2.5 rounded-lg border border-slate-200 shadow-2xs">
                    <span className="text-slate-400 block text-[10px] uppercase">Backend</span>
                    <span className="text-slate-800 font-medium">Python 3.10 + FastAPI</span>
                    <p className="text-slate-500 text-[10px] mt-0.5">SQLAlchemy 2.0 Async + SQLite</p>
                  </div>
                  <div className="bg-white p-2.5 rounded-lg border border-slate-200 shadow-2xs">
                    <span className="text-slate-400 block text-[10px] uppercase">Frontend</span>
                    <span className="text-slate-800 font-medium">React 18 + Vite + TS</span>
                    <p className="text-slate-500 text-[10px] mt-0.5">Tailwind CSS + Lucide Icons</p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-slate-200 pt-3.5 text-xs text-slate-500 shrink-0">
          <div className="flex items-center gap-2">
            {activeTab === 'agent' && (
              <button
                onClick={handleTest}
                disabled={testing}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 transition cursor-pointer disabled:opacity-50"
              >
                {testing ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5 text-amber-500" />}
                <span>{testing ? '探测中...' : '测试连通性'}</span>
              </button>
            )}
            {saveSuccess && (
              <span className="text-xs text-emerald-700 font-medium flex items-center gap-1">
                <Check className="w-3.5 h-3.5 text-emerald-600" />
                配置已保存并生效
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            {activeTab === 'agent' && (
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white transition cursor-pointer disabled:opacity-50 shadow-xs"
              >
                {saving ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                <span>{saving ? '保存中...' : '保存配置'}</span>
              </button>
            )}
            <button
              onClick={onClose}
              className="px-4 py-1.5 rounded-lg text-xs font-medium bg-slate-900 hover:bg-slate-800 text-white transition cursor-pointer"
            >
              完成
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
