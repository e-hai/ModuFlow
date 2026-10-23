import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Copy, Check } from 'lucide-react';

interface MarkdownViewerProps {
  content: string;
  className?: string;
  variant?: 'artifact' | 'chat';
}

export const MarkdownViewer: React.FC<MarkdownViewerProps> = ({
  content,
  className = '',
  variant = 'artifact'
}) => {
  const [copiedCodeIndex, setCopiedCodeIndex] = useState<number | null>(null);

  const handleCopyCode = (text: string, index: number) => {
    navigator.clipboard.writeText(text);
    setCopiedCodeIndex(index);
    setTimeout(() => setCopiedCodeIndex(null), 2000);
  };

  const isArtifact = variant === 'artifact';

  return (
    <div className={`moduflow-markdown ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className={`${isArtifact ? 'text-xl' : 'text-base'} font-bold text-slate-900 mt-6 mb-3 pb-2 border-b border-slate-200 first:mt-0 tracking-tight leading-snug`}>
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className={`${isArtifact ? 'text-base' : 'text-sm'} font-bold text-slate-800 mt-5 mb-2.5 pb-1 border-b border-slate-100 flex items-center gap-1.5 leading-snug`}>
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className={`${isArtifact ? 'text-sm' : 'text-xs'} font-semibold text-slate-800 mt-4 mb-2 leading-snug`}>
              {children}
            </h3>
          ),
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
          blockquote: ({ children }) => (
            <blockquote className="my-3.5 pl-3.5 py-2 border-l-4 border-emerald-500 bg-emerald-50/60 rounded-r-xl text-xs text-slate-700 not-italic leading-relaxed shadow-2xs">
              {children}
            </blockquote>
          ),
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

            const codeId = Math.random();
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
          )
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};
