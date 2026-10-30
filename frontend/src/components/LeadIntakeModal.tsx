import React, { useState, useEffect, useRef } from 'react';
import {
  Compass,
  X,
  Bot,
  Sparkles,
  Send,
  ShieldAlert,
  CheckCircle2,
  TrendingUp,
  AlertTriangle,
  Flame,
  ArrowRight,
  Layers,
  DollarSign
} from 'lucide-react';
import { api } from '../services/api';
import { StrategicInitiative, IntakeProposal } from '../types';

interface LeadIntakeModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated: (initiative: StrategicInitiative) => void;
}

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

export const LeadIntakeModal: React.FC<LeadIntakeModalProps> = ({
  isOpen,
  onClose,
  onCreated
}) => {
  const [activeTab, setActiveTab] = useState<'intake' | 'manual'>('intake');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoadingChat, setIsLoadingChat] = useState(false);
  const [quickPrompts, setQuickPrompts] = useState<string[]>([]);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  // Proposal Draft State (editable by CEO)
  const [proposal, setProposal] = useState<IntakeProposal>({
    name: '',
    description: '',
    strategic_intent: '',
    target_market: '',
    business_model_hypothesis: '',
    budget: 15000,
    suggested_budget: 15000,
    hard_stop_loss: 20000,
    currency: 'USD',
    signals: [],
    unverified_assumptions: [],
    kill_criteria: [],
    stage_allocations: {}
  });

  // Manual form states
  const [manualName, setManualName] = useState('');
  const [manualDesc, setManualDesc] = useState('');
  const [manualOwner, setManualOwner] = useState('负责人');
  const [manualBudget, setManualBudget] = useState(10000);
  const [manualIntent, setManualIntent] = useState('');
  const [manualMarket, setManualMarket] = useState('');
  const [manualHypothesis, setManualHypothesis] = useState('');

  // Initial welcome on open
  useEffect(() => {
    if (isOpen) {
      initIntakeSession();
    }
  }, [isOpen]);

  const initIntakeSession = async () => {
    setIsLoadingChat(true);
    try {
      const res = await api.leadIntakeChat([]);
      setMessages([
        {
          id: 'welcome-1',
          role: 'assistant',
          content: res.reply
        }
      ]);
      setQuickPrompts(res.quick_prompts || []);
      if (res.proposal && Object.keys(res.proposal).length > 0) {
        setProposal(prev => ({ ...prev, ...res.proposal }));
      }
    } catch (e: any) {
      console.error('Failed to init lead intake:', e);
      setMessages([
        {
          id: 'err-1',
          role: 'assistant',
          content: 'CEO 您好！我是项目总控智能体 Lead。请告诉我您的出海方向或赛道构想，我将为您进行立项推演与假设审计。'
        }
      ]);
    } finally {
      setIsLoadingChat(false);
    }
  };

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoadingChat]);

  if (!isOpen) return null;

  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend || inputText).trim();
    if (!text || isLoadingChat) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text
    };

    const nextMessages = [...messages, userMsg];
    setMessages(nextMessages);
    setInputText('');
    setIsLoadingChat(true);

    try {
      const apiMessages = nextMessages.map(m => ({ role: m.role, content: m.content }));
      const res = await api.leadIntakeChat(apiMessages, proposal);

      setMessages(prev => [
        ...prev,
        {
          id: `lead-${Date.now()}`,
          role: 'assistant',
          content: res.reply
        }
      ]);

      if (res.quick_prompts && res.quick_prompts.length > 0) {
        setQuickPrompts(res.quick_prompts);
      }

      if (res.proposal && Object.keys(res.proposal).length > 0) {
        setProposal(prev => ({
          ...prev,
          ...res.proposal,
          budget: res.proposal.budget || res.proposal.suggested_budget || prev.budget
        }));
      }
    } catch (err: any) {
      setMessages(prev => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: 'assistant',
          content: `推演交互异常: ${err.message || '未知错误'}`
        }
      ]);
    } finally {
      setIsLoadingChat(false);
    }
  };

  // Adopt Lead Proposal and Create Initiative
  const handleAdoptAndCreate = async () => {
    if (!proposal.name.trim()) {
      alert('请先输入或由 Lead 生成战略工程名称');
      return;
    }
    setIsSubmitting(true);
    try {
      const payload: Partial<StrategicInitiative> = {
        name: proposal.name.trim(),
        description: proposal.description?.trim() || proposal.strategic_intent?.trim() || '',
        owner: 'CEO',
        budget: Number(proposal.budget) || 15000,
        status: 'validating',
        strategic_intent: proposal.strategic_intent?.trim() || undefined,
        target_market: proposal.target_market?.trim() || undefined,
        business_model_hypothesis: proposal.business_model_hypothesis?.trim() || undefined,
        initiative_rationale: {
          signals: proposal.signals || [],
          unverified_assumptions: proposal.unverified_assumptions || [],
          kill_criteria: proposal.kill_criteria || [],
          stage_allocations: proposal.stage_allocations || {},
          suggested_budget: proposal.suggested_budget,
          hard_stop_loss: proposal.hard_stop_loss,
          lead_recommendation: 'approved_by_lead_intake',
          intake_dialogue_summary: messages.map(m => `[${m.role}] ${m.content}`).join('\n')
        }
      };

      const created = await api.createInitiative(payload);
      onCreated(created);
      onClose();
    } catch (e: any) {
      alert(`创建战略工程失败: ${e.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Manual Form Submit
  const handleManualCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualName.trim()) return;
    setIsSubmitting(true);
    try {
      const created = await api.createInitiative({
        name: manualName.trim(),
        description: manualDesc.trim() || undefined,
        owner: manualOwner.trim() || '负责人',
        budget: Number(manualBudget) || 0,
        status: 'validating',
        strategic_intent: manualIntent.trim() || undefined,
        target_market: manualMarket.trim() || undefined,
        business_model_hypothesis: manualHypothesis.trim() || undefined
      });
      onCreated(created);
      onClose();
    } catch (e: any) {
      alert(`创建战略工程失败: ${e.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-3 md:p-6 animate-in fade-in duration-200">
      <div className="bg-white border border-slate-200 w-full max-w-6xl rounded-2xl shadow-2xl flex flex-col max-h-[92vh] overflow-hidden">
        {/* Top Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-sm text-white">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-semibold text-slate-900 text-base">
                  新建顶层战略工程 (Strategic Initiative)
                </h3>
                <span className="px-2 py-0.5 text-[10px] font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200 rounded-full">
                  Lead Agent 立项前置模式
                </span>
              </div>
              <p className="text-xs text-slate-500">
                五元架构首步：由用户掌控战略方向，Lead Agent 协助推演竞品软肋、审查假设并规划授权包
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Tab switch */}
            <div className="bg-slate-200/80 p-0.5 rounded-lg flex text-xs">
              <button
                type="button"
                onClick={() => setActiveTab('intake')}
                className={`px-3 py-1.5 rounded-md font-medium transition-colors flex items-center gap-1.5 cursor-pointer ${
                  activeTab === 'intake'
                    ? 'bg-white text-indigo-700 shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
                Lead Agent 智能立项推演
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('manual')}
                className={`px-3 py-1.5 rounded-md font-medium transition-colors flex items-center gap-1.5 cursor-pointer ${
                  activeTab === 'manual'
                    ? 'bg-white text-slate-800 shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <Compass className="w-3.5 h-3.5 text-slate-500" />
                常规手动填报
              </button>
            </div>

            <button
              onClick={onClose}
              className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content Body */}
        {activeTab === 'intake' ? (
          <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 overflow-hidden">
            {/* Left Column: Lead Agent Interaction Stream (7 cols) */}
            <div className="lg:col-span-7 flex flex-col border-r border-slate-100 bg-white overflow-hidden">
              {/* Agent Status Bar */}
              <div className="px-5 py-2.5 bg-indigo-50/50 border-b border-indigo-100/60 flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  <span className="font-semibold text-indigo-950">项目总控智能体 · Lead</span>
                  <span className="text-slate-400">|</span>
                  <span className="text-slate-600 text-[11px]">立项前置参谋与红队假设审计</span>
                </div>
                <div className="flex items-center gap-1 text-[11px] text-amber-700 font-medium bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                  <ShieldAlert className="w-3.5 h-3.5 text-amber-600" />
                  严禁虚构数据 · 信号须有据可查
                </div>
              </div>

              {/* Chat Message History */}
              <div className="flex-1 overflow-y-auto p-5 space-y-4 text-xs">
                {messages.map(msg => (
                  <div
                    key={msg.id}
                    className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    {msg.role === 'assistant' && (
                      <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white shrink-0 shadow-xs">
                        <Bot className="w-4 h-4" />
                      </div>
                    )}

                    <div
                      className={`max-w-[85%] rounded-2xl px-4 py-3 shadow-xs leading-relaxed whitespace-pre-wrap ${
                        msg.role === 'user'
                          ? 'bg-indigo-600 text-white rounded-br-xs'
                          : 'bg-slate-50 border border-slate-200/80 text-slate-800 rounded-bl-xs'
                      }`}
                    >
                      {msg.content}
                    </div>
                  </div>
                ))}

                {isLoadingChat && (
                  <div className="flex gap-3 justify-start">
                    <div className="w-7 h-7 rounded-lg bg-indigo-500 flex items-center justify-center text-white shrink-0 animate-pulse">
                      <Bot className="w-4 h-4" />
                    </div>
                    <div className="bg-slate-50 border border-slate-200 rounded-2xl px-4 py-3 text-slate-500 text-xs flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-bounce" />
                      <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-bounce [animation-delay:0.2s]" />
                      <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-bounce [animation-delay:0.4s]" />
                      <span>Lead 正在推演市场信号、测算阶段预算并审计假设...</span>
                    </div>
                  </div>
                )}
                <div ref={chatBottomRef} />
              </div>

              {/* Quick Prompts */}
              {quickPrompts.length > 0 && (
                <div className="px-5 py-2 bg-slate-50/70 border-t border-slate-100 flex flex-wrap gap-1.5 items-center">
                  <span className="text-[11px] text-slate-400 font-medium flex items-center gap-1">
                    <Flame className="w-3 h-3 text-amber-500" />
                    典型出海赛道灵感:
                  </span>
                  {quickPrompts.slice(0, 4).map((qp, idx) => (
                    <button
                      key={idx}
                      type="button"
                      disabled={isLoadingChat}
                      onClick={() => handleSendMessage(qp)}
                      className="px-2.5 py-1 rounded-md bg-white border border-slate-200 text-[11px] text-slate-700 hover:text-indigo-600 hover:border-indigo-300 transition-colors shadow-2xs truncate max-w-[280px] cursor-pointer"
                    >
                      {qp}
                    </button>
                  ))}
                </div>
              )}

              {/* Chat Input Bar */}
              <div className="p-4 bg-white border-t border-slate-100">
                <form
                  onSubmit={e => {
                    e.preventDefault();
                    handleSendMessage();
                  }}
                  className="flex gap-2"
                >
                  <input
                    type="text"
                    value={inputText}
                    disabled={isLoadingChat}
                    onChange={e => setInputText(e.target.value)}
                    placeholder="输入您的战略方向构想（例如：我想在北美做一款买断制极简专注番茄钟，预算控制在 15,000 美元内）..."
                    className="flex-1 bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5 text-xs text-slate-800 placeholder-slate-400 focus:bg-white focus:outline-none focus:border-indigo-500 transition-all"
                  />
                  <button
                    type="submit"
                    disabled={!inputText.trim() || isLoadingChat}
                    className="px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer shadow-xs shrink-0"
                  >
                    <Send className="w-3.5 h-3.5" />
                    推演
                  </button>
                </form>
              </div>
            </div>

            {/* Right Column: Live Strategic Initiative Proposal Draft (5 cols) */}
            <div className="lg:col-span-5 flex flex-col bg-slate-50/70 overflow-hidden">
              <div className="px-5 py-3 border-b border-slate-200/80 bg-white flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Layers className="w-4 h-4 text-emerald-600" />
                  <h4 className="font-semibold text-slate-900 text-xs">
                    战略提案与授权包建议草案
                  </h4>
                </div>
                <span className="text-[10px] text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded font-mono font-medium border border-emerald-200">
                  实时联动推演 · CEO 可直改
                </span>
              </div>

              {/* Proposal Fields */}
              <div className="flex-1 overflow-y-auto p-5 space-y-3.5 text-xs">
                {/* Initiative Name */}
                <div className="bg-white p-3 rounded-xl border border-slate-200 shadow-2xs">
                  <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                    战略工程名称 *
                  </label>
                  <input
                    type="text"
                    value={proposal.name}
                    onChange={e => setProposal(p => ({ ...p, name: e.target.value }))}
                    placeholder="例如：北美离线极简专注与数字排毒应用矩阵"
                    className="w-full bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs text-slate-900 font-medium focus:bg-white focus:outline-none focus:border-indigo-500"
                  />
                </div>

                {/* Strategic Intent */}
                <div className="bg-white p-3 rounded-xl border border-slate-200 shadow-2xs">
                  <label className="block text-[11px] font-semibold text-slate-700 mb-1 flex items-center justify-between">
                    <span>战略定性 (Strategic Intent)</span>
                    <span className="text-[10px] text-slate-400 font-normal">核心价值切口</span>
                  </label>
                  <textarea
                    rows={2}
                    value={proposal.strategic_intent}
                    onChange={e => setProposal(p => ({ ...p, strategic_intent: e.target.value }))}
                    placeholder="以纯本地离线隐私+极简沉浸为切入点，抢占北美专注场景..."
                    className="w-full bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs text-slate-900 focus:bg-white focus:outline-none focus:border-indigo-500"
                  />
                </div>

                {/* Target Market */}
                <div className="bg-white p-3 rounded-xl border border-slate-200 shadow-2xs">
                  <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                    目标细分战区 (Target Market)
                  </label>
                  <input
                    type="text"
                    value={proposal.target_market}
                    onChange={e => setProposal(p => ({ ...p, target_market: e.target.value }))}
                    placeholder="北美 (US/CA) 18-28 岁大学生与远程知识工作者"
                    className="w-full bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs text-slate-900 focus:bg-white focus:outline-none focus:border-indigo-500"
                  />
                </div>

                {/* Business Model Hypothesis */}
                <div className="bg-white p-3 rounded-xl border border-slate-200 shadow-2xs">
                  <label className="block text-[11px] font-semibold text-slate-700 mb-1 flex items-center justify-between">
                    <span>商业模式构想 (Hypothesis)</span>
                    <span className="text-[10px] text-indigo-600 font-normal">工序 02 严格守门</span>
                  </label>
                  <textarea
                    rows={2}
                    value={proposal.business_model_hypothesis}
                    onChange={e => setProposal(p => ({ ...p, business_model_hypothesis: e.target.value }))}
                    placeholder="免费基础计时器 + $14.99 终身买断，LTV/CAC ≥ 3.5x..."
                    className="w-full bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs text-slate-900 focus:bg-white focus:outline-none focus:border-indigo-500"
                  />
                </div>

                {/* Budget & Stop Loss */}
                <div className="bg-white p-3 rounded-xl border border-slate-200 shadow-2xs grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-700 mb-1 flex items-center gap-1">
                      <DollarSign className="w-3.5 h-3.5 text-emerald-600" />
                      建议总预算 ({proposal.currency || 'USD'})
                    </label>
                    <input
                      type="number"
                      min="0"
                      value={proposal.budget}
                      onChange={e => setProposal(p => ({ ...p, budget: Number(e.target.value) }))}
                      className="w-full bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs text-slate-900 font-bold focus:bg-white focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-700 mb-1 flex items-center gap-1">
                      <ShieldAlert className="w-3.5 h-3.5 text-rose-500" />
                      硬止损熔断线 ({proposal.currency || 'USD'})
                    </label>
                    <input
                      type="number"
                      min="0"
                      value={proposal.hard_stop_loss || proposal.budget * 1.3}
                      onChange={e => setProposal(p => ({ ...p, hard_stop_loss: Number(e.target.value) }))}
                      className="w-full bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs text-rose-600 font-bold focus:bg-white focus:outline-none focus:border-rose-400"
                    />
                  </div>
                </div>

                {/* Observed Signals & Unverified Assumptions */}
                <div className="bg-white p-3 rounded-xl border border-slate-200 shadow-2xs space-y-2.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold text-slate-700 uppercase tracking-wider">
                      证据与假设隔离层 (Evidence vs Assumptions)
                    </span>
                  </div>

                  {/* Signals */}
                  {proposal.signals && proposal.signals.length > 0 && (
                    <div className="space-y-1">
                      <span className="text-[10px] font-medium text-emerald-700 flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                        已观测真实信号 (可信依据)
                      </span>
                      {proposal.signals.slice(0, 2).map((sig, idx) => (
                        <div key={idx} className="bg-emerald-50/60 p-2 rounded-lg text-[11px] text-emerald-900 border border-emerald-100">
                          {sig.claim}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Assumptions */}
                  {proposal.unverified_assumptions && proposal.unverified_assumptions.length > 0 && (
                    <div className="space-y-1 pt-1">
                      <span className="text-[10px] font-medium text-amber-700 flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3 text-amber-600" />
                        待后续工序验证的假设 (禁止作为事实)
                      </span>
                      {proposal.unverified_assumptions.slice(0, 2).map((unv, idx) => (
                        <div key={idx} className="bg-amber-50/60 p-2 rounded-lg text-[11px] text-amber-900 border border-amber-100">
                          [{unv.validation_stage || '工序 04'}] {unv.claim}
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Kill Criteria */}
                {proposal.kill_criteria && proposal.kill_criteria.length > 0 && (
                  <div className="bg-rose-50/50 p-3 rounded-xl border border-rose-100 text-[11px] space-y-1">
                    <span className="font-bold text-rose-800 flex items-center gap-1">
                      <ShieldAlert className="w-3.5 h-3.5 text-rose-600" />
                      红队关口退出条件 (Kill Criteria)
                    </span>
                    <ul className="list-disc list-inside text-rose-700 space-y-0.5">
                      {proposal.kill_criteria.slice(0, 2).map((kc, idx) => (
                        <li key={idx} className="truncate">{kc}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              {/* Action Bottom Bar */}
              <div className="p-4 bg-white border-t border-slate-200/80 flex flex-col gap-2">
                <button
                  type="button"
                  disabled={!proposal.name.trim() || isSubmitting}
                  onClick={handleAdoptAndCreate}
                  className="w-full py-2.5 px-4 rounded-xl font-medium text-xs text-white bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 disabled:opacity-50 shadow-md hover:shadow-lg transition-all flex items-center justify-center gap-2 cursor-pointer"
                >
                  <Sparkles className="w-4 h-4 text-emerald-100" />
                  {isSubmitting ? '正在立项并初始化工作区...' : '🚀 采纳 Lead 提案并正式创建战略工程'}
                  <ArrowRight className="w-4 h-4 text-emerald-100" />
                </button>
                <p className="text-[10px] text-slate-400 text-center leading-tight">
                  三层治理架构法则：Lead Agent 仅负责起草与推演，战略工程立项与授权包签署终审权唯一归属于人类战略层。
                </p>
              </div>
            </div>
          </div>
        ) : (
          /* Manual Form Tab */
          <div className="flex-1 overflow-y-auto p-6 max-w-2xl mx-auto w-full">
            <div className="p-3 mb-4 bg-indigo-50/60 rounded-xl border border-indigo-100 flex items-center justify-between text-xs text-indigo-900">
              <div className="flex items-center gap-2">
                <Bot className="w-4 h-4 text-indigo-600" />
                <span>不确定如何设定出海预算与退出条件？</span>
              </div>
              <button
                type="button"
                onClick={() => setActiveTab('intake')}
                className="text-xs font-semibold text-indigo-600 hover:underline cursor-pointer"
              >
                切换至 Lead Agent 智能立项 →
              </button>
            </div>

            <form onSubmit={handleManualCreate} className="space-y-4 text-xs">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">战略工程名称 *</label>
                <input
                  type="text"
                  required
                  placeholder="例：北美跨境电商独立站矩阵战略"
                  value={manualName}
                  onChange={e => setManualName(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 focus:bg-white focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">战略目标描述</label>
                <textarea
                  rows={2}
                  placeholder="例：2026 年度拓展北美服装及家居品类出海，建立品牌站点与配套 AI 客服系统。"
                  value={manualDesc}
                  onChange={e => setManualDesc(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 focus:bg-white focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">责任人</label>
                  <input
                    type="text"
                    value={manualOwner}
                    onChange={e => setManualOwner(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 focus:bg-white focus:outline-none focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">战略预算 (元 / USD)</label>
                  <input
                    type="number"
                    min="0"
                    value={manualBudget}
                    onChange={e => setManualBudget(Number(e.target.value))}
                    className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 focus:bg-white focus:outline-none focus:border-emerald-500"
                  />
                </div>
              </div>

              <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 space-y-3">
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider block font-mono">
                  战略底稿设定 (可选，后续可在驾驶舱随时补充)
                </span>
                <div>
                  <label className="block text-[11px] font-medium text-slate-600 mb-1">战略定性 (Strategic Intent)</label>
                  <input
                    type="text"
                    placeholder="例：以独立站高频单品切入，构建私域用户池与变现闭环"
                    value={manualIntent}
                    onChange={e => setManualIntent(e.target.value)}
                    className="w-full bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-xs text-slate-900 focus:outline-none focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-medium text-slate-600 mb-1">目标市场 (Target Market)</label>
                  <input
                    type="text"
                    placeholder="例：北美千禧一代与 Z 世代高性价比快消及生活方式群体"
                    value={manualMarket}
                    onChange={e => setManualMarket(e.target.value)}
                    className="w-full bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-xs text-slate-900 focus:outline-none focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-medium text-slate-600 mb-1">商业模式假设 (Business Model Hypothesis)</label>
                  <input
                    type="text"
                    placeholder="例：首单 CAC ≤ $20，复购率 ≥ 30%，综合 LTV/CAC ≥ 3.0x"
                    value={manualHypothesis}
                    onChange={e => setManualHypothesis(e.target.value)}
                    className="w-full bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-xs text-slate-900 focus:outline-none focus:border-emerald-500"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-3.5 py-1.5 rounded-lg text-xs text-slate-600 hover:bg-slate-100 cursor-pointer"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-1.5 rounded-lg text-xs font-medium bg-emerald-600 hover:bg-emerald-500 text-white cursor-pointer shadow-xs disabled:opacity-50"
                >
                  {isSubmitting ? '创建中...' : '确认创建战略工程'}
                </button>
              </div>
            </form>
          </div>
        )}
      </div>
    </div>
  );
};
