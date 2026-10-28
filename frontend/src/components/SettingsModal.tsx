import React, { useState, useEffect, useRef } from 'react';
import {
  X,
  Layers,
  Info,
  Cpu,
  ShieldCheck,
  CheckCircle2,
  Terminal,
  Bot,
  Check,
  AlertCircle,
  AlertTriangle,
  RefreshCw,
  Zap,
  FolderGit2,
  Copy
} from 'lucide-react';
import { api } from '../services/api';
import { AgentSettings, CliModelItem } from '../types';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSettingsChanged?: (settings: AgentSettings) => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose, onSettingsChanged }) => {
  const [activeTab, setActiveTab] = useState<'agent' | 'platform'>('agent');
  const [loading, setLoading] = useState<boolean>(false);
  const [saving, setSaving] = useState<boolean>(false);
  const [testing, setTesting] = useState<boolean>(false);
  const [saveSuccess, setSaveSuccess] = useState<boolean>(false);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [copiedCommand, setCopiedCommand] = useState<string | null>(null);

  const [agentSettings, setAgentSettings] = useState<AgentSettings | null>(null);
  const [selectedCommand, setSelectedCommand] = useState<string>('agy');
  const [customCommand, setCustomCommand] = useState<string>('');
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [cliModels, setCliModels] = useState<CliModelItem[]>([]);
  const [modelsLoading, setModelsLoading] = useState<boolean>(false);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const [modelNonce, setModelNonce] = useState<number>(0);
  const refreshModels = useRef(false);
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
      onSettingsChanged?.(data);
      setSelectedCommand(data.cli_command);
      setSelectedModel(data.cli_model || '');
      setTimeoutSeconds(data.timeout);
      if (!['claude', 'agy', 'codex'].includes(data.cli_command)) {
        setCustomCommand(data.cli_command);
        setSelectedCommand('custom');
      }
    } catch (e) {
      console.error('Failed to load agent settings', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!isOpen) return;
    const command = selectedCommand === 'custom' ? customCommand.trim() : selectedCommand;
    if (!command) {
      setCliModels([]);
      setModelsError(null);
      return;
    }
    if (selectedCommand !== 'custom') {
      const preset = agentSettings?.available_presets.find((item) => item.command === command);
      if (preset && !preset.installed) {
        setCliModels([]);
        setModelsError(null);
        return;
      }
    }
    let cancelled = false;
    setCliModels([]);
    setModelsError(null);
    setModelsLoading(true);
    const timer = window.setTimeout(async () => {
      const refresh = refreshModels.current;
      refreshModels.current = false;
      try {
        const listed = await api.listCliModels(command, refresh);
        if (cancelled) return;
        setCliModels(listed.models || []);
        setModelsError(listed.error || null);
      } catch (e: any) {
        if (!cancelled) {
          setCliModels([]);
          setModelsError(e?.message || '读取模型列表失败');
        }
      } finally {
        if (!cancelled) setModelsLoading(false);
      }
    }, selectedCommand === 'custom' ? 400 : 0);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [isOpen, selectedCommand, customCommand, agentSettings, modelNonce]);

  const chooseCommand = (command: string) => {
    if (command !== selectedCommand) {
      setSelectedModel('');
    }
    setSelectedCommand(command);
  };

  const renderModelPicker = () => (
    <div
      className="mt-2.5 pt-2.5 border-t border-slate-200/70 space-y-1.5"
      onClick={(event) => event.stopPropagation()}
    >
      <div className="flex items-center justify-between">
        <span className="font-semibold text-slate-700">模型</span>
        <button
          type="button"
          onClick={() => {
            refreshModels.current = true;
            setModelNonce((value) => value + 1);
          }}
          className="text-[10px] font-medium text-emerald-700 hover:text-emerald-800"
        >
          重新读取
        </button>
      </div>
      <select
        value={selectedModel}
        onChange={(event) => setSelectedModel(event.target.value)}
        disabled={modelsLoading && cliModels.length === 0}
        className="w-full bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
      >
        <option value="">使用该 CLI 当前默认模型</option>
        {selectedModel && !cliModels.some((item) => item.id === selectedModel) && (
          <option value={selectedModel}>{selectedModel}</option>
        )}
        {cliModels.map((item) => (
          <option key={item.id} value={item.id}>
            {item.label} · {item.id}
          </option>
        ))}
      </select>
      {modelsLoading && (
        <p className="text-[10px] text-slate-400">正在读取该 CLI 支持的模型…</p>
      )}
      {modelsError && (
        <p className="text-[10px] text-amber-700">{modelsError}</p>
      )}
      {!modelsError && (
        <p className="text-[10px] text-slate-400">保存后，后续工序会用这里选中的模型调用该 CLI。</p>
      )}
    </div>
  );

  const handleSave = async () => {
    setSaving(true);
    setSaveSuccess(false);
    try {
      const commandToSave = selectedCommand === 'custom' ? (customCommand || 'agy') : selectedCommand;
      const updated = await api.updateAgentSettings({
        adapter_type: 'cli',
        cli_command: commandToSave,
        cli_model: selectedModel,
        timeout: timeoutSeconds,
      });
      setAgentSettings(updated);
      onSettingsChanged?.(updated);
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
      const commandToSave = selectedCommand === 'custom' ? (customCommand || 'agy') : selectedCommand;
      await api.updateAgentSettings({
        adapter_type: 'cli',
        cli_command: commandToSave,
        cli_model: selectedModel,
        timeout: timeoutSeconds,
      });

      const res = await api.testAgentSettings();
      if (res.success) {
        if (res.installed === false) {
          setTestResult(`⚠️ 命令未就绪：系统 PATH 中未找到 [${res.cli_command}]。请参考上方指引安装，或检查自定义路径。`);
        } else {
          setTestResult(`✓ 探测成功：适配器 (${res.adapter_type}) / 命令 [${res.cli_command}] 调度正常，已就绪`);
        }
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
              {/* 未检测到安装时的置顶提醒与引导 */}
              {agentSettings && (!agentSettings.is_current_installed || !agentSettings.any_installed) && (
                <div className="p-3.5 bg-amber-50/90 border border-amber-200/90 rounded-xl space-y-2 animate-in fade-in duration-150">
                  <div className="flex items-center gap-2 text-amber-800 font-bold text-xs">
                    <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                    <span>
                      {!agentSettings.any_installed
                        ? '电脑未检测到已安装的 Agent CLI 命令行工具'
                        : `当前选择的命令行工具 [${selectedCommand}] 尚未安装或未加入 PATH`}
                    </span>
                  </div>
                  <p className="text-[11px] text-amber-700 leading-relaxed">
                    ModuFlow 采用物理工作区调度真实的 Agent CLI 驱动工序推演与交付物输出。请从下方推荐的 Agent CLI 中任选一款一键复制命令安装，或通过「自定义命令行」指定本机已有的可执行脚本。
                  </p>
                </div>
              )}

              {/* 底层 AI 引擎工具预设 */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wider block font-mono">
                    智能体底层执行引擎 (AI Engine)
                  </label>
                  <button
                    type="button"
                    onClick={loadSettings}
                    disabled={loading}
                    className="flex items-center gap-1 text-[11px] font-semibold text-emerald-700 hover:text-emerald-800 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200/80 px-2 py-0.5 rounded-md transition cursor-pointer disabled:opacity-50"
                  >
                    <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
                    <span>{loading ? '探测中...' : '重新探测本机环境'}</span>
                  </button>
                </div>

                <div className="space-y-2">
                  {agentSettings?.available_presets
                    .filter((p) => p.id !== 'simulator')
                    .map((preset) => {
                      const isSelected = selectedCommand === preset.command;
                      return (
                        <div
                          key={preset.id}
                          onClick={() => chooseCommand(preset.command)}
                          className={`p-3 rounded-xl border flex flex-col justify-between transition cursor-pointer ${
                            isSelected
                              ? 'border-emerald-600 bg-emerald-50/40 ring-1 ring-emerald-500/20'
                              : 'border-slate-200 bg-white hover:bg-slate-50'
                          }`}
                        >
                          <div className="flex items-start justify-between">
                            <div className="space-y-1 pr-2">
                              <div className="flex items-center gap-2">
                                <span className="font-bold text-slate-900 text-xs">{preset.name}</span>
                                <code className="text-[10px] font-mono bg-slate-100 text-slate-700 px-1.5 py-0.5 rounded border border-slate-200">
                                  {preset.command}
                                </code>
                                {preset.installed ? (
                                  <span className="inline-flex items-center gap-1 text-[10px] font-medium text-emerald-700 bg-emerald-100/70 border border-emerald-200/60 px-1.5 py-0.2 rounded-full">
                                    <Check className="w-3 h-3 text-emerald-600" />
                                    已检测到安装
                                  </span>
                                ) : (
                                  <span className="inline-flex items-center gap-1 text-[10px] font-medium text-amber-700 bg-amber-50 border border-amber-200/80 px-1.5 py-0.2 rounded-full">
                                    <AlertCircle className="w-3 h-3 text-amber-600" />
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
                              onChange={() => chooseCommand(preset.command)}
                              className="mt-1 text-emerald-600 cursor-pointer shrink-0"
                            />
                          </div>

                          {/* 若未安装，且当前卡片被选中或系统缺少该工具，展示一键复制安装引导 */}
                          {!preset.installed && (
                            <div className="mt-2.5 pt-2 border-t border-slate-200/60 space-y-1.5 bg-slate-50/80 p-2.5 rounded-lg">
                              <div className="flex items-center justify-between text-[11px]">
                                <span className="font-semibold text-slate-700">推荐一键安装命令：</span>
                                {preset.install_command && (
                                  <button
                                    type="button"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      navigator.clipboard.writeText(preset.install_command!);
                                      setCopiedCommand(preset.id);
                                      setTimeout(() => setCopiedCommand(null), 2000);
                                    }}
                                    className="flex items-center gap-1 text-[10px] text-emerald-700 hover:text-emerald-800 font-medium px-2 py-0.5 bg-white border border-slate-200 hover:border-emerald-300 rounded transition cursor-pointer shadow-2xs"
                                  >
                                    {copiedCommand === preset.id ? (
                                      <>
                                        <Check className="w-3 h-3 text-emerald-600" />
                                        <span>已复制命令</span>
                                      </>
                                    ) : (
                                      <>
                                        <Copy className="w-3 h-3 text-slate-500" />
                                        <span>复制命令</span>
                                      </>
                                    )}
                                  </button>
                                )}
                              </div>
                              {preset.install_command && (
                                <div className="font-mono text-[11px] bg-slate-900 text-slate-100 px-2.5 py-1.5 rounded select-all break-all">
                                  {preset.install_command}
                                </div>
                              )}
                              {preset.install_guide && (
                                <p className="text-[10px] text-slate-500">
                                  💡 {preset.install_guide}
                                </p>
                              )}
                            </div>
                          )}
                          {isSelected && preset.installed && renderModelPicker()}
                        </div>
                      );
                    })}

                  {/* 自定义命令行选项 */}
                  <div
                    onClick={() => chooseCommand('custom')}
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
                        onChange={() => chooseCommand('custom')}
                        className="text-emerald-600 cursor-pointer"
                      />
                    </div>
                    {selectedCommand === 'custom' && (
                      <div className="pt-1 space-y-1">
                        <input
                          type="text"
                          placeholder="例如: /usr/local/bin/my-agent-cli 或 python3 -m runner"
                          value={customCommand}
                          onChange={(e) => setCustomCommand(e.target.value)}
                          className="w-full px-3 py-1.5 text-xs font-mono bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                        />
                        <p className="text-[10px] text-slate-400">
                          支持填写绝对路径或系统 PATH 中的可执行文件名。保存后可点击下方「连通性测试」验证。
                        </p>
                      </div>
                    )}
                    {selectedCommand === 'custom' && customCommand.trim() && renderModelPicker()}
                  </div>
                </div>
              </div>

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
