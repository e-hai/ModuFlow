import React, { useEffect, useState, useRef } from 'react';
import { api } from '../services/api';
import { ModuleInstance, CollaborationSession, SessionMessage, Artifact, Issue, ChangeReview, StaleDetail, GateConfig, GateApplication } from '../types';
import { PhaseBadge, SeverityBadge } from '../components/StatusBadge';
import { NewIssueModal } from '../components/NewIssueModal';
import { MarkdownViewer } from '../components/MarkdownViewer';
import { GateBadge } from '../components/gate/GateBadge';
import { GateApplicationModal } from '../components/gate/GateApplicationModal';
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
  Minimize2,
  Columns2,
  GitPullRequest,
  ArrowLeftRight
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
  const [messageType, setMessageType] = useState<SessionMessage['message_type']>(
    module.module_code === '01' ? 'question' : 'instruction'
  );
  const [sending, setSending] = useState(false);
  const [isIssueModalOpen, setIsIssueModalOpen] = useState(false);
  const [moduleState, setModuleState] = useState<ModuleInstance>(module);
  const [moduleIssues, setModuleIssues] = useState<Issue[]>([]);
  const [agentCommand, setAgentCommand] = useState<string>('agy');
  const [agentStage, setAgentStage] = useState<'idle' | 'context' | 'spawning' | 'reasoning' | 'completed' | 'error'>('idle');
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);

  // Architecture Optimization & Unified Approvals state
  const [changeReviews, setChangeReviews] = useState<ChangeReview[]>([]);
  const [selectedReview, setSelectedReview] = useState<ChangeReview | null>(null);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [isStaleDiffModalOpen, setIsStaleDiffModalOpen] = useState(false);
  const [selectedStaleDetail, setSelectedStaleDetail] = useState<StaleDetail | null>(null);

  // Three-Tier Gate System state
  const [isGateModalOpen, setIsGateModalOpen] = useState(false);
  const [moduleGateConfig, setModuleGateConfig] = useState<GateConfig | null>(null);
  const [moduleGateApp, setModuleGateApp] = useState<GateApplication | null>(null);
  const [prototypeViewport, setPrototypeViewport] = useState<'desktop' | 'tablet' | 'mobile'>('desktop');
  const [artifactViewMode, setArtifactViewMode] = useState<'preview' | 'content'>('preview');
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadSummary, setUploadSummary] = useState('');
  const [uploading, setUploading] = useState(false);
  const [ackingUpstream, setAckingUpstream] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [copiedArtifact, setCopiedArtifact] = useState(false);
  const [panelLayout, setPanelLayout] = useState<'equal' | 'wide' | 'full'>('equal');
  const [isLayoutDropdownOpen, setIsLayoutDropdownOpen] = useState(false);
  const layoutDropdownRef = useRef<HTMLDivElement>(null);
  const [readingLayer, setReadingLayer] = useState<'executive' | 'full'>('executive');

  const splitArtifactLayers = (rawContent: string) => {
    if (!rawContent) return { executiveContent: '', hasSecondLayer: false, hiddenChars: 0 };
    if (rawContent.includes('<!-- EXECUTIVE_GATE_END -->')) {
      const [execPart, restPart] = rawContent.split('<!-- EXECUTIVE_GATE_END -->');
      return {
        executiveContent: execPart.trim(),
        hasSecondLayer: Boolean(restPart && restPart.trim().length > 100),
        hiddenChars: restPart ? restPart.trim().length : 0,
      };
    }
    const sec1Idx = rawContent.indexOf('\n## 一、');
    if (sec1Idx !== -1 && (rawContent.includes('拍板摘要') || rawContent.includes('Executive Gate'))) {
      const execPart = rawContent.slice(0, sec1Idx).trim();
      const restPart = rawContent.slice(sec1Idx).trim();
      return {
        executiveContent: execPart,
        hasSecondLayer: restPart.length > 100,
        hiddenChars: restPart.length,
      };
    }
    return { executiveContent: rawContent, hasSecondLayer: false, hiddenChars: 0 };
  };

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<any>(null);

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
    setMessageType(module.module_code === '01' ? 'question' : 'instruction');
    loadSessionAndArtifacts();
    api.getAgentSettings().then(s => {
      if (s?.cli_command) setAgentCommand(s.cli_command);
    }).catch(() => {});
  }, [module.id]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, sending, agentStage]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (layoutDropdownRef.current && !layoutDropdownRef.current.contains(event.target as Node)) {
        setIsLayoutDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

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

      // Load Gate System data
      try {
        const [gc, ga] = await Promise.allSettled([
          api.getModuleGateConfig(module.id),
          api.getModuleGateApplication(module.id)
        ]);
        if (gc.status === 'fulfilled') setModuleGateConfig(gc.value);
        if (ga.status === 'fulfilled') setModuleGateApp(ga.value);
        else setModuleGateApp(null);
      } catch (_) {}

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
    if (!confirm('确认批准该变更单并将其正式设为当前工序的定稿基准 (Baseline) 吗？')) return;
    try {
      await api.approveChangeReview(reviewId, { approver: '定稿审批人' });
      alert('变更单已批准！已正式设为定稿基准并通知下游跟进。');
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

  const executeSendMessage = async (
    content: string,
    currentMsgType: SessionMessage['message_type'],
    issueRefId?: string
  ) => {
    if (!content.trim() || !session || sending) return;

    // 1. Optimistic UI: Immediately show the user's question or instruction in the chat history
    const tempId = `temp-${Date.now()}`;
    const optimisticMsg: SessionMessage = {
      id: tempId,
      session_id: session.id,
      sender: '我 (业务负责人)',
      sender_role: 'human',
      message_type: currentMsgType,
      content,
      issue_ref_id: issueRefId,
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
          content,
          issue_ref_id: issueRefId
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

      // Reload artifacts, session, and module state
      await loadSessionAndArtifacts();
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

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim() || !session || sending) return;

    const content = inputText.trim();
    const currentMsgType = messageType;
    setInputText('');
    await executeSendMessage(content, currentMsgType);
  };

  const handleAcceptCR = async (cr: Issue) => {
    const promptText = `采纳来自协同工序【${cr.reporter || cr.reporter_role || '设计/开发团队'}】的需求变更单 [${cr.id}]: ${cr.title}。\n` +
      `【需求矛盾说明】：${cr.description?.unreasonable_point || cr.description?.summary || ''}\n` +
      `【约束条件】：${cr.description?.constraint || '保证端到端一致性与工程可行性'}\n` +
      `【建议方案】：${cr.description?.suggested_change || cr.description?.expected || ''}\n` +
      `请结合当前交付物与工作区战略底稿，全面评估对整体架构与商业模型的影响，修订 PRD 相关章节（含信息架构、功能规格、数据契约及验收标准），生成新版 PRD 交付物。`;

    await executeSendMessage(promptText, 'feedback', cr.id);
  };

  const handleAutoReviseFromUpstream = async (staleDetail: StaleDetail) => {
    const promptText = `上游【${staleDetail.upstream_name}】已演进并定稿至基线 v${staleDetail.latest_upstream_version}。\n` +
      `【主要变更说明】：${staleDetail.upstream_change_summary || '上游基线规格已更新'}\n` +
      `请根据上游最新定稿成果及前后版本差异，增量修订本工序（${moduleState.name}）的交付物规范与对应设计/工程资产，确保与上游 PRD 契约严格对齐。`;

    await executeSendMessage(promptText, 'feedback');
    try {
      await api.ackUpstreamModule(module.id, staleDetail.upstream_code);
      const updated = await api.getModule(module.id);
      setModuleState(updated);
    } catch (e) {
      // ignore
    }
  };

  const handleBaseline = async () => {
    // 关口审批硬拦截：若关口为黄级或红级且尚未获批，弹出关口一页纸申请单供人类签字
    const effectiveLevel = moduleGateApp?.effective_level || moduleGateConfig?.level || 'green';
    if ((effectiveLevel === 'yellow' || effectiveLevel === 'red') && moduleGateApp?.status !== 'approved') {
      alert(`【${moduleGateConfig?.name || '当前工序关口'}】为 ${effectiveLevel === 'red' ? '🔴 红级关口 (人类即时必批)' : '🟡 黄级关口 (人类批量审批)'}。\n系统已强制阻断自动放行，请在打开的一页纸申请单中由人类战略层签署审批意见。`);
      setIsGateModalOpen(true);
      return;
    }

    if (!confirm('确认将当前工序成果定稿为正式基准 (Baseline) 吗？')) return;
    try {
      const updated = await api.updateModulePhase(module.id, 'baselined');
      setModuleState(updated);
      alert('已成功定稿！');
      onModuleUpdated();
      await loadSessionAndArtifacts();
    } catch (e: any) {
      alert(`定稿检查未通过: ${e.message}\n请检查关口申请单与准入条件。`);
      setIsGateModalOpen(true);
    }
  };

  const handleCreateIssue = async (issueData: any) => {
    await api.createIssue(issueData);
    alert('协同问题已提交并派发至责任环节！');
    await loadSessionAndArtifacts();
    onModuleUpdated();
  };

  const blockingIssues = moduleIssues.filter(
    i => (i.severity === 'critical' || i.severity === 'major') && i.status !== 'closed'
  );
  const openIssues = moduleIssues.filter(i => i.status !== 'closed');
  const incomingCRs = moduleIssues.filter(
    i => i.category === 'requirement_cr' && i.status !== 'closed'
  );

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
            <h1 className="text-lg font-bold text-slate-900">{moduleState.name}</h1>
            <PhaseBadge phase={moduleState.phase} />
            {moduleGateApp ? (
              <GateBadge
                level={moduleGateApp.effective_level}
                gateName={moduleGateApp.gate_name}
                isEscalated={moduleGateApp.is_escalated}
                size="sm"
              />
            ) : moduleGateConfig ? (
              <GateBadge
                level={moduleGateConfig.level}
                gateName={moduleGateConfig.name}
                size="sm"
              />
            ) : null}
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* 一页纸阶段把关拍板卡 */}
          <button
            onClick={() => setIsGateModalOpen(true)}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 transition cursor-pointer shadow-2xs"
            title="查看或提报本工序阶段把关确认单"
          >
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
            <span>阶段把关拍板卡</span>
            {moduleGateApp?.status === 'pending' && (
              <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
            )}
            {moduleGateApp?.status === 'approved' && (
              <span className="text-[10px] text-emerald-700 font-bold">✓ 已批准</span>
            )}
          </button>

          {changeReviews.filter(r => r.status === 'pending_approval').length > 0 && (
            <button
              onClick={() => setSelectedReview(changeReviews.find(r => r.status === 'pending_approval') || null)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white shadow-xs transition cursor-pointer animate-pulse"
              title="有待审批的交付物版本变更"
            >
              <FileDiff className="w-3.5 h-3.5" />
              交付物变更审批 ({changeReviews.filter(r => r.status === 'pending_approval').length})
            </button>
          )}

          <button
            onClick={() => setIsIssueModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 transition cursor-pointer"
            title="向相关责任环节反馈协同问题或修改诉求"
          >
            <Bug className="w-3.5 h-3.5" />
            反馈协同问题
          </button>

          {moduleState.phase !== 'baselined' ? (
            <button
              onClick={handleBaseline}
              className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-medium bg-emerald-600 hover:bg-emerald-500 text-white shadow-xs transition cursor-pointer"
            >
              <FileCheck2 className="w-4 h-4" />
              定稿并推进下一阶段
            </button>
          ) : selectedArtifact && !selectedArtifact.is_baseline ? (
            <button
              onClick={handleBaseline}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-medium bg-emerald-600 hover:bg-emerald-500 text-white shadow-xs transition cursor-pointer"
              title="将当前最新交付物版本设为工序定稿基准"
            >
              <FileCheck2 className="w-4 h-4" />
              更新阶段定稿基准
            </button>
          ) : null}
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
                <span>⚠️ 上游成果已有最新定稿 (待同步跟进)</span>
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
              对比版本修改
            </button>
            <button
              onClick={() => handleAutoReviseFromUpstream(moduleState.stale_details![0])}
              disabled={sending}
              className="px-3.5 py-2 rounded-xl text-xs font-bold bg-indigo-600 hover:bg-indigo-500 text-white shadow-xs transition cursor-pointer flex items-center gap-1.5 disabled:opacity-50"
              title="基于上游 PRD 最新变更说明，让 Agent 自动增量调整本工序成果并对齐基线"
            >
              <Sparkles className="w-3.5 h-3.5" />
              基于上游变更自动增量修订本工序
            </button>
            <button
              onClick={() => handleAckUpstream()}
              disabled={ackingUpstream}
              className="px-3 py-2 rounded-xl text-xs font-semibold bg-white border border-amber-300 text-amber-800 hover:bg-amber-100 transition cursor-pointer flex items-center gap-1.5 disabled:opacity-50"
            >
              <CheckCheck className="w-4 h-4" />
              {ackingUpstream ? '同步中...' : '仅标记已对齐'}
            </button>
          </div>
        </div>
      )}

      {/* 📥 收到来自下游工序的需求变更单 (CR) 专有看板 */}
      {incomingCRs.length > 0 && (
        <div className="bg-gradient-to-r from-indigo-50/90 via-purple-50/80 to-white border border-indigo-200 rounded-2xl p-4 text-xs text-indigo-950 shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="p-1.5 rounded-lg bg-indigo-100 text-indigo-700">
                <GitPullRequest className="w-4 h-4" />
              </div>
              <span className="font-bold text-sm text-indigo-900">
                收到来自协同工序的 {incomingCRs.length} 个需求变更请求 (CR)
              </span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-800 font-semibold font-mono">
                待响应修订
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {incomingCRs.map(cr => (
              <div key={cr.id} className="bg-white/95 border border-indigo-100 rounded-xl p-3 shadow-2xs space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="font-semibold text-slate-900 flex items-center gap-1.5">
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                      {cr.id}
                    </span>
                    <span>{cr.title}</span>
                  </div>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${
                    cr.severity === 'critical' ? 'bg-rose-100 text-rose-700' : 'bg-amber-100 text-amber-700'
                  }`}>
                    {cr.severity.toUpperCase()}
                  </span>
                </div>

                {cr.description?.unreasonable_point && (
                  <div className="text-[11px] text-slate-600 bg-slate-50 rounded-lg p-2">
                    <span className="font-semibold text-slate-700">矛盾说明：</span>
                    {cr.description.unreasonable_point}
                  </div>
                )}

                {cr.description?.suggested_change && (
                  <div className="text-[11px] text-indigo-900 bg-indigo-50/60 rounded-lg p-2">
                    <span className="font-semibold text-indigo-800">建议方案：</span>
                    {cr.description.suggested_change}
                  </div>
                )}

                <div className="flex items-center justify-between pt-1">
                  <span className="text-[10px] text-slate-400">
                    提出方: {cr.reporter || cr.reporter_role}
                  </span>
                  <button
                    onClick={() => handleAcceptCR(cr)}
                    disabled={sending}
                    className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white shadow-2xs transition cursor-pointer flex items-center gap-1.5 disabled:opacity-50"
                  >
                    <ArrowLeftRight className="w-3.5 h-3.5" />
                    采纳此 CR 并修订 PRD
                  </button>
                </div>
              </div>
            ))}
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
                新上传的成果需经由统一审批裁决后，方可正式生效为定稿基准并触发下游工序跟进。
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

      {/* 阻塞性 Issue 警示条 */}
      {blockingIssues.length > 0 && (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-3.5 text-xs text-rose-800 flex items-center justify-between">
          <div>
            <strong>定稿门禁警示：</strong>当前工序存在 {blockingIssues.length} 个未解决的严重卡点问题（
            {blockingIssues.map(i => i.id).join(', ')}），在责任工序彻底解决并验证关闭前，暂不能正式定稿。
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
              <span className="text-xs font-semibold text-slate-800">讨论与生成记录</span>
              <span className="text-[10px] text-slate-500 font-mono">({messages.length} 轮)</span>
            </div>
          </div>

          {/* 消息滚动列表 */}
          <div className="flex-1 p-4 overflow-y-auto space-y-4 bg-slate-50/30">
            {/* 工序 01 顶部极简一行文字动线说明（无多余图标与重复按钮） */}
            {moduleState.module_code === '01' && (
              <div className="bg-slate-100/80 border border-slate-200/90 rounded-lg px-3 py-2 text-[11px] text-slate-600 flex items-center justify-between gap-2">
                <span>
                  <strong className="text-slate-800">使用顺序：</strong>
                  1. 先在下方输入您观察到的应用/趋势（或点选快捷追问）与市场负责人探讨 &nbsp;→&nbsp; 2. 聊透后切至「生成右侧报告」汇总定稿。
                </span>
              </div>
            )}

            {messages.length === 0 && !sending ? (
              <div className="text-center py-12 text-slate-400 text-xs">
                {moduleState.module_code === '01' ? (
                  <>当前尚未开始对话。请直接在下方输入你看到的<strong>热门应用或趋势想法</strong>，先与市场负责人探讨。</>
                ) : (
                  <>当前协作室尚未发起讨论。<br />可在下方先与负责人对话探讨，或直接生成右侧成果初稿。</>
                )}
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
                          <span>AI 智能体执行遇到异常。系统已如实记录，请检查网络连接、AI 引擎设置或稍后重试。</span>
                        </div>
                      </div>
                    </div>
                  );
                }

                return (
                  <div
                    key={msg.id}
                    className={`${isAgent ? 'bg-white shadow-2xs' : 'bg-slate-50/80'} p-3 rounded-xl border border-slate-200`}
                  >
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
                              ? '成果初稿'
                              : msg.message_type === 'revised_artifact'
                              ? '成果修订稿'
                              : msg.message_type === 'feedback'
                              ? '修改建议'
                              : msg.message_type === 'question'
                              ? '探讨咨询'
                              : msg.message_type === 'answer'
                              ? 'AI 答复'
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
                        <div className="mt-2 inline-flex items-center px-2 py-0.5 rounded bg-emerald-50 text-[11px] text-emerald-800 border border-emerald-200">
                          已关联生成右侧成果版本
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
                      {moduleState.primary_role?.name?.replace(' Agent', '') || '系统'} 正在处理 ({elapsedSeconds}s)
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-[11px] font-mono text-slate-600 bg-white px-2 py-0.5 rounded-md border border-slate-200 shadow-2xs font-medium">
                      {agentCommand} 引擎
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
                      <span className="truncate">1. 组装前置资料</span>
                    </div>
                    <div className="text-[10px] text-slate-500 mt-1 leading-tight">
                      {agentStage === 'context'
                        ? '正在分析战略背景与工序输入...'
                        : '背景资料与指导原则已就位'}
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
                      <span className="truncate">2. 准备运行环境</span>
                    </div>
                    <div className="text-[10px] text-slate-500 mt-1 leading-tight">
                      {agentStage === 'spawning'
                        ? '正在初始化运行环境与推演模型...'
                        : agentStage === 'reasoning'
                        ? '协作环境已就位'
                        : '等待资料就绪'}
                    </div>
                  </div>

                  {/* Stage 3: Reasoning / Generating */}
                  <div className={`p-2.5 rounded-xl border text-xs transition-all ${
                    agentStage === 'reasoning'
                      ? 'bg-blue-100/70 border-blue-400 text-blue-900 shadow-2xs font-medium'
                      : 'bg-slate-50/70 border-slate-200 text-slate-400'
                  }`}>
                    <div className="flex items-center gap-1.5">
                      <span className="truncate">3. 自主推演生成</span>
                    </div>
                    <div className="text-[10px] text-slate-500 mt-1 leading-tight">
                      {agentStage === 'reasoning'
                        ? '基于专业框架推演并输出成果...'
                        : '等待模型就绪'}
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-between text-[11px] text-slate-500 pt-0.5">
                  <span className="text-slate-400">
                    系统推演与生成中
                  </span>
                  <span className="text-slate-400 font-mono text-[10px]">
                    当前阶段: {agentStage === 'context' ? '组装前置资料' : agentStage === 'spawning' ? '加载运行环境' : '自主推演生成中'}
                  </span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* 输入框与操作条（去图标干扰，纯文字清晰层级） */}
          <div className="p-3 border-t border-slate-200 bg-white space-y-2">
            {/* 第一行：按直觉顺序排列的操作步骤切换 */}
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="text-[11px] font-medium text-slate-500">当前动作:</span>
                <button
                  type="button"
                  onClick={() => setMessageType('question')}
                  className={`px-2.5 py-1 rounded-md text-[11px] transition cursor-pointer ${
                    messageType === 'question'
                      ? 'bg-blue-600 text-white font-semibold'
                      : 'bg-slate-100 text-slate-600 hover:text-slate-900'
                  }`}
                >
                  1. 先和负责人聊 (仅左侧对话)
                </button>
                <button
                  type="button"
                  onClick={() => setMessageType('instruction')}
                  className={`px-2.5 py-1 rounded-md text-[11px] transition cursor-pointer ${
                    messageType === 'instruction'
                      ? 'bg-emerald-600 text-white font-semibold'
                      : 'bg-slate-100 text-slate-600 hover:text-slate-900'
                  }`}
                >
                  2.{' '}
                  {moduleState.module_code === '01'
                    ? '汇总生成右侧报告'
                    : moduleState.module_code === '03'
                    ? '生成方向与假设清单'
                    : moduleState.module_code === '04'
                    ? '生成假门网页与方案'
                    : moduleState.module_code === '05'
                    ? '确认立项并生成需求规范'
                    : '生成/重写右侧成果'}
                </button>
                <button
                  type="button"
                  onClick={() => setMessageType('feedback')}
                  className={`px-2.5 py-1 rounded-md text-[11px] transition cursor-pointer ${
                    messageType === 'feedback'
                      ? 'bg-amber-600 text-white font-semibold'
                      : 'bg-slate-100 text-slate-600 hover:text-slate-900'
                  }`}
                >
                  3. 局部修改右侧报告
                </button>
              </div>
            </div>

            {/* 第二行：随当前动作自动切换的纯文字快捷填入胶囊 */}
            {moduleState.module_code === '01' && messageType === 'question' && (
              <div className="flex flex-wrap items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-50 border border-slate-200 text-[11px]">
                <span className="text-slate-500 shrink-0">快捷追问 (点击填入):</span>
                <button
                  type="button"
                  onClick={() =>
                    setInputText('我看到近期这个细分方向/应用下载量和讨论度很热，帮我深扒：这波全球热度是真赚钱还是买量虚火？拆解其在全球 T1 利润区（美加英澳/西欧/日韩）与 T2/T3 流量区的真实含金量与首年可获盘子 (SOM)。')
                  }
                  className="px-2 py-0.5 rounded bg-white hover:bg-blue-50 text-slate-700 hover:text-blue-700 border border-slate-200 transition cursor-pointer"
                >
                  1. 验全球真伪
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setInputText('扒出该赛道头部爆款应用的全球流量密码：它们在 TikTok / Reels / Shorts / Reddit 上最吸量的前 3 秒跨文化视觉钩子 (Visual Hook) 是什么？有哪些高意图、低竞争的全球多语种 ASO 搜索词可以截流？')
                  }
                  className="px-2 py-0.5 rounded bg-white hover:bg-blue-50 text-slate-700 hover:text-blue-700 border border-slate-200 transition cursor-pointer"
                >
                  2. 扒流量钩子与ASO
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setInputText('深挖该赛道全球 Top 5 热门竞品近 3 个月的 App Store / Google Play 1-2 星差评与社媒吐槽：用户骂得最凶的是什么（周扣费陷阱、核心功能缺陷还是本地化拉胯）？')
                  }
                  className="px-2 py-0.5 rounded bg-white hover:bg-blue-50 text-slate-700 hover:text-blue-700 border border-slate-200 transition cursor-pointer"
                >
                  3. 扒1-2星差评
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setInputText('从全球跨区套利 (Geo-Arbitrage) 视角看，该品类是否存在“英语区刚火，但西欧/日韩/中东/拉美尚未饱和”的空白机会？我们进场应该怎么改单点去截胡，全球首发和扩量梯队怎么排？')
                  }
                  className="px-2 py-0.5 rounded bg-white hover:bg-blue-50 text-slate-700 hover:text-blue-700 border border-slate-200 transition cursor-pointer"
                >
                  4. 跨区套利打法
                </button>
              </div>
            )}

            {moduleState.module_code === '01' && messageType === 'instruction' && (
              <div className="flex flex-wrap items-center justify-between gap-2 px-2.5 py-1.5 rounded-lg bg-slate-50 border border-slate-200 text-[11px]">
                <span className="text-slate-600">
                  将把左侧讨论结论或您的指令整理成右侧正式的《全球市场研究报告》。
                </span>
                <button
                  type="button"
                  onClick={() =>
                    setInputText('围绕当前赛道与讨论结论，按双层精简标准生成《全球赛道摸底与立项可行性报告》：置顶30秒拍板摘要卡（干/不干/怎么截胡/全球首发梯队），下方输出全球T1-T3含金量与SOM测算、Top5竞品差评与流量钩子拆解、3类核心画像与单点破局刀法。')
                  }
                  className="px-2.5 py-0.5 rounded bg-white hover:bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium transition cursor-pointer shrink-0"
                >
                  填入标准报告生成指令
                </button>
              </div>
            )}

            {moduleState.module_code === '03' && (
              <div className="flex flex-wrap items-center justify-between gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-50 border border-slate-200 text-[11px] text-slate-700">
                <span>一页纸精益决策：聚焦核心卖点、功能减法与 4 个待验证生死假设 (H1~H4)。</span>
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => {
                      setMessageType('question');
                      setInputText('结合前序市场与商业基线，本产品首版最应该砍掉哪些容易亏钱或拖慢进度的伪需求？');
                    }}
                    className="px-2 py-0.5 rounded bg-white hover:bg-slate-100 text-slate-700 border border-slate-200 transition cursor-pointer"
                  >
                    探讨功能减法
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setMessageType('instruction');
                      setInputText('按精益一页纸标准生成《产品方向决策与精益验证基线决策书》：明确核心UVP、MoSCoW减法边界，并提炼移交工序04验证的4个生死假设(H1~H4)，严禁提前编写代码级Schema与详细PRD。');
                    }}
                    className="px-2 py-0.5 rounded bg-white hover:bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium transition cursor-pointer"
                  >
                    填入生成方向书指令
                  </button>
                </div>
              </div>
            )}

            {moduleState.module_code === '04' && (
              <div className="flex flex-wrap items-center justify-between gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-50 border border-slate-200 text-[11px] text-slate-700">
                <span>真原型实测与立项门禁：生成「移动端 H5 假门原型 index.html + 3条实测脚本 + Go/Pivot/Kill 门禁」。</span>
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => {
                      setMessageType('question');
                      setInputText('如果不花钱投广告，怎么在 Reddit / TikTok 用零成本自然流在 3 天内测出真实用户意愿与放行标准？');
                    }}
                    className="px-2 py-0.5 rounded bg-white hover:bg-slate-100 text-slate-700 border border-slate-200 transition cursor-pointer"
                  >
                    探讨零成本测法
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setMessageType('instruction');
                      setInputText('围绕工序03移交的H1~H4生死假设，在工作区直接生成可交互的移动端H5假门着陆页原型(index.html)，输出精炼的3条实测脚本与获客红线，并在文末设立客观严密的 Go/Pivot/Kill 立项决策门禁。');
                    }}
                    className="px-2 py-0.5 rounded bg-white hover:bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium transition cursor-pointer"
                  >
                    生成假门原型+立项门禁
                  </button>
                </div>
              </div>
            )}

            {moduleState.module_code === '05' && (
              <div className="flex flex-wrap items-center justify-between gap-1.5 px-2.5 py-1.5 rounded-lg bg-indigo-50/70 border border-indigo-200 text-[11px] text-indigo-950">
                <span>产品需求定义：承接工序04立项决议输出工程级施工契约，或承接工序11输出版本迭代 PRD，并响应下游 CR 演进。</span>
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => {
                      setMessageType('instruction');
                      setInputText('承接工序 04 市场验证与立项决议，输出全量 7 大章节工程级 PRD 施工契约（包含：①版本定位与MVP范围封版；②全局信息架构与Mermaid状态机；③逐模块M1~M6功能规格与交互边界；④完整数据字典与接口契约；⑤计费与权限状态机；⑥全链路数据埋点字典；⑦非功能性需求与全量Gherkin验收标准），供设计与研发直接施工。');
                    }}
                    className="px-2 py-0.5 rounded bg-white hover:bg-indigo-50 text-indigo-700 border border-indigo-200 font-medium transition cursor-pointer"
                  >
                    首版 7 大章节 PRD 封版
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setMessageType('instruction');
                      setInputText('承接工序 11 运营数据复盘建议书与 Backlog 需求池，输出版本演进目标、[新增]/[修改]/[废弃] 变更点对照表及增量 PRD 规格说明。');
                    }}
                    className="px-2 py-0.5 rounded bg-white hover:bg-purple-50 text-purple-700 border border-purple-200 font-medium transition cursor-pointer"
                  >
                    版本迭代增量 PRD
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setMessageType('feedback');
                      setInputText('收到来自下游工序的需求变更请求 (CR)：【变更模块】：___；【矛盾说明】：___；【建议调整】：___。请全面评估对整体架构与契约的影响，靶向修订 PRD 相关章节并形成新基线版本。');
                    }}
                    className="px-2 py-0.5 rounded bg-white hover:bg-amber-50 text-amber-800 border border-amber-300 font-medium transition cursor-pointer"
                  >
                    下游 CR 修订 PRD
                  </button>
                </div>
              </div>
            )}

            <form onSubmit={handleSendMessage} className="flex gap-2">
              <input
                type="text"
                placeholder={
                  messageType === 'question'
                    ? moduleState.module_code === '01'
                      ? '直接输入你看到的某款热门应用或趋势想法（或点击上方快捷追问），先与市场负责人探讨...'
                      : '输入你的想法或疑问，先在左侧与负责人探讨（不会覆盖右侧成果）...'
                    : messageType === 'instruction'
                    ? moduleState.module_code === '01'
                      ? '输入报告生成要求（或点击上方【填入标准报告生成指令】），产出右侧正式报告...'
                      : moduleState.module_code === '03'
                      ? '输入方向要求（如：明确核心卖点、砍除伪需求，提炼移交04的4个生死假设）...'
                      : moduleState.module_code === '04'
                      ? '输入验证要求（如：生成可交互 H5 假门落地页 index.html 与 3 条测试脚本）...'
                      : moduleState.module_code === '05'
                      ? '请粘贴工序 04 的真实外测数据（如 CTR、转化率、用户反馈），或点击上方【填入实测数据模板】...'
                      : '输入任务指令，让 AI 智能体在右侧生成正式成果...'
                    : '输入对右侧现有报告的具体修改意见（如：补充日本市场的定价策略）...'
                }
                value={inputText}
                onChange={e => setInputText(e.target.value)}
                className="flex-1 bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 placeholder-slate-400 focus:bg-white focus:outline-none focus:border-blue-500"
              />
              <button
                type="submit"
                disabled={sending || !inputText.trim()}
                className={`px-4 py-2 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition flex items-center gap-1.5 cursor-pointer shrink-0 ${
                  messageType === 'question'
                    ? 'bg-blue-600 hover:bg-blue-500'
                    : messageType === 'feedback'
                    ? 'bg-amber-600 hover:bg-amber-500'
                    : 'bg-emerald-600 hover:bg-emerald-500'
                }`}
              >
                {sending
                  ? '处理中...'
                  : messageType === 'question'
                  ? '发送探讨'
                  : messageType === 'feedback'
                  ? '提交修改'
                  : '生成报告'}
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
              <span className="text-xs font-semibold text-slate-800">成果交付库 (Artifacts)</span>
              {panelLayout === 'full' && (
                <span className="text-[10px] text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded-full border border-indigo-200 font-medium">
                  全宽沉浸模式
                </span>
              )}
            </div>

            <div className="flex items-center gap-2">
              {/* 布局切换下拉菜单 (1:1 / 1:2 / 全屏) */}
              <div className="relative" ref={layoutDropdownRef}>
                <button
                  type="button"
                  onClick={() => setIsLayoutDropdownOpen(!isLayoutDropdownOpen)}
                  className="px-2.5 py-1 rounded-lg text-[11px] font-medium bg-white hover:bg-slate-100 text-slate-700 border border-slate-200 shadow-2xs flex items-center gap-1.5 cursor-pointer transition"
                  title="切换分栏比例与视口模式 (1:1 / 1:2 / 全屏)"
                >
                  {panelLayout === 'full' ? (
                    <Maximize2 className="w-3.5 h-3.5 text-indigo-600" />
                  ) : (
                    <Columns2 className="w-3.5 h-3.5 text-slate-500" />
                  )}
                  <span className="font-medium text-slate-700">
                    {panelLayout === 'equal' && '1:1'}
                    {panelLayout === 'wide' && '1:2'}
                    {panelLayout === 'full' && '全屏'}
                  </span>
                  <ChevronDown className={`w-3 h-3 text-slate-400 transition-transform duration-150 ${isLayoutDropdownOpen ? 'rotate-180' : ''}`} />
                </button>

                {isLayoutDropdownOpen && (
                  <div className="absolute right-0 mt-1.5 w-36 bg-white border border-slate-200 rounded-lg shadow-lg py-1 z-30 text-[11px] divide-y divide-slate-100 animate-in fade-in duration-100">
                    <div className="py-0.5">
                      <button
                        type="button"
                        onClick={() => {
                          setPanelLayout('equal');
                          setIsLayoutDropdownOpen(false);
                        }}
                        className={`w-full px-3 py-1.5 text-left flex items-center justify-between cursor-pointer hover:bg-slate-50 transition ${
                          panelLayout === 'equal' ? 'text-indigo-600 font-semibold bg-indigo-50/50' : 'text-slate-700'
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <Columns2 className="w-3.5 h-3.5 text-slate-400" />
                          <span>1:1 (双栏平衡)</span>
                        </div>
                        {panelLayout === 'equal' && <Check className="w-3.5 h-3.5 text-indigo-600" />}
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setPanelLayout('wide');
                          setIsLayoutDropdownOpen(false);
                        }}
                        className={`w-full px-3 py-1.5 text-left flex items-center justify-between cursor-pointer hover:bg-slate-50 transition ${
                          panelLayout === 'wide' ? 'text-indigo-600 font-semibold bg-indigo-50/50' : 'text-slate-700'
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <Columns2 className="w-3.5 h-3.5 text-slate-400" />
                          <span>1:2 (成果加宽)</span>
                        </div>
                        {panelLayout === 'wide' && <Check className="w-3.5 h-3.5 text-indigo-600" />}
                      </button>
                    </div>
                    <div className="py-0.5">
                      <button
                        type="button"
                        onClick={() => {
                          setPanelLayout('full');
                          setIsLayoutDropdownOpen(false);
                        }}
                        className={`w-full px-3 py-1.5 text-left flex items-center justify-between cursor-pointer hover:bg-slate-50 transition ${
                          panelLayout === 'full' ? 'text-indigo-600 font-semibold bg-indigo-50/50' : 'text-slate-700'
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <Maximize2 className="w-3.5 h-3.5 text-slate-400" />
                          <span>全屏 (沉浸模式)</span>
                        </div>
                        {panelLayout === 'full' && <Check className="w-3.5 h-3.5 text-indigo-600" />}
                      </button>
                    </div>
                  </div>
                )}
              </div>

              <button
                type="button"
                onClick={() => setIsUploadModalOpen(true)}
                className="px-2.5 py-1 rounded-lg text-[11px] font-medium bg-white hover:bg-slate-100 text-slate-700 border border-slate-200 shadow-2xs flex items-center gap-1 cursor-pointer transition"
                title="上传外部成果文件 (HTML 交互原型包或 Markdown 规范文档)"
              >
                <UploadCloud className="w-3.5 h-3.5 text-blue-600" />
                上传成果 (HTML/文档)
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
                        v{a.version} {a.is_baseline ? '(定稿基准)' : ''} {a.artifact_type === 'html_bundle' ? '[原型包]' : ''} - {new Date(a.created_at).toLocaleTimeString()}
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
                  方案文档与源码
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
                <div className="flex-1 bg-slate-100/80 p-2.5 flex items-center justify-center overflow-auto min-h-[720px]">
                  <div
                    className={`h-[calc(100vh-210px)] min-h-[700px] bg-white rounded-xl shadow-md border border-slate-300 overflow-hidden transition-all duration-300 flex flex-col ${
                      prototypeViewport === 'mobile'
                        ? 'w-[393px]'
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
                              当前工序正式定稿基准 (Baseline)
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
                          <span className="flex items-center gap-1" title="防篡改唯一数字指纹">
                            <Hash className="w-3 h-3 text-slate-400" />
                            版本指纹: {selectedArtifact.content_hash.slice(0, 12)}...
                          </span>
                        </div>
                      </div>

                      {/* 快捷操作区：双层阅读视图切换、复制全文与下载 */}
                      <div className="flex items-center gap-2 flex-wrap">
                        {splitArtifactLayers(selectedArtifact.content).hasSecondLayer && (
                          <div className="flex items-center bg-slate-100 p-0.5 rounded-lg border border-slate-200">
                            <button
                              type="button"
                              onClick={() => setReadingLayer('executive')}
                              className={`px-2.5 py-1 rounded-md text-xs font-medium transition cursor-pointer ${
                                readingLayer === 'executive'
                                  ? 'bg-indigo-600 text-white shadow-2xs'
                                  : 'text-slate-600 hover:text-slate-900'
                              }`}
                              title="仅展示负责人拍板所需的核心量化结论与决策开关"
                            >
                              30秒拍板视图
                            </button>
                            <button
                              type="button"
                              onClick={() => setReadingLayer('full')}
                              className={`px-2.5 py-1 rounded-md text-xs font-medium transition cursor-pointer ${
                                readingLayer === 'full'
                                  ? 'bg-slate-800 text-white shadow-2xs'
                                  : 'text-slate-600 hover:text-slate-900'
                              }`}
                              title="展开包含供下游 AI 读取的完整执行与传参细节"
                            >
                              完整执行细节
                            </button>
                          </div>
                        )}

                        <button
                          type="button"
                          onClick={handleCopyArtifact}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 shadow-2xs transition cursor-pointer"
                          title="复制 Markdown 源码全文"
                        >
                          {copiedArtifact ? (
                            <span className="text-emerald-700">已复制全文</span>
                          ) : (
                            <span>复制全文</span>
                          )}
                        </button>

                        <button
                          type="button"
                          onClick={handleDownloadArtifact}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 shadow-2xs transition cursor-pointer"
                          title="下载为 Markdown 文件 (.md)"
                        >
                          <span>下载 .md</span>
                        </button>
                      </div>
                    </div>

                    {/* 版本变更说明 */}
                    {selectedArtifact.change_summary && (
                      <div className="bg-blue-50/80 border border-blue-200 rounded-xl p-3.5 text-xs text-blue-900 mb-6 shadow-2xs">
                        <div className="font-semibold text-blue-900 mb-1">
                          本版本关键变更说明：
                        </div>
                        <p className="text-blue-800 leading-relaxed">
                          {selectedArtifact.change_summary}
                        </p>
                      </div>
                    )}

                    {/* 文档排版正文（支持双层决策/执行分层渲染） */}
                    {(() => {
                      const layerInfo = splitArtifactLayers(selectedArtifact.content);
                      const showShortOnly = layerInfo.hasSecondLayer && readingLayer === 'executive';
                      return (
                        <div className="flex-1">
                          <MarkdownViewer
                            content={showShortOnly ? layerInfo.executiveContent : selectedArtifact.content.replace('<!-- EXECUTIVE_GATE_END -->', '')}
                            variant="artifact"
                          />
                          {showShortOnly && (
                            <div className="mt-6 p-4 rounded-xl bg-slate-50 border border-slate-200/90 flex items-center justify-between flex-wrap gap-3">
                              <div className="text-xs text-slate-600">
                                <span className="font-semibold text-slate-800">第二层（执行与传参层）已折叠</span>
                                <span className="ml-2 text-slate-500">
                                  已隐藏 {layerInfo.hiddenChars.toLocaleString()} 字底层推导与供下游 AI 读取的参数细节，让您专注核心拍板。
                                </span>
                              </div>
                              <button
                                type="button"
                                onClick={() => setReadingLayer('full')}
                                className="px-3 py-1.5 rounded-lg text-xs font-medium bg-white hover:bg-slate-100 text-indigo-700 border border-indigo-200 shadow-2xs transition cursor-pointer"
                              >
                                展开完整执行层细节
                              </button>
                            </div>
                          )}
                        </div>
                      );
                    })()}
                  </div>
                </div>
              )
            ) : (
              <div className="text-center py-24 text-slate-400 text-xs flex-1 flex flex-col items-center justify-center">
                当前暂无成果交付物。<br />可在左侧输入需求让 AI 智能体生成，或点击上方【上传新版本】提交原型与文档。
              </div>
            )}
          </div>

          {/* 底部关联的 Issue 状态预览 */}
          <div className="px-4 py-2.5 border-t border-slate-200 bg-slate-50/60 flex items-center justify-between text-xs text-slate-500">
            <span>
              关联协同问题: {openIssues.length} 个待解决
            </span>
            <span className="text-[11px] text-slate-400 font-medium">版本安全归档防篡改</span>
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
                上传工序成果包 (HTML 原型 / 规范文档)
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
                  支持包含 <code>index.html</code>、<code>assets/</code> 等目录的 ZIP 交互原型包，系统将自动解压并提供可交互原型预览。
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
                  本次修改主要内容说明 *
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
                💡 上传后系统将自动生成成果变更审批单，经审批通过后正式生效为定稿基准，并通知下游工序跟进。
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
                  {selectedReview.status === 'approved' ? '已通过' : selectedReview.status === 'rejected' ? '已退回' : '待审批'}
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
                    <strong>退回原因:</strong> {selectedReview.rejection_reason}
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
                    若退回请输入修改建议 (可选):
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
                    退回修改
                  </button>
                  <button
                    type="button"
                    onClick={() => handleApproveReview(selectedReview.id)}
                    className="px-5 py-2 rounded-xl text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white shadow-xs transition cursor-pointer flex items-center gap-1.5"
                  >
                    <CheckCheck className="w-4 h-4" />
                    批准并生效为定稿基准 (Baseline)
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
                <div>上游最新已定稿基准：<strong>v{selectedStaleDetail.latest_upstream_version}</strong></div>
                <div className="pt-1 text-amber-800">{selectedStaleDetail.message}</div>
              </div>

              <div className="bg-slate-50 border border-slate-200 p-3 rounded-xl text-slate-700 text-xs">
                <p>
                  上游工序负责人已完成新版本交付并经统一审批通过。若业务或产研团队已查阅最新上游成果，请点击下方【确认已完成跟进与对齐】，工序状态将恢复为最新对齐。
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

      {/* 一页纸关口申请单与审批弹窗 */}
      <GateApplicationModal
        isOpen={isGateModalOpen}
        moduleId={moduleState.id}
        moduleCode={moduleState.module_code}
        moduleName={moduleState.name}
        onClose={() => setIsGateModalOpen(false)}
        onApproved={() => {
          loadSessionAndArtifacts();
          onModuleUpdated();
        }}
      />
    </div>
  );
};
