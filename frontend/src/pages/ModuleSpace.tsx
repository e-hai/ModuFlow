import React, { useEffect, useState, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { api } from '../services/api';
import { ModuleInstance, CollaborationSession, SessionMessage, Artifact, Issue } from '../types';
import { PhaseBadge, SeverityBadge } from '../components/StatusBadge';
import { NewIssueModal } from '../components/NewIssueModal';
import {
  Send,
  Bot,
  User,
  Sparkles,
  FileCheck2,
  Bug,
  ChevronLeft,
  Hash,
  ShieldCheck,
  AlertCircle,
  AlertTriangle,
  Loader2,
  CheckCircle2,
  Clock,
  Terminal,
  TrendingUp,
  BadgeDollarSign,
  Compass,
  Palette,
  Cpu,
  Rocket,
  LineChart,
  Info
} from 'lucide-react';

interface ModuleSpaceProps {
  module: ModuleInstance;
  allModules: ModuleInstance[];
  onBackToWorkflow: () => void;
  onModuleUpdated: () => void;
}

export const ModuleSpace: React.FC<ModuleSpaceProps> = ({
  module,
  allModules,
  onBackToWorkflow,
  onModuleUpdated
}) => {
  const [session, setSession] = useState<CollaborationSession | null>(null);
  const [messages, setMessages] = useState<SessionMessage[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [selectedArtifact, setSelectedArtifact] = useState<Artifact | null>(null);
  const [inputText, setInputText] = useState('');
  const [messageType, setMessageType] = useState<SessionMessage['message_type']>('instruction');
  const [sending, setSending] = useState(false);
  const [isIssueModalOpen, setIsIssueModalOpen] = useState(false);
  const [moduleState, setModuleState] = useState<ModuleInstance>(module);
  const [moduleIssues, setModuleIssues] = useState<Issue[]>([]);
  const [agentCommand, setAgentCommand] = useState<string>('agy');
  const [agentStage, setAgentStage] = useState<'idle' | 'context' | 'spawning' | 'reasoning' | 'completed' | 'error'>('idle');
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);
  const [showPersonaDetail, setShowPersonaDetail] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<any>(null);

  const renderRoleIcon = (iconName?: string, className = "w-4 h-4") => {
    switch (iconName) {
      case 'TrendingUp': return <TrendingUp className={className} />;
      case 'BadgeDollarSign': return <BadgeDollarSign className={className} />;
      case 'Compass': return <Compass className={className} />;
      case 'Palette': return <Palette className={className} />;
      case 'Cpu': return <Cpu className={className} />;
      case 'ShieldCheck': return <ShieldCheck className={className} />;
      case 'Rocket': return <Rocket className={className} />;
      case 'LineChart': return <LineChart className={className} />;
      default: return <Bot className={className} />;
    }
  };

  useEffect(() => {
    loadSessionAndArtifacts();
    api.getAgentSettings().then(s => {
      if (s?.cli_command) setAgentCommand(s.cli_command);
    }).catch(() => {});
  }, [module.id]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, sending, agentStage]);

  const loadSessionAndArtifacts = async () => {
    try {
      const [sess, arts, modData, issues] = await Promise.all([
        api.getModuleSession(module.id),
        api.getModuleArtifacts(module.id),
        api.getModule(module.id),
        api.getIssues({ target_module_id: module.id })
      ]);
      setSession(sess);
      setMessages(sess.messages || []);
      setArtifacts(arts);
      setModuleState(modData);
      setModuleIssues(issues);

      if (arts.length > 0) {
        setSelectedArtifact(arts[0]);
      }
    } catch (e: any) {
      console.error(e);
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim() || !session || sending) return;

    const content = inputText.trim();
    const currentMsgType = messageType;
    setInputText('');

    // 1. Optimistic UI: Immediately show the user's question or instruction in the chat history
    const tempId = `temp-${Date.now()}`;
    const optimisticMsg: SessionMessage = {
      id: tempId,
      session_id: session.id,
      sender: '我 (业务负责人)',
      sender_role: 'human',
      message_type: currentMsgType,
      content,
      created_at: new Date().toISOString()
    };

    setMessages(prev => [...prev, optimisticMsg]);
    setSending(true);
    setAgentStage('context');
    setElapsedSeconds(0);

    const startTime = Date.now();
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startTime) / 1000);
      setElapsedSeconds(elapsed);
      if (elapsed >= 3) {
        setAgentStage('reasoning');
      } else if (elapsed >= 1) {
        setAgentStage('spawning');
      }
    }, 500);

    try {
      const newMsgs = await api.sendMessage(
        session.id,
        {
          sender: '我 (业务负责人)',
          sender_role: 'human',
          message_type: currentMsgType,
          content
        },
        true // trigger Agent response
      );

      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      setAgentStage('completed');

      // Replace optimistic message with actual persisted messages from backend
      setMessages(prev => {
        const filtered = prev.filter(m => m.id !== tempId);
        return [...filtered, ...newMsgs];
      });

      // Reload artifacts and module state
      const [arts, modData] = await Promise.all([
        api.getModuleArtifacts(module.id),
        api.getModule(module.id)
      ]);
      setArtifacts(arts);
      if (arts.length > 0) {
        setSelectedArtifact(arts[0]);
      }
      setModuleState(modData);
      onModuleUpdated();
    } catch (e: any) {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      setAgentStage('error');
      // In case of network / API failure, append error message
      const errorMsg: SessionMessage = {
        id: `err-${Date.now()}`,
        session_id: session.id,
        sender: `AI Agent (${agentCommand})`,
        sender_role: 'agent',
        message_type: 'error',
        content: `Agent 调用执行异常: ${e.message || '网络连接或后端处理失败'}`,
        created_at: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setSending(false);
    }
  };

  const handleBaseline = async () => {
    if (!confirm('确认将当前模块交付物锁定为正式基线 (Baseline) 吗？')) return;
    try {
      const updated = await api.updateModulePhase(module.id, 'baselined');
      setModuleState(updated);
      alert('已成功锁定基线版本！');
      onModuleUpdated();
    } catch (e: any) {
      alert(`基线检查未通过: ${e.message}`);
    }
  };

  const handleCreateIssue = async (issueData: any) => {
    await api.createIssue(issueData);
    alert('跨模块 Issue 已提交并反向流转！');
    await loadSessionAndArtifacts();
    onModuleUpdated();
  };

  const blockingIssues = moduleIssues.filter(
    i => (i.severity === 'critical' || i.severity === 'major') && i.status !== 'closed'
  );
  const openIssues = moduleIssues.filter(i => i.status !== 'closed');

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-5">
      {/* 顶部栏：模块信息与基线操作 */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white border border-slate-200 rounded-2xl p-4 shadow-xs">
        <div className="flex items-center gap-3">
          <button
            onClick={onBackToWorkflow}
            className="p-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-600 transition cursor-pointer"
            title="返回产品工作台"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2.5">
            <span className="font-mono text-xs px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200 font-bold">
              {moduleState.module_code}
            </span>
            <h1 className="text-lg font-bold text-slate-900">{moduleState.name} 协作研讨空间</h1>
            <PhaseBadge phase={moduleState.phase} />
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsIssueModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 transition cursor-pointer"
          >
            <Bug className="w-3.5 h-3.5" />
            提报跨模块缺陷
          </button>

          {moduleState.phase !== 'baselined' ? (
            <button
              onClick={handleBaseline}
              className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-medium bg-emerald-600 hover:bg-emerald-500 text-white shadow-xs transition cursor-pointer"
            >
              <FileCheck2 className="w-4 h-4" />
              锁定基线版本 (Baseline)
            </button>
          ) : (
            <span className="flex items-center gap-1 px-3 py-1 rounded bg-emerald-50 text-emerald-800 border border-emerald-200 text-xs font-medium">
              <ShieldCheck className="w-4 h-4" />
              基线已锁定
            </span>
          )}
        </div>
      </div>

      {/* 虚拟项目工位：驻场 Agent 角色卡片 */}
      <div className="bg-gradient-to-r from-blue-50/70 via-white to-indigo-50/50 border border-slate-200/90 rounded-2xl p-4 shadow-2xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div className="flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-blue-600 text-white flex items-center justify-center font-bold text-sm shadow-xs shrink-0">
              {renderRoleIcon(moduleState.primary_role?.avatar_icon, "w-5 h-5")}
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-bold text-slate-900">
                  {moduleState.primary_role?.name || '驻场主责 Agent'}
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 font-semibold border border-blue-200">
                  主责责任人
                </span>
                <span className="text-xs text-slate-500 font-medium">
                  {moduleState.primary_role?.title}
                </span>
                <button
                  type="button"
                  onClick={() => setShowPersonaDetail(!showPersonaDetail)}
                  className="text-[11px] text-blue-600 hover:text-blue-700 inline-flex items-center gap-1 cursor-pointer transition ml-1"
                >
                  <Info className="w-3.5 h-3.5" />
                  {showPersonaDetail ? '收起专业准则' : '查看履职思维'}
                </button>
              </div>
              <p className="text-xs text-slate-600 mt-1 line-clamp-1 leading-relaxed">
                {moduleState.primary_role?.responsibilities}
              </p>
            </div>
          </div>

          {moduleState.collaborator_roles && moduleState.collaborator_roles.length > 0 && (
            <div className="flex items-center gap-2 shrink-0 border-t md:border-t-0 md:border-l border-slate-200 pt-2 md:pt-0 md:pl-4">
              <span className="text-[11px] text-slate-400 font-medium">参谋协同:</span>
              <div className="flex items-center gap-1.5 flex-wrap">
                {moduleState.collaborator_roles.map(collab => (
                  <span
                    key={collab.id}
                    title={collab.responsibilities}
                    className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-lg bg-white border border-slate-200 text-slate-700 shadow-2xs font-medium cursor-help hover:border-slate-300 transition"
                  >
                    <span className="text-slate-500">{renderRoleIcon(collab.avatar_icon, "w-3.5 h-3.5")}</span>
                    <span>{collab.name.replace(' Agent', '')}</span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* 展开查看该角色的专业作业准则与思维模型 */}
        {showPersonaDetail && moduleState.primary_role?.system_persona && (
          <div className="mt-3 pt-3 border-t border-slate-200/80 text-xs text-slate-700 space-y-2 animate-in fade-in duration-200 bg-white/70 p-3 rounded-xl border">
            <div className="font-semibold text-slate-800 flex items-center gap-1.5 text-xs">
              <Sparkles className="w-3.5 h-3.5 text-amber-500" />
              【{moduleState.primary_role.name}】专业作业守则与思维准则：
            </div>
            <div className="whitespace-pre-wrap leading-relaxed text-slate-600 font-sans text-[11px]">
              {moduleState.primary_role.system_persona}
            </div>
          </div>
        )}
      </div>

      {/* 阻塞性 Issue 警示条 */}
      {blockingIssues.length > 0 && (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-3.5 text-xs text-rose-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>
              <strong>门禁警示：</strong>当前模块存在 {blockingIssues.length} 个未解决的阻断性 Issue（
              {blockingIssues.map(i => i.id).join(', ')}），在彻底修复并验证关闭前，禁止锁定基线。
            </span>
          </div>
        </div>
      )}

      {/* 主界面：左右分栏（左侧人机对话流，右侧产物看板） */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 h-[720px]">
        {/* 左侧：人机多轮协作会话 (6 栏) */}
        <div className="lg:col-span-6 bg-white border border-slate-200 rounded-2xl flex flex-col overflow-hidden shadow-xs">
          <div className="px-4 py-3 border-b border-slate-200 bg-slate-50/60 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-emerald-600" />
              <span className="text-xs font-semibold text-slate-800">人机交互研讨流</span>
              <span className="text-[10px] text-slate-500 font-mono">({messages.length} 轮)</span>
            </div>
            <div className="text-[11px] text-slate-500">
              Agent 负责草拟与执行 · 人类负责质量把关
            </div>
          </div>

          {/* 消息滚动列表 */}
          <div className="flex-1 p-4 overflow-y-auto space-y-4 bg-slate-50/30">
            {messages.length === 0 && !sending ? (
              <div className="text-center py-16 text-slate-400 text-xs">
                <Bot className="w-8 h-8 mx-auto mb-2 text-slate-300" />
                协作室尚未发起讨论。<br />在下方选择【指令 (Instruction)】输入要求，让 Agent 产出初稿。
              </div>
            ) : (
              messages.map(msg => {
                const isAgent = msg.sender_role === 'agent';
                const isSystem = msg.sender_role === 'system';
                const isError = msg.message_type === 'error';

                if (isSystem) {
                  return (
                    <div key={msg.id} className="text-center my-2">
                      <span className="inline-block px-3 py-1 rounded-full text-[11px] bg-slate-100 text-slate-600 border border-slate-200">
                        {msg.content}
                      </span>
                    </div>
                  );
                }

                // Explicit Error message style
                if (isError) {
                  return (
                    <div
                      key={msg.id}
                      className="flex gap-3 bg-rose-50/90 border border-rose-200 p-3.5 rounded-xl shadow-2xs"
                    >
                      <div className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0 bg-rose-100 text-rose-600 border border-rose-300">
                        <AlertTriangle className="w-4 h-4" />
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between mb-1.5">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-bold text-rose-950">{msg.sender}</span>
                            <span className="text-[10px] px-1.5 py-0.5 rounded font-mono bg-rose-100 text-rose-800 border border-rose-300 font-semibold">
                              执行失败 (Error)
                            </span>
                          </div>
                          <span className="text-[10px] text-rose-400 font-mono">
                            {new Date(msg.created_at).toLocaleTimeString()}
                          </span>
                        </div>

                        <div className="text-xs text-rose-900 bg-white/90 p-3 rounded-lg border border-rose-200/90 whitespace-pre-wrap leading-relaxed font-mono">
                          {msg.content}
                        </div>

                        <div className="mt-2 text-[11px] text-rose-600/90 flex items-center gap-1.5">
                          <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                          <span>底层 Agent 进程执行异常已真实报告，绝不伪造正常答复。请检查右上角 Agent 适配设置或底层 CLI 配置。</span>
                        </div>
                      </div>
                    </div>
                  );
                }

                return (
                  <div
                    key={msg.id}
                    className={`flex gap-3 ${isAgent ? 'bg-white shadow-2xs' : 'bg-slate-50/80'} p-3 rounded-xl border border-slate-200`}
                  >
                    <div
                      className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${
                        isAgent ? 'bg-blue-50 text-blue-600 border border-blue-200' : 'bg-slate-100 text-slate-700 border border-slate-200'
                      }`}
                    >
                      {isAgent ? renderRoleIcon(moduleState.primary_role?.avatar_icon, "w-4 h-4") : <User className="w-4 h-4" />}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold text-slate-900">{msg.sender}</span>
                          <span
                            className={`text-[10px] px-1.5 py-0.2 rounded font-mono ${
                              msg.message_type === 'draft_artifact'
                                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                : msg.message_type === 'revised_artifact'
                                ? 'bg-blue-50 text-blue-700 border border-blue-200'
                                : msg.message_type === 'feedback'
                                ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                : msg.message_type === 'question'
                                ? 'bg-cyan-50 text-cyan-700 border border-cyan-200'
                                : msg.message_type === 'answer'
                                ? 'bg-purple-50 text-purple-700 border border-purple-200'
                                : 'bg-slate-100 text-slate-600 border border-slate-200'
                            }`}
                          >
                            {msg.message_type === 'draft_artifact'
                              ? '交付物初稿'
                              : msg.message_type === 'revised_artifact'
                              ? '交付物修订'
                              : msg.message_type === 'feedback'
                              ? '反馈修正'
                              : msg.message_type === 'question'
                              ? '疑问讨论'
                              : msg.message_type === 'answer'
                              ? 'Agent 答复'
                              : msg.message_type}
                          </span>
                        </div>
                        <span className="text-[10px] text-slate-400">
                          {new Date(msg.created_at).toLocaleTimeString()}
                        </span>
                      </div>

                      {msg.message_type === 'answer' ? (
                        <div className="prose prose-xs max-w-none text-xs text-slate-800 leading-relaxed font-sans">
                          <ReactMarkdown>{msg.content}</ReactMarkdown>
                        </div>
                      ) : (
                        <div className="text-xs text-slate-700 whitespace-pre-wrap leading-relaxed">
                          {msg.content}
                        </div>
                      )}

                      {msg.artifact_ref_id && (
                        <div className="mt-2 inline-flex items-center gap-1.5 px-2 py-1 rounded bg-emerald-50 text-[11px] text-emerald-800 border border-emerald-200">
                          <FileCheck2 className="w-3.5 h-3.5 text-emerald-600" />
                          已关联生成右侧交付物版本
                        </div>
                      )}
                    </div>
                  </div>
                );
              })
            )}

            {/* Active Multi-stage Agent Status Card */}
            {sending && (
              <div className="bg-gradient-to-b from-blue-50/70 to-slate-50 border border-blue-200/90 rounded-2xl p-4 shadow-sm space-y-3 animate-in fade-in slide-in-from-bottom-2 duration-300">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="relative flex h-2.5 w-2.5">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-blue-600"></span>
                    </div>
                    <span className="text-xs font-bold text-slate-800">
                      {moduleState.primary_role?.name || 'Agent'} 正在处理任务 ({elapsedSeconds}s)
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Terminal className="w-3.5 h-3.5 text-slate-400" />
                    <span className="text-[11px] font-mono text-slate-600 bg-white px-2 py-0.5 rounded-md border border-slate-200 shadow-2xs font-medium">
                      {agentCommand} CLI
                    </span>
                  </div>
                </div>

                {/* 3-Stage Progress Cards */}
                <div className="grid grid-cols-3 gap-2">
                  {/* Stage 1: Context */}
                  <div className={`p-2.5 rounded-xl border text-xs transition-all ${
                    agentStage === 'context'
                      ? 'bg-blue-100/70 border-blue-400 text-blue-900 shadow-2xs font-medium'
                      : 'bg-white border-slate-200 text-slate-600'
                  }`}>
                    <div className="flex items-center gap-1.5">
                      {agentStage === 'context' ? (
                        <Loader2 className="w-3.5 h-3.5 text-blue-600 animate-spin shrink-0" />
                      ) : (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                      )}
                      <span className="truncate">1. 装配上下文</span>
                    </div>
                    <div className="text-[10px] text-slate-500 mt-1 leading-tight">
                      {agentStage === 'context'
                        ? `注入战略底稿与【${moduleState.primary_role?.name || '主责'}】专业准则...`
                        : '底稿与角色准则已注入'}
                    </div>
                  </div>

                  {/* Stage 2: Process */}
                  <div className={`p-2.5 rounded-xl border text-xs transition-all ${
                    agentStage === 'spawning'
                      ? 'bg-blue-100/70 border-blue-400 text-blue-900 shadow-2xs font-medium'
                      : agentStage === 'reasoning'
                      ? 'bg-white border-slate-200 text-slate-600'
                      : 'bg-slate-50/70 border-slate-200 text-slate-400'
                  }`}>
                    <div className="flex items-center gap-1.5">
                      {agentStage === 'spawning' ? (
                        <Loader2 className="w-3.5 h-3.5 text-blue-600 animate-spin shrink-0" />
                      ) : agentStage === 'reasoning' ? (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                      ) : (
                        <Clock className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                      )}
                      <span className="truncate">2. 唤起 Agent</span>
                    </div>
                    <div className="text-[10px] text-slate-500 mt-1 leading-tight">
                      {agentStage === 'spawning'
                        ? `启动 ${agentCommand} CLI 子进程...`
                        : agentStage === 'reasoning'
                        ? '物理隔离进程已就位'
                        : '等待底稿就绪'}
                    </div>
                  </div>

                  {/* Stage 3: Reasoning / Generating */}
                  <div className={`p-2.5 rounded-xl border text-xs transition-all ${
                    agentStage === 'reasoning'
                      ? 'bg-blue-100/70 border-blue-400 text-blue-900 shadow-2xs font-medium'
                      : 'bg-slate-50/70 border-slate-200 text-slate-400'
                  }`}>
                    <div className="flex items-center gap-1.5">
                      {agentStage === 'reasoning' ? (
                        <Loader2 className="w-3.5 h-3.5 text-blue-600 animate-spin shrink-0" />
                      ) : (
                        <Clock className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                      )}
                      <span className="truncate">3. 推演与生成</span>
                    </div>
                    <div className="text-[10px] text-slate-500 mt-1 leading-tight">
                      {agentStage === 'reasoning'
                        ? `基于【${moduleState.primary_role?.name?.replace(' Agent', '') || '业务'}】专业框架推演输出...`
                        : '等待进程就绪'}
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-between text-[11px] text-slate-500 pt-0.5">
                  <span className="flex items-center gap-1 text-slate-400">
                    <Sparkles className="w-3 h-3 text-amber-500" />
                    物理工作区安全隔离运行中
                  </span>
                  <span className="text-slate-400 font-mono text-[10px]">
                    状态: {agentStage === 'context' ? 'Context Assembly' : agentStage === 'spawning' ? 'Process Spawn' : 'Autonomous Reasoning'}
                  </span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* 输入框与操作条 */}
          <div className="p-3 border-t border-slate-200 bg-white">
            {/* 消息类型快速切换 */}
            <div className="flex items-center gap-1.5 mb-2 text-xs">
              <span className="text-[11px] text-slate-400">动作类型:</span>
              <button
                type="button"
                onClick={() => setMessageType('instruction')}
                className={`px-2 py-0.5 rounded text-[11px] transition cursor-pointer ${
                  messageType === 'instruction'
                    ? 'bg-emerald-600 text-white font-medium'
                    : 'bg-slate-100 text-slate-600 hover:text-slate-900'
                }`}
              >
                指令 (Instruction)
              </button>
              <button
                type="button"
                onClick={() => setMessageType('feedback')}
                className={`px-2 py-0.5 rounded text-[11px] transition cursor-pointer ${
                  messageType === 'feedback'
                    ? 'bg-amber-600 text-white font-medium'
                    : 'bg-slate-100 text-slate-600 hover:text-slate-900'
                }`}
              >
                反馈修正 (Feedback)
              </button>
              <button
                type="button"
                onClick={() => setMessageType('question')}
                className={`px-2 py-0.5 rounded text-[11px] transition cursor-pointer ${
                  messageType === 'question'
                    ? 'bg-blue-600 text-white font-medium'
                    : 'bg-slate-100 text-slate-600 hover:text-slate-900'
                }`}
              >
                疑问讨论 (Question)
              </button>
            </div>

            <form onSubmit={handleSendMessage} className="flex gap-2">
              <input
                type="text"
                placeholder={
                  messageType === 'instruction'
                    ? '输入指令，让 Agent 产出交付物初稿...'
                    : messageType === 'feedback'
                    ? '提出针对交付物的补充与质疑意见...'
                    : '输入讨论内容...'
                }
                value={inputText}
                onChange={e => setInputText(e.target.value)}
                className="flex-1 bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 placeholder-slate-400 focus:bg-white focus:outline-none focus:border-emerald-500"
              />
              <button
                type="submit"
                disabled={sending || !inputText.trim()}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg text-xs font-medium transition flex items-center gap-1 cursor-pointer"
              >
                <Send className="w-3.5 h-3.5" />
                {sending ? '处理中...' : '发送'}
              </button>
            </form>
          </div>
        </div>

        {/* 右侧：产物看板与版本树 (6 栏) */}
        <div className="lg:col-span-6 bg-white border border-slate-200 rounded-2xl flex flex-col overflow-hidden shadow-xs">
          <div className="px-4 py-3 border-b border-slate-200 bg-slate-50/60 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileCheck2 className="w-4 h-4 text-emerald-600" />
              <span className="text-xs font-semibold text-slate-800">交付物产物库 (Artifacts)</span>
            </div>

            {/* 版本切换下拉 */}
            {artifacts.length > 0 && (
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-slate-500">历史版本:</span>
                <select
                  value={selectedArtifact?.id}
                  onChange={e => {
                    const found = artifacts.find(a => a.id === e.target.value);
                    if (found) setSelectedArtifact(found);
                  }}
                  className="bg-slate-50 border border-slate-200 rounded px-2 py-0.5 text-xs text-emerald-800 font-mono font-medium"
                >
                  {artifacts.map(a => (
                    <option key={a.id} value={a.id}>
                      v{a.version} {a.is_baseline ? '(基线)' : ''} - {new Date(a.created_at).toLocaleTimeString()}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {/* 产物内容实时渲染 */}
          <div className="flex-1 p-5 overflow-y-auto bg-white">
            {selectedArtifact ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                  <div>
                    <h2 className="text-base font-bold text-slate-900">{selectedArtifact.title}</h2>
                    <div className="flex items-center gap-2 text-[10px] text-slate-400 font-mono mt-1">
                      <Hash className="w-3 h-3" />
                      SHA-256: {selectedArtifact.content_hash.slice(0, 16)}...
                    </div>
                  </div>
                  {selectedArtifact.is_baseline && (
                    <span className="px-2 py-0.5 rounded text-[11px] bg-emerald-50 text-emerald-800 border border-emerald-200 font-medium flex items-center gap-1">
                      <ShieldCheck className="w-3.5 h-3.5" />
                      当前基线
                    </span>
                  )}
                </div>

                <div className="prose prose-slate prose-sm max-w-none text-slate-700 leading-relaxed">
                  <ReactMarkdown>{selectedArtifact.content}</ReactMarkdown>
                </div>
              </div>
            ) : (
              <div className="text-center py-24 text-slate-400 text-xs">
                尚无生成产物。<br />在左侧输入指令后，Agent 自动在此生成交付物。
              </div>
            )}
          </div>

          {/* 底部关联的 Issue 状态预览 */}
          <div className="px-4 py-2.5 border-t border-slate-200 bg-slate-50/60 flex items-center justify-between text-xs text-slate-500">
            <span className="flex items-center gap-1.5">
              <Bug className="w-3.5 h-3.5 text-rose-600" />
              关联 Issue: {openIssues.length} 个未关闭
            </span>
            <span className="text-[11px] text-slate-400">不可变快照隔离存储</span>
          </div>
        </div>
      </div>

      {/* 提报 Issue 弹窗 */}
      <NewIssueModal
        isOpen={isIssueModalOpen}
        currentModule={moduleState}
        allModules={allModules}
        onClose={() => setIsIssueModalOpen(false)}
        onSubmit={handleCreateIssue}
      />
    </div>
  );
};
