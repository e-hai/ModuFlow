import React, { useEffect, useState, useCallback } from 'react';
import { api } from '../services/api';
import { StrategicInitiative, Product, ExecutiveCockpitResponse } from '../types';
import { Building2, Loader2, Plus } from 'lucide-react';
import { CockpitHeader, CockpitTabKey } from '../components/cockpit/CockpitHeader';
import { OverviewTab } from '../components/cockpit/OverviewTab';
import { PortfolioTab } from '../components/cockpit/PortfolioTab';
import { MarketingTab } from '../components/cockpit/MarketingTab';
import { OperationsTab } from '../components/cockpit/OperationsTab';
import { FinancialLedgerTab } from '../components/cockpit/FinancialLedgerTab';
import { DecisionCenterTab } from '../components/cockpit/DecisionCenterTab';

interface DashboardProps {
  currentInitiative: StrategicInitiative | null;
  products: Product[];
  refreshTrigger?: number;
  selectedPeriod?: string;
  onPeriodChange?: (period: string) => void;
  onEnterProductWorkbench: (product: Product, defaultRunId?: string) => void;
  onOpenNewProductModal: () => void;
  onOpenNewInitiativeModal?: () => void;
  onNavigateToIssues?: () => void;
  initialTab?: CockpitTabKey;
  listStatus?: 'loading' | 'ready' | 'error';
  listError?: string | null;
  onRetryLoad?: () => void;
}

export const Dashboard: React.FC<DashboardProps> = ({
  currentInitiative,
  products,
  refreshTrigger,
  selectedPeriod = 'lifetime',
  onPeriodChange,
  onEnterProductWorkbench,
  onOpenNewProductModal,
  onOpenNewInitiativeModal,
  onNavigateToIssues,
  initialTab = 'overview',
  listStatus = 'ready',
  listError = null,
  onRetryLoad,
}) => {
  const [activeTab, setActiveTab] = useState<CockpitTabKey>(initialTab);
  const [cockpit, setCockpit] = useState<ExecutiveCockpitResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const loadCockpitData = useCallback(async () => {
    if (!currentInitiative?.id) return;
    try {
      setLoading(true);
      setError(null);
      const data = await api.getCockpit(currentInitiative.id, selectedPeriod);
      setCockpit(data);
    } catch (err: any) {
      console.error('Failed to load cockpit data:', err);
      setError(err.message || '加载驾驶舱数据失败');
    } finally {
      setLoading(false);
    }
  }, [currentInitiative?.id, selectedPeriod]);

  useEffect(() => {
    loadCockpitData();
  }, [loadCockpitData, refreshTrigger, products]);

  if (!currentInitiative) {
    const waiting = listStatus === 'loading';
    const failed = listStatus === 'error';
    return (
      <div className="max-w-4xl mx-auto py-16 text-center text-slate-500">
        <Building2 className="w-12 h-12 mx-auto mb-3 text-slate-300" />
        <p className="text-base font-semibold text-slate-800">
          {waiting ? '正在读取工程…' : failed ? '工程还在，页面暂时读不出来' : '暂无选中的战略工程'}
        </p>
        <p className="text-xs text-slate-400 mt-1 mb-4">
          {waiting
            ? '同意之后下一步会在后台继续，刷新不会把工程删掉。'
            : failed
              ? (listError || '请稍后重试')
              : '请在左侧侧边栏中选择已有工程，或新建首个顶层战略工程'}
        </p>
        {failed && onRetryLoad && (
          <button
            onClick={onRetryLoad}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-xs transition cursor-pointer"
          >
            重试
          </button>
        )}
        {!waiting && !failed && onOpenNewInitiativeModal && (
          <button
            onClick={onOpenNewInitiativeModal}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-xs transition cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>新建战略工程</span>
          </button>
        )}
      </div>
    );
  }

  const pendingDecisionsCount = cockpit?.decisions?.filter((d) => d.status === 'proposed').length || 0;
  const activeRisksCount = cockpit?.risks?.filter((r) => !r.is_resolved).length || 0;

  return (
    <div className="max-w-6xl mx-auto px-6 py-6 space-y-6">
      {/* 6 大业务模块 Tab 导航栏 */}
      {cockpit && (
        <CockpitHeader
          cockpit={cockpit}
          activeTab={activeTab}
          onTabChange={setActiveTab}
          pendingDecisionsCount={pendingDecisionsCount}
          activeRisksCount={activeRisksCount}
        />
      )}

      {loading && !cockpit && (
        <div className="py-24 text-center text-slate-400 space-y-3">
          <Loader2 className="w-8 h-8 mx-auto animate-spin text-emerald-600" />
          <p className="text-xs">正在加载经营数据...</p>
        </div>
      )}

      {error && !cockpit && (
        <div className="p-4 rounded-xl bg-rose-50 text-rose-700 text-xs border border-rose-200">
          {error}
        </div>
      )}

      {/* 6 大业务模块内容区 */}
      {cockpit && (
        <div>
          {activeTab === 'overview' && (
            <OverviewTab
              cockpit={cockpit}
              onNavigateTab={setActiveTab}
              onEnterProductWorkbench={(productId) => {
                const p = products.find((prod) => prod.id === productId || prod.code === productId);
                if (p) onEnterProductWorkbench(p);
              }}
            />
          )}

          {activeTab === 'portfolio' && (
            <PortfolioTab
              portfolio={cockpit.portfolio}
              products={products}
              onOpenNewProductModal={onOpenNewProductModal}
              onEnterProductWorkbench={onEnterProductWorkbench}
            />
          )}

          {activeTab === 'marketing' && (
            <MarketingTab
              marketing={cockpit.marketing}
              onNavigateToDecisions={() => setActiveTab('decisions')}
            />
          )}

          {activeTab === 'operations' && (
            <OperationsTab operations={cockpit.operations} />
          )}

          {activeTab === 'finance' && (
            <FinancialLedgerTab financials={cockpit.financials} />
          )}

          {activeTab === 'decisions' && (
            <DecisionCenterTab
              initiativeId={cockpit.initiative_id}
              risks={cockpit.risks}
              decisions={cockpit.decisions}
              onDecisionUpdated={loadCockpitData}
            />
          )}
        </div>
      )}
    </div>
  );
};
