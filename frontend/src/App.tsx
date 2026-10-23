import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { Sidebar } from './components/Sidebar';
import { SettingsModal } from './components/SettingsModal';
import { Dashboard } from './pages/Dashboard';
import { WorkflowView } from './pages/WorkflowView';
import { ModuleSpace } from './pages/ModuleSpace';
import { IssueBoard } from './pages/IssueBoard';
import { StrategicInitiative, Product, ModuleInstance } from './types';
import { api } from './services/api';
import { X, Compass, Briefcase } from 'lucide-react';

export const App: React.FC = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [currentView, setCurrentView] = useState<'dashboard' | 'workflow' | 'module' | 'issues'>('dashboard');

  const [initiatives, setInitiatives] = useState<StrategicInitiative[]>([]);
  const [currentInitiative, setCurrentInitiative] = useState<StrategicInitiative | null>(null);

  const [products, setProducts] = useState<Product[]>([]);
  const [currentProduct, setCurrentProduct] = useState<Product | null>(null);

  const [selectedRunId, setSelectedRunId] = useState<string | undefined>(undefined);
  const [activeModule, setActiveModule] = useState<ModuleInstance | null>(null);
  const [runModules, setRunModules] = useState<ModuleInstance[]>([]);

  // Modals
  const [showNewInitModal, setShowNewInitModal] = useState(false);
  const [initName, setInitName] = useState('');
  const [initDesc, setInitDesc] = useState('');
  const [initOwner, setInitOwner] = useState('负责人');
  const [initBudget, setInitBudget] = useState(0);
  const [initStrategicIntent, setInitStrategicIntent] = useState('');
  const [initTargetMarket, setInitTargetMarket] = useState('');
  const [initBusinessHypothesis, setInitBusinessHypothesis] = useState('');

  const [showNewProdModal, setShowNewProdModal] = useState(false);
  const [prodName, setProdName] = useState('');
  const [prodCode, setProdCode] = useState('');
  const [prodDesc, setProdDesc] = useState('');

  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [selectedPeriod, setSelectedPeriod] = useState<string>('lifetime');

  useEffect(() => {
    loadInitiativesAndProducts();
  }, []);

  const loadInitiativesAndProducts = async (preferredInitId?: string) => {
    try {
      const initList = await api.getInitiatives();
      setInitiatives(initList);

      const activeInit = preferredInitId
        ? initList.find(i => i.id === preferredInitId) || initList[0]
        : (currentInitiative ? initList.find(i => i.id === currentInitiative.id) || initList[0] : initList[0]);

      if (activeInit) {
        setCurrentInitiative(activeInit);
        const prodList = await api.getProducts(activeInit.id);
        setProducts(prodList);
        if (prodList.length > 0 && (!currentProduct || !prodList.find(p => p.id === currentProduct.id))) {
          setCurrentProduct(prodList[0]);
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleSelectInitiative = async (initId: string) => {
    const found = initiatives.find(i => i.id === initId);
    if (found) {
      setCurrentInitiative(found);
      setCurrentView('dashboard');
      try {
        const prodList = await api.getProducts(found.id);
        setProducts(prodList);
        if (prodList.length > 0) {
          setCurrentProduct(prodList[0]);
        } else {
          setCurrentProduct(null);
        }
      } catch (e) {
        console.error(e);
      }
    }
  };

  const handleRenameInitiative = async (initId: string, newName: string) => {
    const updated = await api.updateInitiative(initId, { name: newName });
    setInitiatives(prev => prev.map(i => i.id === initId ? { ...i, name: updated.name } : i));
    if (currentInitiative?.id === initId) {
      setCurrentInitiative(prev => prev ? { ...prev, name: updated.name } : null);
    }
  };

  const handleDeleteInitiative = async (initId: string) => {
    await api.deleteInitiative(initId);
    const remaining = initiatives.filter(i => i.id !== initId);
    setInitiatives(remaining);
    if (currentInitiative?.id === initId) {
      if (remaining.length > 0) {
        await handleSelectInitiative(remaining[0].id);
      } else {
        setCurrentInitiative(null);
        setProducts([]);
        setCurrentProduct(null);
      }
    }
  };

  // Called from Dashboard or Sidebar to select product & enter its workbench
  const handleSelectProduct = (product: Product, defaultRunId?: string) => {
    setCurrentProduct(product);
    setSelectedRunId(defaultRunId);
    setCurrentView('workflow');
  };

  const handleSelectModule = (mod: ModuleInstance, allModules: ModuleInstance[]) => {
    setActiveModule(mod);
    setRunModules(allModules);
    setCurrentView('module');
  };

  // Create Initiative submit
  const handleCreateInitiative = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!initName.trim()) return;
    try {
      const created = await api.createInitiative({
        name: initName.trim(),
        description: initDesc.trim() || undefined,
        owner: initOwner.trim() || '负责人',
        budget: Number(initBudget) || 0,
        status: 'active',
        strategic_intent: initStrategicIntent.trim() || undefined,
        target_market: initTargetMarket.trim() || undefined,
        business_model_hypothesis: initBusinessHypothesis.trim() || undefined,
      });
      setShowNewInitModal(false);
      setInitName('');
      setInitDesc('');
      setInitStrategicIntent('');
      setInitTargetMarket('');
      setInitBusinessHypothesis('');
      await loadInitiativesAndProducts(created.id);
      alert('战略工程创建成功！');
    } catch (err: any) {
      alert(`创建战略工程失败: ${err.message}`);
    }
  };

  // Create Product submit
  const handleCreateProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prodName.trim() || !prodCode.trim() || !currentInitiative) return;
    try {
      const newProd = await api.createProduct({
        name: prodName.trim(),
        code: prodCode.trim().toUpperCase(),
        description: prodDesc.trim(),
        initiative_id: currentInitiative.id
      });
      setShowNewProdModal(false);
      setProdName('');
      setProdCode('');
      setProdDesc('');
      const prodList = await api.getProducts(currentInitiative.id);
      setProducts(prodList);
      setCurrentProduct(newProd);
      alert('矩阵产品添加成功！');
    } catch (err: any) {
      alert(`创建产品失败: ${err.message}`);
    }
  };

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50 text-slate-900 font-sans">
      {/* 1. 左侧战略工程列表侧边栏 */}
      <Sidebar
        isOpen={isSidebarOpen}
        initiatives={initiatives}
        currentInitiative={currentInitiative}
        onSelectInitiative={handleSelectInitiative}
        onOpenNewInitiativeModal={() => setShowNewInitModal(true)}
        onRenameInitiative={handleRenameInitiative}
        onDeleteInitiative={handleDeleteInitiative}
        onOpenSettingsModal={() => setShowSettingsModal(true)}
      />

      {/* 2. 右侧主工作区 */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* 顶部极简导航：展开收起按钮、战略标题、主体身份与底稿弹窗入口、周期切换下拉 */}
        <Navbar
          isSidebarOpen={isSidebarOpen}
          onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
          currentInitiative={currentInitiative}
          currentProduct={currentProduct}
          products={products}
          currentView={currentView}
          onNavigateToDashboard={() => setCurrentView('dashboard')}
          selectedPeriod={selectedPeriod}
          onPeriodChange={setSelectedPeriod}
        />

        {/* 内容展示区 */}
        <main className="flex-1 overflow-y-auto">
          {currentView === 'dashboard' && (
            <Dashboard
              currentInitiative={currentInitiative}
              products={products}
              selectedPeriod={selectedPeriod}
              onPeriodChange={setSelectedPeriod}
              onEnterProductWorkbench={handleSelectProduct}
              onOpenNewProductModal={() => setShowNewProdModal(true)}
              onOpenNewInitiativeModal={() => setShowNewInitModal(true)}
              onNavigateToIssues={() => setCurrentView('issues')}
            />
          )}

          {currentView === 'workflow' && (
            <WorkflowView
              currentProduct={currentProduct}
              allProducts={products}
              initialRunId={selectedRunId}
              onSelectProduct={p => {
                setCurrentProduct(p);
                setSelectedRunId(undefined);
              }}
              onSelectModule={handleSelectModule}
              onBackToDashboard={() => setCurrentView('dashboard')}
            />
          )}

          {currentView === 'module' && activeModule && (
            <ModuleSpace
              module={activeModule}
              allModules={runModules}
              onBackToWorkflow={() => setCurrentView('workflow')}
              onModuleUpdated={() => {
                loadInitiativesAndProducts();
              }}
            />
          )}

          {currentView === 'issues' && (
            <IssueBoard />
          )}
        </main>
      </div>

      {/* 弹窗 1: 新建战略工程 */}
      {showNewInitModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 w-full max-w-lg rounded-2xl p-6 shadow-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-100">
              <h3 className="font-semibold text-slate-900 text-base flex items-center gap-2">
                <Compass className="w-5 h-5 text-emerald-600" />
                新建顶层战略工程 (Strategic Initiative)
              </h3>
              <button onClick={() => setShowNewInitModal(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleCreateInitiative} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">战略工程名称 *</label>
                <input
                  type="text"
                  required
                  placeholder="例：北美跨境电商独立站矩阵战略"
                  value={initName}
                  onChange={e => setInitName(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 focus:bg-white focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">战略目标描述</label>
                <textarea
                  rows={2}
                  placeholder="例：2026 年度拓展北美服装及家居品类出海，建立品牌站点与配套 AI 客服系统。"
                  value={initDesc}
                  onChange={e => setInitDesc(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 focus:bg-white focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">责任人</label>
                  <input
                    type="text"
                    value={initOwner}
                    onChange={e => setInitOwner(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 focus:bg-white focus:outline-none focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">战略预算 (元)</label>
                  <input
                    type="number"
                    min="0"
                    value={initBudget}
                    onChange={e => setInitBudget(Number(e.target.value))}
                    className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 focus:bg-white focus:outline-none focus:border-emerald-500"
                  />
                </div>
              </div>

              {/* 战略底稿三要素 (可选) */}
              <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 space-y-3">
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider block font-mono">
                  战略底稿设定 (可选，后续可在驾驶舱随时补充)
                </span>
                <div>
                  <label className="block text-[11px] font-medium text-slate-600 mb-1">战略定性 (Strategic Intent)</label>
                  <input
                    type="text"
                    placeholder="例：以独立站高频单品切入，构建私域用户池与变现闭环"
                    value={initStrategicIntent}
                    onChange={e => setInitStrategicIntent(e.target.value)}
                    className="w-full bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-xs text-slate-900 focus:outline-none focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-medium text-slate-600 mb-1">目标市场 (Target Market)</label>
                  <input
                    type="text"
                    placeholder="例：北美千禧一代与 Z 世代高性价比快消及生活方式群体"
                    value={initTargetMarket}
                    onChange={e => setInitTargetMarket(e.target.value)}
                    className="w-full bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-xs text-slate-900 focus:outline-none focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-medium text-slate-600 mb-1">商业模式假设 (Business Model Hypothesis)</label>
                  <input
                    type="text"
                    placeholder="例：首单 CAC ≤ $20，复购率 ≥ 30%，综合 LTV/CAC ≥ 3.0x"
                    value={initBusinessHypothesis}
                    onChange={e => setInitBusinessHypothesis(e.target.value)}
                    className="w-full bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-xs text-slate-900 focus:outline-none focus:border-emerald-500"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowNewInitModal(false)}
                  className="px-3 py-1.5 rounded-lg text-xs text-slate-600 hover:bg-slate-100 cursor-pointer"
                >
                  取消
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 rounded-lg text-xs font-medium bg-emerald-600 hover:bg-emerald-500 text-white cursor-pointer"
                >
                  确认创建战略工程
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 弹窗 2: 新增产品 */}
      {showNewProdModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 w-full max-w-md rounded-2xl p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-100">
              <h3 className="font-semibold text-slate-900 text-base flex items-center gap-2">
                <Briefcase className="w-5 h-5 text-emerald-600" />
                新增矩阵产品 (Product)
              </h3>
              <button onClick={() => setShowNewProdModal(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleCreateProduct} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">产品名称 *</label>
                <input
                  type="text"
                  required
                  placeholder="例：北美独立站 Web 端"
                  value={prodName}
                  onChange={e => setProdName(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 focus:bg-white focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">产品代号 (Code) *</label>
                <input
                  type="text"
                  required
                  placeholder="例：NA-WEB"
                  value={prodCode}
                  onChange={e => setProdCode(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 uppercase font-mono focus:bg-white focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">产品描述</label>
                <textarea
                  rows={2}
                  placeholder="例：面向北美用户的快时尚电商平台主站。"
                  value={prodDesc}
                  onChange={e => setProdDesc(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 focus:bg-white focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowNewProdModal(false)}
                  className="px-3 py-1.5 rounded-lg text-xs text-slate-600 hover:bg-slate-100"
                >
                  取消
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 rounded-lg text-xs font-medium bg-emerald-600 hover:bg-emerald-500 text-white"
                >
                  添加到当前战略矩阵
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 弹窗 3: 工作台应用信息与设置 */}
      <SettingsModal
        isOpen={showSettingsModal}
        onClose={() => setShowSettingsModal(false)}
      />
    </div>
  );
};

export default App;
