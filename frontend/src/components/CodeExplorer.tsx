import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  Folder,
  FolderOpen,
  FileCode,
  FileText,
  Search,
  Copy,
  Check,
  ExternalLink,
  ChevronRight,
  ChevronDown,
  Terminal,
  Code2,
  Layers,
  Sparkles,
  Info,
  RefreshCw,
  Laptop
} from 'lucide-react';
import { api } from '../services/api';
import { CodebaseTreeNode, CodebaseSummaryAndTree, CodebaseFileContent } from '../types';

interface CodeExplorerProps {
  moduleId: string;
  moduleName?: string;
  moduleCode?: string;
}

export const CodeExplorer: React.FC<CodeExplorerProps> = ({
  moduleId,
  moduleName = '开发实现',
  moduleCode = '07',
}) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [data, setData] = useState<CodebaseSummaryAndTree | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState<string>('');
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set());
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<CodebaseFileContent | null>(null);
  const [loadingFile, setLoadingFile] = useState<boolean>(false);
  const [copiedCode, setCopiedCode] = useState<boolean>(false);
  const [copiedPath, setCopiedPath] = useState<boolean>(false);

  // IDE launch dropdown & message state
  const [showIdeMenu, setShowIdeMenu] = useState<boolean>(false);
  const [ideFeedback, setIdeFeedback] = useState<{ success: boolean; message: string } | null>(null);
  const [launchingIde, setLaunchingIde] = useState<boolean>(false);
  const ideMenuRef = useRef<HTMLDivElement>(null);

  // Close IDE dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (ideMenuRef.current && !ideMenuRef.current.contains(e.target as Node)) {
        setShowIdeMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Fetch summary and tree
  const loadTree = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getCodebaseTree(moduleId);
      setData(res);

      // Auto-expand root directories and select the first code file
      const initialExpanded = new Set<string>();
      let firstFile: string | null = null;

      const traverse = (nodes: CodebaseTreeNode[]) => {
        for (const n of nodes) {
          if (n.type === 'directory') {
            initialExpanded.add(n.path);
            if (n.children) traverse(n.children);
          } else if (n.type === 'file' && !firstFile) {
            // Prefer kotlin or build file if available
            if (n.name.endsWith('.kt') || n.name.endsWith('.kts') || n.name.endsWith('.md')) {
              firstFile = n.path;
            }
          }
        }
      };

      if (res.tree) {
        traverse(res.tree);
        // Fallback to any first file if no preferred file was picked
        if (!firstFile) {
          const findAny = (nodes: CodebaseTreeNode[]): string | null => {
            for (const n of nodes) {
              if (n.type === 'file') return n.path;
              if (n.children) {
                const sub = findAny(n.children);
                if (sub) return sub;
              }
            }
            return null;
          };
          firstFile = findAny(res.tree);
        }
      }

      setExpandedPaths(initialExpanded);
      if (firstFile) {
        setSelectedFilePath(firstFile);
      }
    } catch (err: any) {
      setError(err?.message || '获取代码工程树失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTree();
  }, [moduleId]);

  // Load file content when selectedFilePath changes
  useEffect(() => {
    if (!selectedFilePath) {
      setFileContent(null);
      return;
    }
    let cancelled = false;
    const fetchFile = async () => {
      try {
        setLoadingFile(true);
        const res = await api.getCodebaseFile(moduleId, selectedFilePath);
        if (!cancelled) {
          setFileContent(res);
        }
      } catch (err: any) {
        if (!cancelled) {
          setFileContent({
            path: selectedFilePath,
            name: selectedFilePath.split('/').pop() || '',
            size: 0,
            language: 'plaintext',
            content: `// 无法读取文件内容: ${err?.message || '未知错误'}`
          });
        }
      } finally {
        if (!cancelled) setLoadingFile(false);
      }
    };
    fetchFile();
    return () => {
      cancelled = true;
    };
  }, [moduleId, selectedFilePath]);

  const toggleDirectory = (path: string) => {
    setExpandedPaths(prev => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  const handleCopyCode = () => {
    if (!fileContent?.content) return;
    navigator.clipboard.writeText(fileContent.content);
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 2000);
  };

  const handleCopyAbsolutePath = () => {
    if (!data?.codebase_path) return;
    navigator.clipboard.writeText(data.codebase_path);
    setCopiedPath(true);
    setShowIdeMenu(false);
    setIdeFeedback({
      success: true,
      message: `已复制本地绝对路径: ${data.codebase_path}`
    });
    setTimeout(() => setCopiedPath(false), 3000);
  };

  const handleOpenIde = async (ide: 'android_studio' | 'xcode') => {
    try {
      setLaunchingIde(true);
      setShowIdeMenu(false);
      setIdeFeedback(null);
      const res = await api.openCodebaseInIde(moduleId, ide);
      setIdeFeedback({
        success: res.success,
        message: res.message
      });
    } catch (err: any) {
      setIdeFeedback({
        success: false,
        message: err?.message || '调起本地 IDE 失败'
      });
    } finally {
      setLaunchingIde(false);
    }
  };

  // Helper to format file sizes
  const formatBytes = (bytes?: number) => {
    if (bytes === undefined || bytes === null) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  // Helper for language badge styling
  const renderLanguageBadge = (lang?: string) => {
    const l = (lang || '').toLowerCase();
    let bg = 'bg-slate-100 text-slate-700 border-slate-200';
    if (l === 'kotlin') bg = 'bg-purple-50 text-purple-700 border-purple-200';
    else if (l === 'swift') bg = 'bg-orange-50 text-orange-700 border-orange-200';
    else if (l === 'gradle') bg = 'bg-sky-50 text-sky-700 border-sky-200';
    else if (l === 'json') bg = 'bg-amber-50 text-amber-700 border-amber-200';
    else if (l === 'markdown') bg = 'bg-blue-50 text-blue-700 border-blue-200';
    return (
      <span className={`text-[10px] font-mono px-2 py-0.5 rounded border uppercase font-medium ${bg}`}>
        {lang || 'CODE'}
      </span>
    );
  };

  // Filter tree nodes by search query
  const filteredTree = useMemo(() => {
    if (!data?.tree) return [];
    if (!searchQuery.trim()) return data.tree;

    const query = searchQuery.toLowerCase().trim();

    const filterNode = (node: CodebaseTreeNode): CodebaseTreeNode | null => {
      if (node.type === 'file') {
        if (node.name.toLowerCase().includes(query) || node.path.toLowerCase().includes(query)) {
          return node;
        }
        return null;
      }
      if (node.type === 'directory' && node.children) {
        const filteredChildren = node.children
          .map(child => filterNode(child))
          .filter((c): c is CodebaseTreeNode => c !== null);
        if (filteredChildren.length > 0 || node.name.toLowerCase().includes(query)) {
          return {
            ...node,
            children: filteredChildren
          };
        }
      }
      return null;
    };

    return data.tree
      .map(n => filterNode(n))
      .filter((n): n is CodebaseTreeNode => n !== null);
  }, [data?.tree, searchQuery]);

  // Recursive tree node renderer
  const renderTreeNode = (node: CodebaseTreeNode, depth = 0) => {
    const isDir = node.type === 'directory';
    const isExpanded = expandedPaths.has(node.path);
    const isSelected = selectedFilePath === node.path;

    return (
      <div key={node.path} className="select-none">
        <div
          onClick={() => {
            if (isDir) {
              toggleDirectory(node.path);
            } else {
              setSelectedFilePath(node.path);
            }
          }}
          style={{ paddingLeft: `${depth * 14 + 10}px` }}
          className={`flex items-center gap-1.5 py-1 px-2 rounded-md text-xs cursor-pointer transition group ${
            isSelected
              ? 'bg-indigo-100/80 text-indigo-900 font-semibold border-l-2 border-indigo-600'
              : 'text-slate-700 hover:bg-slate-100'
          }`}
        >
          {isDir ? (
            <>
              {isExpanded ? (
                <ChevronDown className="w-3.5 h-3.5 text-slate-400 shrink-0" />
              ) : (
                <ChevronRight className="w-3.5 h-3.5 text-slate-400 shrink-0" />
              )}
              {isExpanded ? (
                <FolderOpen className="w-3.5 h-3.5 text-amber-500 shrink-0" />
              ) : (
                <Folder className="w-3.5 h-3.5 text-amber-500 shrink-0" />
              )}
              <span className="truncate">{node.name}</span>
            </>
          ) : (
            <>
              <span className="w-3.5 h-3.5 shrink-0 flex items-center justify-center">
                <FileCode className="w-3.5 h-3.5 text-slate-400 group-hover:text-slate-600" />
              </span>
              <span className="truncate flex-1">{node.name}</span>
              {node.size !== undefined && (
                <span className="text-[10px] text-slate-400 font-mono opacity-0 group-hover:opacity-100 transition">
                  {formatBytes(node.size)}
                </span>
              )}
            </>
          )}
        </div>

        {isDir && isExpanded && node.children && (
          <div>
            {node.children.map(child => renderTreeNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-12 text-slate-400 gap-3">
        <RefreshCw className="w-6 h-6 animate-spin text-indigo-500" />
        <span className="text-xs font-medium">正在解析本地代码工程结构...</span>
      </div>
    );
  }

  if (error || !data || !data.exists || data.tree.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-12 text-slate-500 text-center max-w-lg mx-auto">
        <div className="w-12 h-12 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 mb-4 shadow-xs">
          <Terminal className="w-6 h-6" />
        </div>
        <h3 className="text-sm font-semibold text-slate-800 mb-1.5">
          {data?.exists ? '工程目录暂无代码文件' : '代码工程目录尚未生成'}
        </h3>
        <p className="text-xs text-slate-500 leading-relaxed mb-6">
          {error || '当前工序的工程代码正在由研发 Agent (eng) 进行架构与编写。待构建完成后，完整的跨平台目录树与源码将在此呈现。'}
        </p>
        <button
          onClick={loadTree}
          className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-medium bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 shadow-2xs transition"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          刷新代码库状态
        </button>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-slate-50">
      {/* 顶部工程指标栏与操作入口 */}
      <div className="bg-white border-b border-slate-200 px-4 py-2.5 flex items-center justify-between flex-wrap gap-3 shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-xs font-semibold text-slate-800">
              {data.root_name}
            </span>
          </div>

          <div className="flex items-center gap-3 text-xs text-slate-500 font-mono">
            <span>
              <strong className="text-slate-700 font-bold">{data.total_files}</strong> 个文件
            </span>
            <span className="text-slate-300">|</span>
            <span>
              约 <strong className="text-slate-700 font-bold">{data.total_lines.toLocaleString()}</strong> 行代码
            </span>
          </div>
        </div>

        {/* 核心操作区：统一入口 [💻 在本地 Android Studio / Xcode 打开] */}
        <div className="flex items-center gap-2 relative" ref={ideMenuRef}>
          <button
            type="button"
            onClick={() => setShowIdeMenu(!showIdeMenu)}
            disabled={launchingIde}
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white shadow-xs transition cursor-pointer"
            title="在本地主流 IDE 中直接调起当前跨平台工程"
          >
            <Laptop className="w-4 h-4" />
            <span>💻 在本地 Android Studio / Xcode 打开</span>
            <ChevronDown className="w-3.5 h-3.5 opacity-80" />
          </button>

          {/* IDE 展开菜单 */}
          {showIdeMenu && (
            <div className="absolute right-0 top-full mt-1.5 w-64 bg-white rounded-xl shadow-lg border border-slate-200 py-1.5 z-50 text-xs">
              <div className="px-3 py-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-wider border-b border-slate-100">
                本地 IDE 联动
              </div>
              <button
                type="button"
                onClick={() => handleOpenIde('android_studio')}
                className="w-full text-left px-3.5 py-2 hover:bg-slate-50 flex items-center gap-2.5 text-slate-700 transition"
              >
                <div className="w-6 h-6 rounded-md bg-emerald-100 flex items-center justify-center text-emerald-700 font-bold text-[10px]">
                  AS
                </div>
                <div>
                  <div className="font-medium text-slate-800">在 Android Studio 打开</div>
                  <div className="text-[10px] text-slate-400">推荐 KMP / Android 架构主入口</div>
                </div>
              </button>

              <button
                type="button"
                onClick={() => handleOpenIde('xcode')}
                className="w-full text-left px-3.5 py-2 hover:bg-slate-50 flex items-center gap-2.5 text-slate-700 transition"
              >
                <div className="w-6 h-6 rounded-md bg-sky-100 flex items-center justify-center text-sky-700 font-bold text-[10px]">
                  XC
                </div>
                <div>
                  <div className="font-medium text-slate-800">在 Xcode 打开</div>
                  <div className="text-[10px] text-slate-400">打开 iosApp 纯原生工程</div>
                </div>
              </button>

              <div className="border-t border-slate-100 my-1" />

              <button
                type="button"
                onClick={handleCopyAbsolutePath}
                className="w-full text-left px-3.5 py-2 hover:bg-slate-50 flex items-center gap-2.5 text-slate-700 transition"
              >
                <div className="w-6 h-6 rounded-md bg-slate-100 flex items-center justify-center text-slate-600">
                  <Copy className="w-3.5 h-3.5" />
                </div>
                <div>
                  <div className="font-medium text-slate-800">复制本地工程绝对路径</div>
                  <div className="text-[10px] text-slate-400 font-mono truncate max-w-[160px]">
                    {data.codebase_path}
                  </div>
                </div>
              </button>
            </div>
          )}

          <button
            type="button"
            onClick={loadTree}
            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-700 hover:bg-slate-100 transition"
            title="刷新代码工程树"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* 调起反馈通知 */}
      {ideFeedback && (
        <div
          className={`px-4 py-2 text-xs flex items-center justify-between border-b ${
            ideFeedback.success
              ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
              : 'bg-amber-50 text-amber-800 border-amber-200'
          }`}
        >
          <div className="flex items-center gap-2">
            <Info className="w-4 h-4 shrink-0" />
            <span>{ideFeedback.message}</span>
          </div>
          <button
            type="button"
            onClick={() => setIdeFeedback(null)}
            className="text-[11px] underline opacity-80 hover:opacity-100"
          >
            关闭
          </button>
        </div>
      )}

      {/* 主体两栏：左侧目录树 + 右侧源码阅读器 */}
      <div className="flex-1 flex overflow-hidden">
        {/* 左侧：文件树 */}
        <div className="w-72 bg-white border-r border-slate-200 flex flex-col shrink-0">
          {/* 文件搜索输入框 */}
          <div className="p-2 border-b border-slate-100">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="搜索文件..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-lg pl-8 pr-3 py-1 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          </div>

          {/* 目录树滚动区 */}
          <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
            {filteredTree.length > 0 ? (
              filteredTree.map(node => renderTreeNode(node, 0))
            ) : (
              <div className="text-center py-8 text-xs text-slate-400">
                未找到匹配的文件
              </div>
            )}
          </div>
        </div>

        {/* 右侧：代码预览区 */}
        <div className="flex-1 flex flex-col bg-slate-900 text-slate-200 overflow-hidden">
          {selectedFilePath ? (
            <>
              {/* 文件信息顶栏 */}
              <div className="bg-slate-800/90 border-b border-slate-700 px-4 py-2 flex items-center justify-between flex-wrap gap-2 shrink-0">
                <div className="flex items-center gap-2.5 min-w-0">
                  {renderLanguageBadge(fileContent?.language)}
                  <span className="text-xs font-mono text-slate-300 truncate">
                    {selectedFilePath}
                  </span>
                  {fileContent?.size !== undefined && (
                    <span className="text-[11px] font-mono text-slate-400">
                      ({formatBytes(fileContent.size)})
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={handleCopyCode}
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-700/80 hover:bg-slate-700 text-slate-200 text-xs font-medium transition cursor-pointer"
                    title="复制文件代码"
                  >
                    {copiedCode ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                        <span className="text-emerald-300">已复制代码</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5 text-slate-400" />
                        <span>复制代码</span>
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* 代码正文与行号 */}
              <div className="flex-1 overflow-auto font-mono text-xs leading-relaxed p-4 bg-slate-900 text-slate-100 flex">
                {loadingFile ? (
                  <div className="flex-1 flex items-center justify-center text-slate-400 gap-2">
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>正在加载文件内容...</span>
                  </div>
                ) : (
                  <div className="w-full flex">
                    {/* 行号列 */}
                    <div className="select-none text-slate-600 text-right pr-4 border-r border-slate-800 font-mono text-[11px]">
                      {(fileContent?.content || '').split('\n').map((_, i) => (
                        <div key={i}>{i + 1}</div>
                      ))}
                    </div>

                    {/* 代码内容 */}
                    <pre className="flex-1 pl-4 overflow-x-auto text-[11px] font-mono text-slate-200 m-0">
                      <code>{fileContent?.content || ''}</code>
                    </pre>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-slate-500 text-xs gap-2">
              <FileCode className="w-8 h-8 text-slate-700" />
              <span>请在左侧文件树中选择要预览的文件</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
