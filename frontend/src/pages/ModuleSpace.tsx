import React, { useEffect, useState, useRef } from 'react';
import { api } from '../services/api';
import { ModuleInstance, CollaborationSession, SessionMessage, Artifact, Issue, ChangeReview, StaleDetail } from '../types';
import { PhaseBadge, SeverityBadge } from '../components/StatusBadge';
import { NewIssueModal } from '../components/NewIssueModal';
import { MarkdownViewer } from '../components/MarkdownViewer';
import {
  Send,
  Bot,
  User,
  Sparkles,
  FileCheck2,
  Bug,
  ChevronLeft,
  ChevronDown,
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
  Info,
  UploadCloud,
  ExternalLink,
  Monitor,
  Smartphone,
  Tablet,
  FileDiff,
  CheckCheck,
  X,
  Eye,
  ThumbsUp,
  ThumbsDown,
  Copy,
  Check,
  Download,
  FileText,
  Maximize2,
  Minimize2
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

  // Architecture Optimization & Unified Approvals state
  const [changeReviews, setChangeReviews] = useState<ChangeReview[]>([]);
  const [selectedReview, setSelectedReview] = useState<ChangeReview | null>(null);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [isStaleDiffModalOpen, setIsStaleDiffModalOpen] = useState(false);
  const [selectedStaleDetail, setSelectedStaleDetail] = useState<StaleDetail | null>(null);
  const [prototypeViewport, setPrototypeViewport] = useState<'desktop' | 'tablet' | 'mobile'>('desktop');
  const [artifactViewMode, setArtifactViewMode] = useState<'preview' | 'content'>('preview');
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadSummary, setUploadSummary] = useState('');
  const [uploading, setUploading] = useState(false);
  const [ackingUpstream, setAckingUpstream] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [showSkillMenu, setShowSkillMenu] = useState(false);
  const [copiedArtifact, setCopiedArtifact] = useState(false);
  const [panelLayout, setPanelLayout] = useState<'equal' | 'wide' | 'full'>('equal');

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<any>(null);
  const skillMenuRef = useRef<HTMLDivElement>(null);

  const handleCopyArtifact = () => {
    if (!selectedArtifact) return;
    navigator.clipboard.writeText(selectedArtifact.content);
    setCopiedArtifact(true);
    setTimeout(() => setCopiedArtifact(false), 2000);
  };

  const handleDownloadArtifact = () => {
    if (!selectedArtifact) return;
    const blob = new Blob([selectedArtifact.content], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `交付物_${moduleState.module_code}_${moduleState.name}_v${selectedArtifact.version}.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (skillMenuRef.current && !skillMenuRef.current.contains(event.target as Node)) {
        setShowSkillMenu(false);
      }
    };
    if (showSkillMenu) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showSkillMenu]);

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
      const [sess, arts, modData, issues, reviews] = await Promise.all([
        api.getModuleSession(module.id),
        api.getModuleArtifacts(module.id),
        api.getModule(module.id),
        api.getIssues({ target_module_id: module.id }),
        api.getChangeReviews({ module_id: module.id })
      ]);
      setSession(sess);
      setMessages(sess.messages || []);
      setArtifacts(arts);
      setModuleState(modData);
      setModuleIssues(issues);
      setChangeReviews(reviews);

      if (arts.length > 0) {
        setSelectedArtifact(arts[0]);
        if (arts[0].artifact_type === 'html_bundle') {
          setArtifactViewMode('preview');
        } else {
          setArtifactViewMode('content');
        }
      }
    } catch (e: any) {
      console.error(e);
    }
  };

  const handleUploadBundle = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile) return;
    try {
      setUploading(true);
      const res = await api.uploadModuleArtifact(module.id, uploadFile, uploadSummary);
      setUploadFile(null);
      setUploadSummary('');
      setIsUploadModalOpen(false);
      alert(`交付物已上传成功！版本 v${res.artifact.version} 已进入统一审批流程。`);
      await loadSessionAndArtifacts();
      onModuleUpdated();
    } catch (e: any) {
      alert(`上传失败: ${e.message}`);
    } finally {
      setUploading(false);
    }
  };

  const handleApproveReview = async (reviewId: string) => {
    if (!confirm('确认批准该变更单并将其正式设为当前模块的锁定基线 (Baseline) 吗？')) return;
    try {
      await api.approveChangeReview(reviewId, { approver: '统一审批人 (我)' });
      alert('变更单已批准！已正式设为基线并通知下游跟进。');
      setSelectedReview(null);
      await loadSessionAndArtifacts();
      onModuleUpdated();
    } catch (e: any) {
      alert(`审批失败: ${e.message}`);
    }
  };

  const handleRejectReview = async (reviewId: string) => {
    try {
      await api.rejectChangeReview(reviewId, {
        approver: '统一审批人 (我)',
        rejection_reason: rejectReason || '未通过审批，退回修改'
      });
      alert('变更单已驳回。');
      setRejectReason('');
      setSelectedReview(null);
      await loadSessionAndArtifacts();
      onModuleUpdated();
    } catch (e: any) {
      alert(`操作失败: ${e.message}`);
    }
  };

  const handleAckUpstream = async (upstreamCode?: string) => {
    try {
      setAckingUpstream(true);
      const updated = await api.ackUpstreamModule(module.id, upstreamCode);
      setModuleState(updated);
      setIsStaleDiffModalOpen(false);
      alert('已成功确认跟进！当前工序已同步至最新上游基线版本。');
      onModuleUpdated();
    } catch (e: any) {
      alert(`同步确认失败: ${e.message}`);
    } finally {
      setAckingUpstream(false);
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
    <div className="w-full max-w-[2160px] mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-5">
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
            {moduleState.execution_mode === 'human_driven' ? (
              <span className="text-[11px] px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-700 font-semibold border border-blue-200">
                真人主导 (专业工具作业)
              </span>
            ) : moduleState.execution_mode === 'hybrid' ? (
              <span className="text-[11px] px-2.5 py-0.5 rounded-full bg-teal-50 text-teal-700 font-semibold border border-teal-200">
                人机协同 (混合执行)
              </span>
            ) : (
              <span className="text-[11px] px-2.5 py-0.5 rounded-full bg-purple-50 text-purple-700 font-semibold border border-purple-200">
                Agent 驱动
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => setIsUploadModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 transition cursor-pointer"
            title="上传 HTML 交互原型包或全量文档"
          >
            <UploadCloud className="w-3.5 h-3.5" />
            上传交付包
          </button>

          {changeReviews.filter(r => r.status === 'pending_approval').length > 0 && (
            <button
              onClick={() => setSelectedReview(changeReviews.find(r => r.status === 'pending_approval') || null)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white shadow-xs transition cursor-pointer animate-pulse"
              title="有待审批的交付物变更"
            >
              <FileDiff className="w-3.5 h-3.5" />
              统一审批 ({changeReviews.filter(r => r.status === 'pending_approval').length})
            </button>
          )}

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

      {/* ⚠️ 上游交付物变更待跟进警示条 */}
      {moduleState.is_upstream_stale && (moduleState.stale_details?.length || 0) > 0 && (
        <div className="bg-amber-50/90 border border-amber-300 rounded-2xl p-4 text-xs text-amber-900 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3 animate-in fade-in duration-200">
          <div className="flex items-start gap-3">
            <div className="p-2 rounded-xl bg-amber-100 text-amber-700 shrink-0">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <div className="font-bold flex items-center gap-2 text-sm text-amber-900">
                <span>⚠️ 上游规范基线已演进更新 (待跟进对齐)</span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-200 text-amber-900 font-semibold font-mono">
                  {moduleState.stale_details?.length} 个待同步源
                </span>
              </div>
              <div className="text-amber-800 mt-1 space-y-0.5">
                {moduleState.stale_details?.map((detail, idx) => (
                  <div key={idx} className="flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
                    <span>{detail.message}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => {
                if (moduleState.stale_details && moduleState.stale_details.length > 0) {
                  setSelectedStaleDetail(moduleState.stale_details[0]);
                  setIsStaleDiffModalOpen(true);
                }
              }}
              className="px-3.5 py-2 rounded-xl text-xs font-semibold bg-white border border-amber-300 text-amber-800 hover:bg-amber-100 transition cursor-pointer flex items-center gap-1.5 shadow-2xs"
            >
              <FileDiff className="w-3.5 h-3.5" />
              查看变更 Diff
            </button>
            <button
              onClick={() => handleAckUpstream()}
              disabled={ackingUpstream}
              className="px-4 py-2 rounded-xl text-xs font-bold bg-amber-600 hover:bg-amber-500 text-white shadow-xs transition cursor-pointer flex items-center gap-1.5 disabled:opacity-50"
            >
              <CheckCheck className="w-4 h-4" />
              {ackingUpstream ? '同步中...' : '确认已跟进'}
            </button>
          </div>
        </div>
      )}

      {/* 待统一审批的变更通知栏 */}
      {changeReviews.filter(r => r.status === 'pending_approval').length > 0 && (
        <div className="bg-indigo-50/80 border border-indigo-200 rounded-2xl p-4 text-xs text-indigo-900 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-indigo-100 text-indigo-700 shrink-0">
              <FileDiff className="w-5 h-5" />
            </div>
            <div>
              <div className="font-bold text-sm text-indigo-900">
                本工序存在 {changeReviews.filter(r => r.status === 'pending_approval').length} 个待统一审批的变更交付物
              </div>
              <p className="text-indigo-700 mt-0.5">
                新上传的交付物需经由你统一审批裁决后，方可正式成为锁定基线并触发下游工序跟进。
              </p>
            </div>
          </div>
          <button
            onClick={() => setSelectedReview(changeReviews.find(r => r.status === 'pending_approval') || null)}
            className="px-4 py-2 rounded-xl text-xs font-bold bg-indigo-600 hover:bg-indigo-500 text-white shadow-xs transition cursor-pointer shrink-0"
          >
            立即审核变更单
          </button>
        </div>
      )}

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
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 h-[calc(100vh-190px)] min-h-[720px]">
        {/* 左侧：人机多轮协作会话 */}
        {panelLayout !== 'full' && (
          <div className={`${
            panelLayout === 'wide' ? 'lg:col-span-4' : 'lg:col-span-6'
          } bg-white border border-slate-200 rounded-2xl flex flex-col overflow-hidden shadow-xs transition-all duration-200`}>
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
                        <MarkdownViewer content={msg.content} variant="chat" />
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
            {/* 消息类型快速切换与专属技能入口 */}
            <div className="flex items-center justify-between mb-2 text-xs">
              <div className="flex items-center gap-1.5">
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

              {/* 工序 01 (市场研究) 技能下拉弹窗入口 */}
              {moduleState.module_code === '01' && (
                <div className="relative" ref={skillMenuRef}>
                  <button
                    type="button"
                    onClick={() => setShowSkillMenu(!showSkillMenu)}
                    className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 transition shadow-2xs cursor-pointer"
                  >
                    <TrendingUp className="w-3.5 h-3.5 text-blue-600" />
                    <span>调研技能</span>
                    <ChevronDown className={`w-3.5 h-3.5 text-blue-500 transition-transform duration-150 ${showSkillMenu ? 'rotate-180' : ''}`} />
                  </button>

                  {showSkillMenu && (
                    <div className="absolute right-0 bottom-full mb-1.5 w-76 bg-white border border-slate-200 rounded-xl shadow-xl p-1.5 z-30 animate-in fade-in zoom-in-95 duration-150">
                      <div className="px-2.5 py-1 text-[10px] font-bold text-slate-400 uppercase tracking-wider border-b border-slate-100 mb-1 flex items-center justify-between">
                        <span>市场研究专项技能</span>
                        <span className="text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded font-mono">5 项可用</span>
                      </div>
                      <div className="space-y-0.5">
                        <button
                          type="button"
                          onClick={() => {
                            setMessageType('question');
                            setInputText('请用自下而上 (Bottom-Up) 模型量化测算本产品的 TAM/SAM/SOM 市场空间与发展情景');
                            setShowSkillMenu(false);
                          }}
                          className="w-full text-left px-2.5 py-1.5 rounded-lg hover:bg-blue-50 transition flex items-start gap-2 group cursor-pointer"
                        >
                          <span className="text-sm shrink-0 mt-0.5">📊</span>
                          <div>
                            <div className="text-xs font-medium text-slate-800 group-hover:text-blue-700">TAM/SAM/SOM 测算</div>
                            <div className="text-[10px] text-slate-400">自下而上量化设备盘与 Blended ARPU</div>
                          </div>
                        </button>

                        <button
                          type="button"
                          onClick={() => {
                            setMessageType('question');
                            setInputText('深入拆解目标市场 Top 5 核心标杆竞品 5 维矩阵及 App Store 1-2星差评槽点');
                            setShowSkillMenu(false);
                          }}
                          className="w-full text-left px-2.5 py-1.5 rounded-lg hover:bg-blue-50 transition flex items-start gap-2 group cursor-pointer"
                        >
                          <span className="text-sm shrink-0 mt-0.5">🔍</span>
                          <div>
                            <div className="text-xs font-medium text-slate-800 group-hover:text-blue-700">竞品 5 维对比与差评</div>
                            <div className="text-[10px] text-slate-400">定价阶梯、流量来源与真实差评槽点</div>
                          </div>
                        </button>

                        <button
                          type="button"
                          onClick={() => {
                            setMessageType('question');
                            setInputText('提炼本产品核心 3 个典型目标客户画像 (ICP) 与真实未满足痛点');
                            setShowSkillMenu(false);
                          }}
                          className="w-full text-left px-2.5 py-1.5 rounded-lg hover:bg-blue-50 transition flex items-start gap-2 group cursor-pointer"
                        >
                          <span className="text-sm shrink-0 mt-0.5">🎯</span>
                          <div>
                            <div className="text-xs font-medium text-slate-800 group-hover:text-blue-700">目标客群画像 (ICP)</div>
                            <div className="text-[10px] text-slate-400">3类典型用户画像与 Jobs-To-Be-Done</div>
                          </div>
                        </button>

                        <button
                          type="button"
                          onClick={() => {
                            setMessageType('question');
                            setInputText('推演对抗巨头的价值缝隙 (Value Gap) 与前10,000名用户冷启动单点击穿切口 (Wedge)');
                            setShowSkillMenu(false);
                          }}
                          className="w-full text-left px-2.5 py-1.5 rounded-lg hover:bg-blue-50 transition flex items-start gap-2 group cursor-pointer"
                        >
                          <span className="text-sm shrink-0 mt-0.5">⚡</span>
                          <div>
                            <div className="text-xs font-medium text-slate-800 group-hover:text-blue-700">破局切入点 (Wedge)</div>
                            <div className="text-[10px] text-slate-400">价值缝隙与种子用户单点击穿打法</div>
                          </div>
                        </button>

                        <div className="border-t border-slate-100 my-1 pt-1">
                          <button
                            type="button"
                            onClick={() => {
                              setMessageType('instruction');
                              setInputText('综合上述分析，生成本单品正式的《市场研究与竞品深度洞察报告》交付物');
                              setShowSkillMenu(false);
                            }}
                            className="w-full text-left px-2.5 py-1.5 rounded-lg bg-emerald-50/70 hover:bg-emerald-100 text-emerald-900 transition flex items-start gap-2 group cursor-pointer border border-emerald-200/60"
                          >
                            <span className="text-sm shrink-0 mt-0.5">📑</span>
                            <div>
                              <div className="text-xs font-semibold text-emerald-800">生成完整市场研究报告</div>
                              <div className="text-[10px] text-emerald-600">全量推演并归档至交付物基准</div>
                            </div>
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
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
        )}

        {/* 右侧：产物看板与版本树 */}
        <div className={`${
          panelLayout === 'full'
            ? 'lg:col-span-12'
            : panelLayout === 'wide'
            ? 'lg:col-span-8'
            : 'lg:col-span-6'
        } bg-white border border-slate-200 rounded-2xl flex flex-col overflow-hidden shadow-xs transition-all duration-200`}>
          <div className="px-4 py-3 border-b border-slate-200 bg-slate-50/60 flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <FileCheck2 className="w-4 h-4 text-emerald-600" />
              <span className="text-xs font-semibold text-slate-800">交付物产物库 (Artifacts)</span>
              {panelLayout === 'full' && (
                <span className="text-[10px] text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded-full border border-indigo-200 font-medium">
                  全宽沉浸模式
                </span>
              )}
            </div>

            <div className="flex items-center gap-2">
              {/* 分栏布局比例控制 */}
              <div className="flex items-center bg-slate-200/70 p-0.5 rounded-lg text-[11px]">
                <button
                  type="button"
                  onClick={() => setPanelLayout('equal')}
                  className={`px-2 py-0.5 rounded-md transition cursor-pointer font-medium ${
                    panelLayout === 'equal'
                      ? 'bg-white text-slate-800 shadow-2xs font-semibold'
                      : 'text-slate-500 hover:text-slate-800'
                  }`}
                  title="双栏平衡 (5:5)"
                >
                  1:1
                </button>
                <button
                  type="button"
                  onClick={() => setPanelLayout('wide')}
                  className={`px-2 py-0.5 rounded-md transition cursor-pointer font-medium ${
                    panelLayout === 'wide'
                      ? 'bg-white text-slate-800 shadow-2xs font-semibold'
                      : 'text-slate-500 hover:text-slate-800'
                  }`}
                  title="产物加宽 (4:8)"
                >
                  1:2
                </button>
                <button
                  type="button"
                  onClick={() => setPanelLayout(panelLayout === 'full' ? 'equal' : 'full')}
                  className={`px-2 py-0.5 rounded-md transition cursor-pointer font-medium flex items-center gap-1 ${
                    panelLayout === 'full'
                      ? 'bg-white text-indigo-700 shadow-2xs font-semibold'
                      : 'text-slate-500 hover:text-slate-800'
                  }`}
                  title={panelLayout === 'full' ? '还原为双栏视图' : '产物全宽沉浸阅读'}
                >
                  {panelLayout === 'full' ? <Minimize2 className="w-3 h-3 text-indigo-600" /> : <Maximize2 className="w-3 h-3" />}
                  <span>{panelLayout === 'full' ? '还原' : '全宽'}</span>
                </button>
              </div>

              <button
                type="button"
                onClick={() => setIsUploadModalOpen(true)}
                className="px-2.5 py-1 rounded-lg text-[11px] font-medium bg-white hover:bg-slate-100 text-slate-700 border border-slate-200 shadow-2xs flex items-center gap-1 cursor-pointer transition"
                title="上传 HTML 交互原型包或全量文档"
              >
                <UploadCloud className="w-3.5 h-3.5 text-blue-600" />
                上传新版本
              </button>

              {/* 版本切换下拉 */}
              {artifacts.length > 0 && (
                <div className="flex items-center gap-1.5">
                  <span className="text-[11px] text-slate-500">版本:</span>
                  <select
                    value={selectedArtifact?.id}
                    onChange={e => {
                      const found = artifacts.find(a => a.id === e.target.value);
                      if (found) {
                        setSelectedArtifact(found);
                        if (found.artifact_type === 'html_bundle') {
                          setArtifactViewMode('preview');
                        }
                      }
                    }}
                    className="bg-white border border-slate-200 rounded px-2 py-0.5 text-xs text-emerald-800 font-mono font-medium shadow-2xs"
                  >
                    {artifacts.map(a => (
                      <option key={a.id} value={a.id}>
                        v{a.version} {a.is_baseline ? '(基线)' : ''} {a.artifact_type === 'html_bundle' ? '[原型包]' : ''} - {new Date(a.created_at).toLocaleTimeString()}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          </div>

          {/* 若为 HTML 原型包，展示视图切换条与视口缩放控制 */}
          {selectedArtifact && selectedArtifact.artifact_type === 'html_bundle' && (
            <div className="px-4 py-2 border-b border-slate-200 bg-slate-100/70 flex items-center justify-between text-xs">
              <div className="flex items-center gap-1 bg-slate-200/80 p-0.5 rounded-lg">
                <button
                  type="button"
                  onClick={() => setArtifactViewMode('preview')}
                  className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition cursor-pointer flex items-center gap-1 ${
                    artifactViewMode === 'preview'
                      ? 'bg-white text-slate-900 shadow-2xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  <Monitor className="w-3.5 h-3.5 text-blue-600" />
                  交互原型预览
                </button>
                <button
                  type="button"
                  onClick={() => setArtifactViewMode('content')}
                  className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition cursor-pointer flex items-center gap-1 ${
                    artifactViewMode === 'content'
                      ? 'bg-white text-slate-900 shadow-2xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  <Eye className="w-3.5 h-3.5 text-slate-500" />
                  DOM与结构源码
                </button>
              </div>

              {artifactViewMode === 'preview' && (
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1 bg-white border border-slate-200 rounded-lg p-0.5">
                    <button
                      type="button"
                      onClick={() => setPrototypeViewport('desktop')}
                      className={`p-1 rounded transition cursor-pointer ${
                        prototypeViewport === 'desktop' ? 'bg-slate-200 text-slate-900' : 'text-slate-400 hover:text-slate-600'
                      }`}
                      title="桌面全宽"
                    >
                      <Monitor className="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => setPrototypeViewport('tablet')}
                      className={`p-1 rounded transition cursor-pointer ${
                        prototypeViewport === 'tablet' ? 'bg-slate-200 text-slate-900' : 'text-slate-400 hover:text-slate-600'
                      }`}
                      title="平板视口 (768px)"
                    >
                      <Tablet className="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => setPrototypeViewport('mobile')}
                      className={`p-1 rounded transition cursor-pointer ${
                        prototypeViewport === 'mobile' ? 'bg-slate-200 text-slate-900' : 'text-slate-400 hover:text-slate-600'
                      }`}
                      title="手机视口 (375px)"
                    >
                      <Smartphone className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  <a
                    href={api.getArtifactPreviewUrl(selectedArtifact.id)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="p-1.5 rounded-lg bg-white border border-slate-200 text-slate-600 hover:text-blue-600 shadow-2xs transition"
                    title="新窗口全屏打开原型"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                </div>
              )}
            </div>
          )}

          {/* 产物内容实时渲染 */}
          <div className="flex-1 overflow-y-auto bg-white flex flex-col">
            {selectedArtifact ? (
              selectedArtifact.artifact_type === 'html_bundle' && artifactViewMode === 'preview' ? (
                <div className="flex-1 bg-slate-100/80 p-3 flex items-center justify-center overflow-auto min-h-[460px]">
                  <div
                    className={`h-[580px] bg-white rounded-xl shadow-md border border-slate-300 overflow-hidden transition-all duration-300 flex flex-col ${
                      prototypeViewport === 'mobile'
                        ? 'w-[375px]'
                        : prototypeViewport === 'tablet'
                        ? 'w-[768px]'
                        : 'w-full'
                    }`}
                  >
                    <div className="h-6 bg-slate-200/80 border-b border-slate-300 flex items-center px-3 gap-1.5 shrink-0">
                      <div className="w-2 h-2 rounded-full bg-rose-400"></div>
                      <div className="w-2 h-2 rounded-full bg-amber-400"></div>
                      <div className="w-2 h-2 rounded-full bg-emerald-400"></div>
                      <span className="text-[10px] text-slate-500 font-mono ml-2 truncate">
                        {selectedArtifact.entry_file || 'index.html'} (v{selectedArtifact.version})
                      </span>
                    </div>
                    <iframe
                      src={api.getArtifactPreviewUrl(selectedArtifact.id)}
                      className="w-full flex-1 border-0 bg-white"
                      title={selectedArtifact.title}
                      sandbox="allow-scripts allow-same-origin allow-forms"
                    />
                  </div>
                </div>
              ) : (
                <div className="p-4 md:p-6 bg-slate-50/60 min-h-full flex flex-col">
                  {/* 文档白板容器 */}
                  <div className="bg-white border border-slate-200/90 rounded-2xl shadow-xs p-6 md:p-8 w-full flex-1 flex flex-col">
                    {/* 文档头部元信息与操作条 */}
                    <div className="flex items-start justify-between pb-5 border-b border-slate-200 flex-wrap gap-4 mb-5">
                      <div className="space-y-1.5">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-md bg-emerald-100 text-emerald-800 border border-emerald-200">
                            v{selectedArtifact.version}
                          </span>
                          {selectedArtifact.is_baseline && (
                            <span className="px-2 py-0.5 rounded-md text-xs bg-emerald-50 text-emerald-800 border border-emerald-200 font-semibold flex items-center gap-1 shadow-2xs">
                              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                              当前工序锁定基线 (Baseline)
                            </span>
                          )}
                          <span className="text-xs text-slate-400 font-mono">
                            {selectedArtifact.content.length.toLocaleString()} 字符
                          </span>
                        </div>
                        <h1 className="text-lg md:text-xl font-bold text-slate-900 tracking-tight">
                          {selectedArtifact.title}
                        </h1>
                        <div className="flex items-center gap-3 text-[11px] text-slate-400 font-mono">
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3 text-slate-400" />
                            {new Date(selectedArtifact.created_at).toLocaleString('zh-CN', { hour12: false })}
                          </span>
                          <span className="flex items-center gap-1">
                            <Hash className="w-3 h-3 text-slate-400" />
                            SHA-256: {selectedArtifact.content_hash.slice(0, 12)}...
                          </span>
                        </div>
                      </div>

                      {/* 快捷操作区：复制全文与下载 */}
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={handleCopyArtifact}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 shadow-2xs transition cursor-pointer"
                          title="复制 Markdown 源码全文"
                        >
                          {copiedArtifact ? (
                            <>
                              <Check className="w-3.5 h-3.5 text-emerald-600" />
                              <span className="text-emerald-700">已复制全文</span>
                            </>
                          ) : (
                            <>
                              <Copy className="w-3.5 h-3.5 text-slate-500" />
                              <span>复制全文</span>
                            </>
                          )}
                        </button>

                        <button
                          type="button"
                          onClick={handleDownloadArtifact}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 shadow-2xs transition cursor-pointer"
                          title="下载为 Markdown 文件 (.md)"
                        >
                          <Download className="w-3.5 h-3.5 text-slate-500" />
                          <span>下载 .md</span>
                        </button>
                      </div>
                    </div>

                    {/* 版本变更说明 */}
                    {selectedArtifact.change_summary && (
                      <div className="bg-blue-50/80 border border-blue-200 rounded-xl p-3.5 text-xs text-blue-900 mb-6 shadow-2xs">
                        <div className="font-semibold flex items-center gap-1.5 text-blue-900 mb-1">
                          <span>📝</span>
                          <span>本版本关键变更说明：</span>
                        </div>
                        <p className="text-blue-800 leading-relaxed pl-5">
                          {selectedArtifact.change_summary}
                        </p>
                      </div>
                    )}

                    {/* 文档排版正文 */}
                    <div className="flex-1">
                      <MarkdownViewer content={selectedArtifact.content} variant="artifact" />
                    </div>
                  </div>
                </div>
              )
            ) : (
              <div className="text-center py-24 text-slate-400 text-xs flex-1 flex flex-col items-center justify-center">
                <UploadCloud className="w-10 h-10 text-slate-300 mb-2" />
                尚无生成产物。<br />在左侧输入指令让 Agent 产出，或点击上方【上传新版本】提交原型与文档。
              </div>
            )}
          </div>

          {/* 底部关联的 Issue 状态预览 */}
          <div className="px-4 py-2.5 border-t border-slate-200 bg-slate-50/60 flex items-center justify-between text-xs text-slate-500">
            <span className="flex items-center gap-1.5">
              <Bug className="w-3.5 h-3.5 text-rose-600" />
              关联 Issue: {openIssues.length} 个未关闭
            </span>
            <span className="text-[11px] text-slate-400 font-mono">不可变快照隔离存储</span>
          </div>
        </div>
      </div>

      {/* 弹窗 1: 上传全量交付物包 (HTML/ZIP/MD) */}
      {isUploadModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 w-full max-w-lg rounded-2xl p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-100">
              <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
                <UploadCloud className="w-5 h-5 text-blue-600" />
                上传工序交付物包 (HTML 原型 / 文档)
              </h3>
              <button
                onClick={() => setIsUploadModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleUploadBundle} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  选择文件 (.zip, .html, .md, .txt) *
                </label>
                <p className="text-[11px] text-slate-500 mb-2">
                  支持包含 <code>index.html</code>、<code>assets/</code>、<code>preview/</code> 等目录的 ZIP 交互原型包，系统将自动解压并提供交互 iframe 预览。
                </p>
                <input
                  type="file"
                  required
                  accept=".zip,.html,.htm,.md,.markdown,.txt"
                  onChange={e => setUploadFile(e.target.files ? e.target.files[0] : null)}
                  className="w-full text-xs text-slate-600 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 cursor-pointer border border-slate-300 rounded-xl p-2 bg-slate-50"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  版本变更核心意图说明 (Change Summary) *
                </label>
                <textarea
                  rows={3}
                  required
                  placeholder="简要描述本次交付物更新的核心改动，例：依据业务评审调整了底部结算抽屉交互，增加多币种选择器规范..."
                  value={uploadSummary}
                  onChange={e => setUploadSummary(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-xl p-3 text-xs text-slate-900 focus:bg-white focus:outline-none focus:border-blue-500"
                />
              </div>

              <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-[11px] text-amber-800">
                💡 上传后系统将自动生成统一变更审批单 (ChangeReview)，经由统一审批通过后正式升级为基线，并通知下游工序跟进。
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsUploadModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs font-medium text-slate-600 hover:bg-slate-100 transition cursor-pointer"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={uploading || !uploadFile}
                  className="px-5 py-2 rounded-xl text-xs font-bold bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white transition cursor-pointer shadow-xs"
                >
                  {uploading ? '上传解压中...' : '确认上传并提交审批'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 弹窗 2: 统一审批单详情弹窗 (我统一审批) */}
      {selectedReview && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 w-full max-w-2xl rounded-2xl p-6 shadow-2xl flex flex-col max-h-[85vh]">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <FileDiff className="w-5 h-5 text-indigo-600" />
                <h3 className="font-bold text-slate-900 text-base">{selectedReview.title}</h3>
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                  selectedReview.status === 'approved'
                    ? 'bg-emerald-100 text-emerald-800'
                    : selectedReview.status === 'rejected'
                    ? 'bg-rose-100 text-rose-800'
                    : 'bg-amber-100 text-amber-800'
                }`}>
                  {selectedReview.status === 'approved' ? '已批准' : selectedReview.status === 'rejected' ? '已驳回' : '待我统一审批'}
                </span>
              </div>
              <button
                onClick={() => setSelectedReview(null)}
                className="text-slate-400 hover:text-slate-600 cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto py-4 space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3 bg-slate-50 p-3 rounded-xl border border-slate-200 text-slate-700">
                <div>
                  <span className="text-slate-400">版本演进:</span>{' '}
                  <span className="font-mono font-bold text-slate-900">
                    v{selectedReview.from_version} → v{selectedReview.to_version}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400">提交时间:</span>{' '}
                  <span>{new Date(selectedReview.created_at).toLocaleString()}</span>
                </div>
                {selectedReview.approver && (
                  <div>
                    <span className="text-slate-400">审批人:</span>{' '}
                    <span className="font-semibold text-slate-900">{selectedReview.approver}</span>
                  </div>
                )}
                {selectedReview.rejection_reason && (
                  <div className="col-span-2 text-rose-700 bg-rose-50 p-2 rounded border border-rose-200">
                    <strong>驳回原因:</strong> {selectedReview.rejection_reason}
                  </div>
                )}
              </div>

              {/* 差异分析报告 Markdown */}
              <div className="border border-slate-200 rounded-xl p-4 bg-white space-y-2">
                <div className="font-bold text-slate-800 flex items-center gap-1.5 pb-2 border-b border-slate-100">
                  <Sparkles className="w-4 h-4 text-indigo-600" />
                  变更差异分析与影响评估
                </div>
                <div>
                  <MarkdownViewer content={selectedReview.diff_summary} variant="chat" />
                </div>
              </div>

              {/* 若为待审批状态，提供驳回原因输入 */}
              {selectedReview.status === 'pending_approval' && (
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    若驳回请输入原因 (可选):
                  </label>
                  <input
                    type="text"
                    placeholder="如：缺少异常流交互规范，请补充后再提审..."
                    value={rejectReason}
                    onChange={e => setRejectReason(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900"
                  />
                </div>
              )}
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setSelectedReview(null)}
                className="px-4 py-2 rounded-xl text-xs font-medium text-slate-600 hover:bg-slate-100 transition cursor-pointer"
              >
                关闭
              </button>
              {selectedReview.status === 'pending_approval' && (
                <>
                  <button
                    type="button"
                    onClick={() => handleRejectReview(selectedReview.id)}
                    className="px-4 py-2 rounded-xl text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-100 transition cursor-pointer"
                  >
                    驳回变更
                  </button>
                  <button
                    type="button"
                    onClick={() => handleApproveReview(selectedReview.id)}
                    className="px-5 py-2 rounded-xl text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white shadow-xs transition cursor-pointer flex items-center gap-1.5"
                  >
                    <CheckCheck className="w-4 h-4" />
                    批准并生效基线 (Baseline)
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 弹窗 3: 上游变更差异对齐弹窗 */}
      {isStaleDiffModalOpen && selectedStaleDetail && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 w-full max-w-lg rounded-2xl p-6 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-amber-600" />
                <h3 className="font-bold text-slate-900 text-base">
                  上游规范对齐：【{selectedStaleDetail.upstream_name}】
                </h3>
              </div>
              <button
                onClick={() => setIsStaleDiffModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="py-4 space-y-3 text-xs">
              <div className="bg-amber-50/80 border border-amber-200 p-3 rounded-xl text-amber-900 space-y-1">
                <div className="font-bold">版本状态：</div>
                <div>当前工序跟进基准：<strong>v{selectedStaleDetail.current_synced_version}</strong></div>
                <div>上游最新已锁定基准：<strong>v{selectedStaleDetail.latest_upstream_version}</strong></div>
                <div className="pt-1 text-amber-800">{selectedStaleDetail.message}</div>
              </div>

              <div className="bg-slate-50 border border-slate-200 p-3 rounded-xl text-slate-700 text-xs">
                <p>
                  上游模块负责人已完成新版本交付并经统一审批通过。若研发或测试团队已查阅最新上游文档/原型，请点击下方【确认已跟进】，工序状态将恢复为最新对齐。
                </p>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setIsStaleDiffModalOpen(false)}
                className="px-4 py-2 rounded-xl text-xs font-medium text-slate-600 hover:bg-slate-100 transition cursor-pointer"
              >
                稍后跟进
              </button>
              <button
                type="button"
                onClick={() => handleAckUpstream(selectedStaleDetail.upstream_code)}
                disabled={ackingUpstream}
                className="px-5 py-2 rounded-xl text-xs font-bold bg-amber-600 hover:bg-amber-500 text-white shadow-xs transition cursor-pointer flex items-center gap-1.5"
              >
                <CheckCheck className="w-4 h-4" />
                {ackingUpstream ? '同步中...' : '确认已完成跟进与对齐'}
              </button>
            </div>
          </div>
        </div>
      )}

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
