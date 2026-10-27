import React, { useState, useEffect } from 'react';
import { HotfixTasksStatus, HotfixFollowupTask } from '../../types';
import { api } from '../../services/api';
import {
  ShieldAlert,
  Clock,
  CheckCircle2,
  AlertTriangle,
  FileText,
  Loader2,
  FileCheck2,
  AlertCircle
} from 'lucide-react';

interface HotfixSlaCardProps {
  runId: string;
  onTaskCompleted?: () => void;
}

export const HotfixSlaCard: React.FC<HotfixSlaCardProps> = ({ runId, onTaskCompleted }) => {
  const [status, setStatus] = useState<HotfixTasksStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [completingId, setCompletingId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (runId) {
      loadHotfixStatus();
    }
  }, [runId]);

  const loadHotfixStatus = async () => {
    try {
      setLoading(true);
      setErrorMsg(null);
      const data = await api.getHotfixTasks(runId);
      setStatus(data);
    } catch (err: any) {
      console.error('Failed to load hotfix tasks:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCompleteTask = async (taskId: string) => {
    const notes = prompt('请输入该任务的完成说明或文档链接：', '已补齐文档并通过审核闭环');
    if (notes === null) return;

    try {
      setCompletingId(taskId);
      setErrorMsg(null);
      await api.completeHotfixTask(taskId, notes);
      await loadHotfixStatus();
      if (onTaskCompleted) {
        onTaskCompleted();
      }
    } catch (err: any) {
      setErrorMsg(err.message || '标记完成失败');
    } finally {
      setCompletingId(null);
    }
  };

  if (loading || !status || status.tasks.length === 0) {
    return null;
  }

  const isBreached = status.is_breached;
  const allDone = status.all_completed;

  const getTaskHumanName = (type: string, defaultTitle: string) => {
    switch (type) {
      case 'cr_patch':
        return '1. 补齐需求变更单 (CR)';
      case 'postmortem':
        return '2. 编写事故复盘报告';
      case 'prd_update':
        return '3. 同步更新产品需求文档 (PRD)';
      default:
        return defaultTitle;
    }
  };

  return (
    <div
      className={`border rounded-2xl p-5 shadow-xs transition-all space-y-3 ${
        isBreached
          ? 'bg-rose-50 border-rose-300'
          : allDone
          ? 'bg-emerald-50/70 border-emerald-300'
          : 'bg-amber-50/70 border-amber-300'
      }`}
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-black/5 pb-2.5">
        <div className="flex items-center gap-2.5">
          {isBreached ? (
            <ShieldAlert className="w-5 h-5 text-rose-600 animate-pulse" />
          ) : allDone ? (
            <CheckCircle2 className="w-5 h-5 text-emerald-600" />
          ) : (
            <Clock className="w-5 h-5 text-amber-600" />
          )}

          <div>
            <h4
              className={`font-bold text-xs flex items-center gap-2 ${
                isBreached ? 'text-rose-950' : allDone ? 'text-emerald-950' : 'text-amber-950'
              }`}
            >
              <span>紧急修复 · 24小时补齐文档倒计时</span>
              {isBreached && (
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-200 text-rose-900">
                  🔴 已超时，请尽快补齐
                </span>
              )}
              {allDone && (
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-200 text-emerald-900">
                  ✓ 3 项文档已全部补齐
                </span>
              )}
            </h4>
            <p className="text-[11px] text-slate-600 mt-0.5">
              紧急版本上线后，请在 24 小时内补齐事故复盘与需求文档，避免日后代码脱节或重复踩坑。
            </p>
          </div>
        </div>

        <div className="text-right shrink-0">
          <span className="text-[11px] text-slate-500 block">24小时截止时间</span>
          <span className="font-mono text-xs font-bold text-slate-800">
            {new Date(status.sla_deadline).toLocaleString()}
          </span>
        </div>
      </div>

      {errorMsg && (
        <div className="p-2.5 bg-rose-100/80 rounded-lg text-rose-800 text-xs flex items-center justify-between">
          <span>{errorMsg}</span>
          <button onClick={() => setErrorMsg(null)} className="font-bold text-rose-600">✕</button>
        </div>
      )}

      {/* 3 大必选任务清单 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-1">
        {status.tasks.map((task) => {
          const isDone = task.status === 'completed';
          return (
            <div
              key={task.id}
              className={`p-3.5 rounded-xl border flex flex-col justify-between space-y-2 text-xs transition ${
                isDone
                  ? 'bg-white/80 border-emerald-200'
                  : isBreached
                  ? 'bg-white border-rose-300 shadow-2xs'
                  : 'bg-white border-amber-200 shadow-2xs'
              }`}
            >
              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] uppercase font-bold text-slate-400">
                    {task.task_type}
                  </span>
                  {isDone ? (
                    <span className="text-emerald-700 font-bold text-[11px] flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" /> 已完成
                    </span>
                  ) : (
                    <span className="text-amber-700 font-bold text-[11px] flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5" /> 待补齐
                    </span>
                  )}
                </div>
                <h5 className="font-bold text-slate-900 text-xs">
                  {getTaskHumanName(task.task_type, task.title)}
                </h5>
              </div>

              <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
                {isDone ? (
                  <span className="text-[10px] text-slate-400 truncate">
                    {task.completed_by} 于 {task.completed_at ? new Date(task.completed_at).toLocaleTimeString() : ''}
                  </span>
                ) : (
                  <button
                    onClick={() => handleCompleteTask(task.id)}
                    disabled={completingId === task.id}
                    className="w-full py-1.5 px-3 rounded-lg text-xs font-bold bg-slate-900 hover:bg-slate-800 text-white transition flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
                  >
                    {completingId === task.id ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                      <FileCheck2 className="w-3.5 h-3.5" />
                    )}
                    已补齐并确认
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
