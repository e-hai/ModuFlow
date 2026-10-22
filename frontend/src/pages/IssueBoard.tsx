import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Issue } from '../types';
import { SeverityBadge } from '../components/StatusBadge';
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Clock,
  Filter,
  RefreshCw,
  Search,
  Wrench
} from 'lucide-react';

export const IssueBoard: React.FC = () => {
  const [issues, setIssues] = useState<Issue[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [searchKeyword, setSearchKeyword] = useState('');

  useEffect(() => {
    loadIssues();
  }, []);

  const loadIssues = async () => {
    try {
      setLoading(true);
      const data = await api.getIssues();
      setIssues(data);
    } catch (e: any) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateStatus = async (issueId: string, newStatus: Issue['status'], resolution?: string) => {
    try {
      await api.updateIssue(issueId, { status: newStatus, resolution });
      await loadIssues();
    } catch (e: any) {
      alert(`更新状态失败: ${e.message}`);
    }
  };

  const filteredIssues = issues.filter(i => {
    if (statusFilter !== 'all' && i.status !== statusFilter) return false;
    if (severityFilter !== 'all' && i.severity !== severityFilter) return false;
    if (searchKeyword && !i.title.toLowerCase().includes(searchKeyword.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-rose-600" />
            跨模块 Issue 与缺陷闭环追踪
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            支持下游测试/运营将问题穿透反馈至前序需求或开发模块，Critical 级问题将阻塞基线锁定
          </p>
        </div>

        <button
          onClick={loadIssues}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 shadow-xs transition cursor-pointer"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          刷新列表
        </button>
      </div>

      {/* 过滤条 */}
      <div className="flex flex-wrap items-center gap-3 bg-white border border-slate-200 p-3 rounded-xl text-xs shadow-xs">
        <div className="flex items-center gap-1.5 text-slate-500">
          <Filter className="w-3.5 h-3.5" />
          <span>筛选:</span>
        </div>

        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          className="bg-slate-50 border border-slate-200 rounded px-2.5 py-1 text-slate-800"
        >
          <option value="all">全部状态</option>
          <option value="open">待解决 (Open)</option>
          <option value="investigating">排查中 (Investigating)</option>
          <option value="fixing">修复中 (Fixing)</option>
          <option value="verifying">待回验 (Verifying)</option>
          <option value="closed">已关闭 (Closed)</option>
        </select>

        <select
          value={severityFilter}
          onChange={e => setSeverityFilter(e.target.value)}
          className="bg-slate-50 border border-slate-200 rounded px-2.5 py-1 text-slate-800"
        >
          <option value="all">全部严重度</option>
          <option value="critical">Critical (阻断性)</option>
          <option value="major">Major (严重)</option>
          <option value="minor">Minor (次要)</option>
        </select>

        <div className="relative flex-1 max-w-xs">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2" />
          <input
            type="text"
            placeholder="搜索缺陷标题..."
            value={searchKeyword}
            onChange={e => setSearchKeyword(e.target.value)}
            className="w-full bg-slate-50 border border-slate-200 rounded pl-8 pr-3 py-1 text-xs text-slate-900 placeholder-slate-400 focus:bg-white focus:outline-none"
          />
        </div>

        <div className="ml-auto text-slate-500 font-mono text-[11px]">
          共 {filteredIssues.length} 条记录
        </div>
      </div>

      {/* Issue 表格 / 列表 */}
      {loading ? (
        <div className="text-center py-12 text-slate-400 text-xs">加载 Issue 列表中...</div>
      ) : filteredIssues.length === 0 ? (
        <div className="bg-white border border-slate-200 rounded-xl p-12 text-center text-slate-400 text-xs shadow-xs">
          暂无符合条件的 Issue
        </div>
      ) : (
        <div className="space-y-3">
          {filteredIssues.map(issue => {
            const isClosed = issue.status === 'closed';
            return (
              <div
                key={issue.id}
                className={`p-4 rounded-xl border transition ${
                  isClosed
                    ? 'bg-slate-50/60 border-slate-200 opacity-70'
                    : issue.severity === 'critical'
                    ? 'bg-white border-rose-200 hover:border-rose-300 shadow-xs'
                    : 'bg-white border-slate-200 hover:border-slate-300 shadow-xs'
                }`}
              >
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                  <div className="space-y-1.5 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-xs text-slate-500">
                        {issue.id}
                      </span>
                      <SeverityBadge severity={issue.severity} />
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-slate-100 text-slate-600 border border-slate-200">
                        {issue.priority}
                      </span>
                      <h3 className="font-bold text-sm text-slate-900">{issue.title}</h3>
                    </div>

                    <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
                      <div className="flex items-center gap-1.5 font-medium">
                        <span className="text-slate-700">{issue.source_module_name || '来源模块'}</span>
                        <ArrowRight className="w-3.5 h-3.5 text-rose-500" />
                        <span className="text-emerald-700">{issue.target_module_name || '责任模块'}</span>
                      </div>
                      <span>•</span>
                      <span>提报人: {issue.reporter} ({issue.reporter_role})</span>
                      <span>•</span>
                      <span>{new Date(issue.created_at).toLocaleString()}</span>
                    </div>

                    {/* 复现与描述详情 */}
                    {issue.description && (
                      <div className="text-[11px] text-slate-600 bg-slate-50 p-2.5 rounded-lg border border-slate-200 font-mono space-y-1">
                        {issue.description.expected && (
                          <div><span className="text-slate-400">预期:</span> {issue.description.expected}</div>
                        )}
                        {issue.description.actual && (
                          <div><span className="text-rose-600 font-medium">实际:</span> {issue.description.actual}</div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* 状态操作区 */}
                  <div className="flex items-center gap-2 shrink-0 border-t md:border-t-0 md:border-l border-slate-100 pt-3 md:pt-0 md:pl-4">
                    <span
                      className={`text-xs px-2.5 py-1 rounded font-medium ${
                        isClosed
                          ? 'bg-slate-100 text-slate-600 border border-slate-200'
                          : issue.status === 'fixing'
                          ? 'bg-amber-50 text-amber-800 border border-amber-200'
                          : 'bg-rose-50 text-rose-800 border border-rose-200'
                      }`}
                    >
                      状态: {issue.status}
                    </span>

                    {!isClosed ? (
                      <div className="flex items-center gap-1">
                        {issue.status === 'open' && (
                          <button
                            onClick={() => handleUpdateStatus(issue.id, 'fixing')}
                            className="px-2.5 py-1 rounded text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 transition flex items-center gap-1 cursor-pointer"
                          >
                            <Wrench className="w-3 h-3 text-amber-600" />
                            开始修复
                          </button>
                        )}
                        {issue.status === 'fixing' && (
                          <button
                            onClick={() => handleUpdateStatus(issue.id, 'verifying', 'fixed')}
                            className="px-2.5 py-1 rounded text-xs bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 transition flex items-center gap-1 cursor-pointer"
                          >
                            <Clock className="w-3 h-3 text-blue-600" />
                            提交待回验
                          </button>
                        )}
                        <button
                          onClick={() => handleUpdateStatus(issue.id, 'closed', 'fixed')}
                          className="px-2.5 py-1 rounded text-xs bg-emerald-600 hover:bg-emerald-500 text-white transition flex items-center gap-1 font-medium cursor-pointer"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          验证关闭
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => handleUpdateStatus(issue.id, 'open')}
                        className="px-2 py-1 rounded text-[11px] text-slate-500 hover:text-slate-800 cursor-pointer"
                      >
                        重新打开
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
