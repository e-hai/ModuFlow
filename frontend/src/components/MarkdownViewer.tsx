import React, { useState, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import { Copy, Check, ListTree, X, Compass, ChevronRight } from 'lucide-react';
import { MermaidDiagram } from './MermaidDiagram';

interface MarkdownViewerProps {
  content: string;
  className?: string;
  variant?: 'artifact' | 'chat';
}

const getHeadingId = (text: string) => {
  return 'sec-' + text
    .toLowerCase()
    .replace(/[^\w\u4e00-\u9fa5]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 50);
};

export const MarkdownViewer: React.FC<MarkdownViewerProps> = ({
  content,
  className = '',
  variant = 'artifact'
}) => {
  const [copiedCodeIndex, setCopiedCodeIndex] = useState<number | null>(null);
  const [isTocOpen, setIsTocOpen] = useState(false);
  const [activeHeadingId, setActiveHeadingId] = useState<string>('');

  const handleCopyCode = (text: string, index: number) => {
    navigator.clipboard.writeText(text);
    setCopiedCodeIndex(index);
    setTimeout(() => setCopiedCodeIndex(null), 2000);
  };

  const isArtifact = variant === 'artifact';

  // Extract TOC items for artifact mode
  const tocItems = useMemo(() => {
    if (!content || !isArtifact) return [];
    const items: { id: string; level: number; text: string }[] = [];
    const lines = content.split('\n');
    for (const line of lines) {
      const match = line.match(/^(#{1,3})\s+(.+)$/);
      if (match) {
        const level = match[1].length;
        const text = match[2].trim().replace(/[*_`]/g, '');
        if (text && !text.startsWith('---') && !text.startsWith('![')) {
          items.push({
            id: getHeadingId(text),
            level,
            text
          });
        }
      }
    }
    return items;
  }, [content, isArtifact]);

  const scrollToHeading = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      setActiveHeadingId(id);
    }
  };

  // 预处理内容：确保表格中常见的多行换行符 <br>、<br/> 或被转义的 &lt;br&gt; 均能被 rehype-raw 正常识别并换行渲染
  const processedContent = useMemo(() => {
    if (!content) return '';
    return content.replace(/&lt;br\s*\/?&gt;/gi, '<br />');
  }, [content]);

  return (
    <div className={`relative moduflow-markdown ${className}`}>
      {/* 智能悬浮目录大纲导航 (TOC) */}
      {isArtifact && tocItems.length >= 3 && (
        <div className="sticky top-2 z-20 flex justify-end mb-2 pointer-events-none">
          <div className="pointer-events-auto relative">
            <button
              type="button"
              onClick={() => setIsTocOpen(!isTocOpen)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold shadow-xs transition cursor-pointer border ${
                isTocOpen
                  ? 'bg-indigo-600 text-white border-indigo-700'
                  : 'bg-white/90 backdrop-blur-md text-slate-700 hover:text-indigo-600 hover:bg-slate-50 border-slate-200/90'
              }`}
              title="切换文档大纲目录"
            >
              <ListTree className="w-3.5 h-3.5" />
              <span>文档大纲 ({tocItems.length})</span>
            </button>

            {isTocOpen && (
              <div className="absolute right-0 top-9 w-72 max-h-[70vh] overflow-y-auto bg-white/95 backdrop-blur-md border border-slate-200 rounded-2xl shadow-2xl p-3 z-30 animate-in fade-in duration-150">
                <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-100">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800">
                    <Compass className="w-4 h-4 text-indigo-600" />
                    <span>章节目录导引</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setIsTocOpen(false)}
                    className="p-1 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition cursor-pointer"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
                <div className="space-y-0.5">
                  {tocItems.map((item, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => {
                        scrollToHeading(item.id);
                        setIsTocOpen(false);
                      }}
                      className={`w-full text-left rounded-lg px-2 py-1.5 text-xs transition cursor-pointer flex items-start gap-1.5 ${
                        item.level === 1
                          ? 'font-bold text-slate-900 bg-slate-50/80 hover:bg-indigo-50 hover:text-indigo-700'
                          : item.level === 2
                            ? 'font-medium text-slate-700 pl-4 hover:bg-slate-50 hover:text-indigo-600'
                            : 'text-slate-500 pl-6 text-[11px] hover:bg-slate-50 hover:text-slate-800'
                      } ${activeHeadingId === item.id ? 'bg-indigo-50 text-indigo-700 font-semibold' : ''}`}
                    >
                      {item.level === 2 && <span className="text-slate-300 shrink-0 mt-0.5">•</span>}
                      {item.level === 3 && <ChevronRight className="w-2.5 h-2.5 text-slate-400 shrink-0 mt-1" />}
                      <span className="line-clamp-1">{item.text}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw]}
        components={{
          h1: ({ children }) => {
            const text = String(children);
            const id = getHeadingId(text);
            return (
              <h1 id={id} className={`scroll-mt-14 ${isArtifact ? 'text-xl' : 'text-base'} font-bold text-slate-900 mt-6 mb-3 pb-2 border-b border-slate-200 first:mt-0 tracking-tight leading-snug`}>
                {children}
              </h1>
            );
          },
          h2: ({ children }) => {
            const text = String(children);
            const id = getHeadingId(text);
            return (
              <h2 id={id} className={`scroll-mt-14 ${isArtifact ? 'text-base' : 'text-sm'} font-bold text-slate-800 mt-5 mb-2.5 pb-1 border-b border-slate-100 flex items-center gap-1.5 leading-snug`}>
                {children}
              </h2>
            );
          },
          h3: ({ children }) => {
            const text = String(children);
            const id = getHeadingId(text);
            return (
              <h3 id={id} className={`scroll-mt-14 ${isArtifact ? 'text-sm' : 'text-xs'} font-semibold text-slate-800 mt-4 mb-2 leading-snug`}>
                {children}
              </h3>
            );
          },
          h4: ({ children }) => (
            <h4 className="text-xs font-semibold text-slate-700 mt-3 mb-1.5 tracking-wide">
              {children}
            </h4>
          ),
          p: ({ children }) => (
            <p className="my-2.5 leading-relaxed text-xs text-slate-700">
              {children}
            </p>
          ),
          ul: ({ children }) => (
            <ul className="my-2.5 list-disc pl-5 space-y-1.5 text-xs text-slate-700 marker:text-slate-400">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="my-2.5 list-decimal pl-5 space-y-1.5 text-xs text-slate-700 marker:text-slate-500 font-medium">
              {children}
            </ol>
          ),
          li: ({ children }) => (
            <li className="leading-relaxed">
              {children}
            </li>
          ),
          blockquote: ({ children }) => {
            const text = String(children);
            let borderCls = 'border-emerald-500 bg-emerald-50/60 text-slate-700';
            if (text.includes('[!IMPORTANT]') || text.includes('硬性红线') || text.includes('安全区') || text.includes('门禁')) {
              borderCls = 'border-amber-500 bg-amber-50/70 text-amber-900';
            } else if (text.includes('[!WARNING]') || text.includes('[!CAUTION]') || text.includes('风险')) {
              borderCls = 'border-rose-500 bg-rose-50/70 text-rose-900';
            } else if (text.includes('[!NOTE]') || text.includes('[!TIP]')) {
              borderCls = 'border-blue-500 bg-blue-50/70 text-blue-900';
            }
            return (
              <blockquote className={`my-3.5 pl-3.5 pr-3 py-2.5 border-l-4 rounded-r-xl text-xs not-italic leading-relaxed shadow-2xs ${borderCls}`}>
                {children}
              </blockquote>
            );
          },
          table: ({ children }) => (
            <div className="my-4 overflow-x-auto rounded-xl border border-slate-200 shadow-2xs bg-white">
              <table className="w-full text-left border-collapse text-xs min-w-[500px]">
                {children}
              </table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="bg-slate-100/90 border-b border-slate-200 text-slate-800 font-semibold text-[11px] uppercase tracking-wider">
              {children}
            </thead>
          ),
          tbody: ({ children }) => (
            <tbody className="divide-y divide-slate-100">
              {children}
            </tbody>
          ),
          tr: ({ children }) => (
            <tr className="hover:bg-slate-50/80 transition-colors even:bg-slate-50/40">
              {children}
            </tr>
          ),
          th: ({ children }) => (
            <th className="py-2.5 px-3.5 text-xs font-semibold text-slate-800 border-r border-slate-200/60 last:border-r-0 whitespace-nowrap">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="py-2.5 px-3.5 text-xs text-slate-700 border-r border-slate-200/60 last:border-r-0 align-top leading-relaxed">
              {children}
            </td>
          ),
          hr: () => (
            <hr className="my-6 border-t border-slate-200" />
          ),
          code: ({ className: codeClassName, children, ...props }: any) => {
            const rawContent = String(children).replace(/\n$/, '');
            const isMultiline = rawContent.includes('\n');
            const match = /language-(\w+)/.exec(codeClassName || '');

            if (!isMultiline && !match) {
              return (
                <code
                  className="px-1.5 py-0.5 mx-0.5 rounded-md bg-slate-100 text-rose-600 font-mono text-[11px] border border-slate-200/70"
                  {...props}
                >
                  {children}
                </code>
              );
            }

            if (match && match[1] === 'mermaid') {
              return <MermaidDiagram chart={rawContent} />;
            }

            return (
              <div className="my-3.5 rounded-xl overflow-hidden border border-slate-800 bg-slate-900 shadow-md group relative">
                <div className="px-3.5 py-1.5 bg-slate-950/80 border-b border-slate-800 flex items-center justify-between text-[11px] text-slate-400 font-mono">
                  <span>{match ? match[1] : 'code'}</span>
                  <button
                    type="button"
                    onClick={() => handleCopyCode(rawContent, 1)}
                    className="flex items-center gap-1 text-slate-400 hover:text-white transition cursor-pointer"
                  >
                    {copiedCodeIndex === 1 ? (
                      <>
                        <Check className="w-3 h-3 text-emerald-400" />
                        <span className="text-emerald-400 text-[10px]">已复制</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3 h-3" />
                        <span className="text-[10px]">复制</span>
                      </>
                    )}
                  </button>
                </div>
                <pre className="p-3.5 text-slate-100 text-xs font-mono overflow-x-auto leading-relaxed">
                  <code className={codeClassName} {...props}>
                    {children}
                  </code>
                </pre>
              </div>
            );
          },
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:text-blue-800 underline underline-offset-2 transition font-medium"
            >
              {children}
            </a>
          ),
          strong: ({ children }) => (
            <strong className="font-semibold text-slate-900">
              {children}
            </strong>
          ),
          br: () => <br className="my-0.5" />
        }}
      >
        {processedContent}
      </ReactMarkdown>
    </div>
  );
};
