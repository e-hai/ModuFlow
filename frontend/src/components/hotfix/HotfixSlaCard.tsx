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
      // It's normal if not triggered yet
    } finally {
      setLoading(false);
    }
  };

  const handleCompleteTask = async (taskId: string) => {
    const notes = prompt('请输入该追溯任务完成说明/文档链接：', '已补齐文档并通过审核闭环');
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

  return (
    <div
      className={`border rounded-2xl p-5 shadow-xs transition-all space-y-3 ${
        isBreached
          ? 'bg-rose-50 border-rose-300'
          : allDone
          ? 'bg-emerald-50/60 border-emerald-300'
          : 'bg-amber-50/60 border-amber-300'
      }`}
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-black/5 pb-2.5">
        <div className="flex items-center gap-2">
          {isBreached ? (
            <ShieldAlert className="w-5 h-5 text-rose-600 animate-pulse" />
          ) : allDone ? (
            <CheckCircle2 className="w-5 h-5 text-emerald-600" />
          ) : (
            <Clock className="w-5 h-5 text-amber-600" />
          )}

          <div>
            <h4
              className={`font-bold text-xs flex items-center gap-1.5 ${
                isBreached ? 'text-rose-950' : allDone ? 'text-emerald-950' : 'text-amber-950'
              }`}
            >
              <span>紧急热修 24h 追溯归档机制 (Hotfix Documentation SLA)</span>
              {isBreached && (
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-200 text-rose-900 font-mono">
                  🔴 SLA 已超时超期
                </span>
              )}
              {allDone && (
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-200 text-emerald-900 font-mono">
                  ✓ 3项任务全部闭环
                </span>
              )}
            </h4>
            <p className="text-[11px] text-slate-600 mt-0.5">
              硬约束铁律：线上发布后 24 小时内必须补齐「需求变更单 + 事故复盘 + PRD 基线同步」，否则触发阻断性告警。
            </p>
          </div>
        </div>

        <div className="text-right shrink-0">
          <span className="text-[11px] text-slate-500 block">SLA 截止期限</span>
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
              className={`p-3 rounded-xl border flex flex-col justify-between space-y-2 text-xs transition ${
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
                <h5 className="font-bold text-slate-900 text-xs">{task.title}</h5>
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
                    标记补齐完成
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
