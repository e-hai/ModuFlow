import React, { useEffect, useState, useId } from 'react';
import mermaid from 'mermaid';
import { Eye, Code2, Copy, Check, AlertCircle } from 'lucide-react';

mermaid.initialize({
  startOnLoad: false,
  theme: 'neutral',
  securityLevel: 'loose',
  fontFamily: 'ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
  flowchart: {
    htmlLabels: true,
    curve: 'basis',
  },
});

export function sanitizeMermaid(chart: string): string {
  let cleanChart = chart.trim();

  // 1. Fix subgraph starting with digit: subgraph 1_name -> subgraph sub_1_name
  cleanChart = cleanChart.replace(/subgraph\s+(\d+[\w-]*)/g, 'subgraph sub_$1');

  // 2. Fix unbracketed subgraphs with spaces/parens: subgraph Title -> subgraph sub_sg_0["Title"]
  let sgIdx = 0;
  cleanChart = cleanChart.replace(/^(\s*subgraph\s+)([^"\[\n\r]+)$/gm, (match, prefix, title) => {
    return `${prefix}sub_sg_${sgIdx++}["${title.trim()}"]`;
  });

  // 3. Fix chained arrows with & like: A1 & A2 & A3 --> B1 --> B2
  cleanChart = cleanChart.replace(
    /^(\s*)([\w\s&]+?)\s*(-->|-.->|==>)\s*([\w]+)\s*(-->|-.->|==>)\s*([\w]+)\s*$/gm,
    (_match, indent, fromStr, arrow1, mid, arrow2, to) => {
      return `${indent}${fromStr} ${arrow1} ${mid}\n${indent}${mid} ${arrow2} ${to}`;
    }
  );

  // 4. Fix labeled links on & multi-nodes: C1 & C2 -->|"label"| A2 & A3
  cleanChart = cleanChart.replace(
    /^(\s*)([\w\s&]+?)\s*(-->|-.->|==>)\|([^|]+)\|\s*([\w\s&]+?)\s*$/gm,
    (match, indent, fromStr, arrow, label, toStr) => {
      const froms = fromStr.split('&').map((s: string) => s.trim()).filter(Boolean);
      const tos = toStr.split('&').map((s: string) => s.trim()).filter(Boolean);
      if (froms.length > 1 || tos.length > 1) {
        const lines: string[] = [];
        froms.forEach((f: string) => {
          tos.forEach((t: string) => {
            lines.push(`${indent}${f} ${arrow}|${label}| ${t}`);
          });
        });
        return lines.join('\n');
      }
      return match;
    }
  );

  return cleanChart;
}

interface MermaidDiagramProps {
  chart: string;
}

export const MermaidDiagram: React.FC<MermaidDiagramProps> = ({ chart }) => {
  const [svgHtml, setSvgHtml] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'chart' | 'code'>('chart');
  const [copied, setCopied] = useState<boolean>(false);
  const rawId = useId();
  const safeId = 'm_' + rawId.replace(/[^a-zA-Z0-9]/g, '');

  useEffect(() => {
    let isMounted = true;
    const renderId = `${safeId}_${Math.random().toString(36).slice(2, 7)}`;

    const render = async () => {
      try {
        setError(null);
        const cleanChart = sanitizeMermaid(chart);
        const { svg } = await mermaid.render(renderId, cleanChart);
        if (isMounted) {
          setSvgHtml(svg);
        }
      } catch (err: any) {
        console.warn('Mermaid rendering failed:', err);
        // Clean up any stray error div injected into body by Mermaid
        const stray = document.getElementById(renderId) || document.getElementById(`d${renderId}`);
        if (stray) stray.remove();

        if (isMounted) {
          setError(err?.message || '图表语法解析失败');
          setActiveTab('code');
        }
      }
    };

    render();

    return () => {
      isMounted = false;
      const stray = document.getElementById(renderId) || document.getElementById(`d${renderId}`);
      if (stray) stray.remove();
    };
  }, [chart, safeId]);

  const handleCopy = () => {
    navigator.clipboard.writeText(chart);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="my-4 rounded-xl border border-slate-200 bg-white shadow-2xs overflow-hidden">
      {/* Header bar */}
      <div className="px-3.5 py-2 bg-slate-50/90 border-b border-slate-200 flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-slate-700 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            架构拓扑图
          </span>
          {error && (
            <span className="text-[11px] text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full border border-amber-200 flex items-center gap-1">
              <AlertCircle className="w-3 h-3" />
              语法异常，已切换至源码
            </span>
          )}
        </div>

        <div className="flex items-center gap-1.5">
          <div className="flex bg-slate-200/70 p-0.5 rounded-lg text-[11px]">
            <button
              type="button"
              onClick={() => setActiveTab('chart')}
              className={`flex items-center gap-1 px-2 py-1 rounded-md transition cursor-pointer ${
                activeTab === 'chart'
                  ? 'bg-white text-slate-800 font-medium shadow-2xs'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              <Eye className="w-3 h-3" />
              视图
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('code')}
              className={`flex items-center gap-1 px-2 py-1 rounded-md transition cursor-pointer ${
                activeTab === 'code'
                  ? 'bg-white text-slate-800 font-medium shadow-2xs'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              <Code2 className="w-3 h-3" />
              源码
            </button>
          </div>

          <button
            type="button"
            onClick={handleCopy}
            className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-md transition cursor-pointer"
            title="复制源码"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      {activeTab === 'chart' && (
        <div className="p-4 overflow-x-auto flex justify-center bg-slate-50/30 min-h-[140px]">
          {svgHtml ? (
            <div
              className="mermaid-svg-container w-full flex justify-center [&>svg]:max-w-full [&>svg]:h-auto"
              dangerouslySetInnerHTML={{ __html: svgHtml }}
            />
          ) : (
            <div className="flex items-center justify-center text-xs text-slate-400 py-8">
              正在渲染拓扑图...
            </div>
          )}
        </div>
      )}

      {activeTab === 'code' && (
        <div className="relative">
          {error && (
            <div className="px-4 py-2 bg-amber-50/80 border-b border-amber-200 text-[11px] text-amber-800 font-mono">
              错误提示: {error}
            </div>
          )}
          <pre className="p-3.5 text-slate-200 bg-slate-900 text-xs font-mono overflow-x-auto leading-relaxed">
            <code>{chart}</code>
          </pre>
        </div>
      )}
    </div>
  );
};
