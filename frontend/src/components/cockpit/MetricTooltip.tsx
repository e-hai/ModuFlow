import React, { useState } from 'react';
import { HelpCircle, X } from 'lucide-react';

interface MetricTooltipProps {
  title: string;
  formula?: string;
  definition: string;
  accountingType?: '收付实现制 (Cash Basis)' | '权责发生制 (Accrual Basis)' | '业务统计口径';
  dataSource?: string;
  className?: string;
}

export const MetricTooltip: React.FC<MetricTooltipProps> = ({
  title,
  formula,
  definition,
  accountingType,
  dataSource = '财务系统自动对接 · 每小时同步',
  className = '',
}) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <span className={`relative inline-flex items-center align-middle ${className}`}>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setIsOpen(!isOpen);
        }}
        onMouseEnter={() => setIsOpen(true)}
        onMouseLeave={() => setIsOpen(false)}
        className="text-slate-400 hover:text-emerald-600 transition p-0.5 rounded cursor-pointer"
        aria-label={`查看 ${title} 统计口径说明`}
      >
        <HelpCircle className="w-3.5 h-3.5" />
      </button>

      {isOpen && (
        <div
          role="tooltip"
          className="absolute z-50 left-1/2 -translate-x-1/2 bottom-full mb-2 w-72 p-3 bg-slate-900 text-slate-100 text-xs rounded-xl shadow-xl border border-slate-700 pointer-events-auto space-y-2 animate-in fade-in zoom-in-95 duration-150"
        >
          <div className="flex items-center justify-between border-b border-slate-800 pb-1.5">
            <span className="font-semibold text-emerald-400 flex items-center gap-1">
              <span>ⓘ</span> {title}
            </span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                setIsOpen(false);
              }}
              className="text-slate-400 hover:text-white"
            >
              <X className="w-3 h-3" />
            </button>
          </div>

          <p className="text-slate-300 leading-relaxed text-[11px]">{definition}</p>

          {formula && (
            <div className="bg-slate-800/80 rounded-lg p-2 font-mono text-[11px] text-emerald-300 border border-slate-700">
              <span className="text-slate-400 block text-[10px] font-sans mb-0.5">计算公式</span>
              {formula}
            </div>
          )}

          <div className="pt-1 border-t border-slate-800 flex flex-col gap-0.5 text-[10px] text-slate-400">
            {accountingType && (
              <div>
                <span className="text-slate-500">核算原则：</span>
                <span className="text-slate-300 font-medium">{accountingType}</span>
              </div>
            )}
            <div>
              <span className="text-slate-500">数据源：</span>
              <span className="text-slate-300">{dataSource}</span>
            </div>
          </div>
        </div>
      )}
    </span>
  );
};
