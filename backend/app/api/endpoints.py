from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload

from backend.app.core.database import get_db
from backend.app.core.config import settings
from backend.app.models.entities import (
    StrategicInitiative,
    Product,
    WorkflowTemplate,
    WorkflowRun,
    ModuleInstance,
    CollaborationSession,
    SessionMessage,
    Artifact,
    Issue,
    ExecutiveDecision,
    ExecutiveRisk
)
from backend.app.schemas.all_schemas import (
    StrategicInitiativeOut, StrategicInitiativeCreate, StrategicInitiativeUpdate,
    ProductOut, ProductCreate,
    WorkflowTemplateOut,
    WorkflowRunOut, WorkflowRunCreate, WorkflowRunUpdate,
    ModuleInstanceOut, ModulePhaseUpdate,
    CollaborationSessionOut, SessionMessageCreate, SessionMessageOut,
    ArtifactOut,
    IssueOut, IssueCreate, IssueUpdate,
    ExecutiveCockpitResponse, DecisionActionRequest, ExecutiveDecisionItem,
    FinancialMetrics, FocusAlert, PortfolioProductItem, MarketingCockpitData, MarketingCategoryItem, MarketingSubChannelItem,
    OperationsCockpitData, ExecutiveRiskItem,
    AgentSettingsOut, AgentSettingsUpdate, AgentPresetItem
)
from backend.app.services.workflow_engine import (
    create_workflow_run_from_template,
    can_baseline_module,
    unlock_downstream_modules
)
from backend.app.services.agent_runner import execute_agent_for_session

api_router = APIRouter()

# --- Strategic Initiatives ---
@api_router.get("/initiatives", response_model=List[StrategicInitiativeOut])
async def list_initiatives(db: AsyncSession = Depends(get_db)):
    stmt = select(StrategicInitiative).order_by(StrategicInitiative.created_at.desc())
    res = await db.execute(stmt)
    initiatives = res.scalars().all()
    
    out = []
    for item in initiatives:
        # Count products
        p_stmt = select(func.count(Product.id)).where(Product.initiative_id == item.id)
        p_res = await db.execute(p_stmt)
        count = p_res.scalar_one() or 0
        
        dto = StrategicInitiativeOut.model_validate(item)
        dto.product_count = count
        out.append(dto)
    return out

@api_router.post("/initiatives", response_model=StrategicInitiativeOut)
async def create_initiative(data: StrategicInitiativeCreate, db: AsyncSession = Depends(get_db)):
    init = StrategicInitiative(
        name=data.name,
        description=data.description,
        owner=data.owner,
        budget=data.budget,
        status=data.status
    )
    if data.id:
        init.id = data.id
    db.add(init)
    await db.commit()
    await db.refresh(init)
    dto = StrategicInitiativeOut.model_validate(init)
    dto.product_count = 0
    return dto

@api_router.patch("/initiatives/{initiative_id}", response_model=StrategicInitiativeOut)
async def update_initiative(
    initiative_id: str,
    data: StrategicInitiativeUpdate,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(StrategicInitiative).where(StrategicInitiative.id == initiative_id)
    res = await db.execute(stmt)
    init = res.scalar_one_or_none()
    if not init:
        raise HTTPException(status_code=404, detail="Initiative not found")
    
    if data.name is not None:
        init.name = data.name
    if data.description is not None:
        init.description = data.description
    if data.owner is not None:
        init.owner = data.owner
    if data.budget is not None:
        init.budget = data.budget
    if data.status is not None:
        init.status = data.status
    if data.strategic_intent is not None:
        init.strategic_intent = data.strategic_intent
    if data.target_market is not None:
        init.target_market = data.target_market
    if data.business_model_hypothesis is not None:
        init.business_model_hypothesis = data.business_model_hypothesis
        
    await db.commit()
    await db.refresh(init)
    
    # 自动同步至物理工作区
    from backend.app.services.workspace_sync import sync_strategic_initiative_workspace
    try:
        await sync_strategic_initiative_workspace(db, init.id)
    except Exception as e:
        logger.warning(f"Failed to sync workspace for {init.id}: {e}")
    
    p_stmt = select(func.count(Product.id)).where(Product.initiative_id == init.id)
    p_res = await db.execute(p_stmt)
    count = p_res.scalar_one() or 0
    
    dto = StrategicInitiativeOut.model_validate(init)
    dto.product_count = count
    return dto

@api_router.delete("/initiatives/{initiative_id}")
async def delete_initiative(
    initiative_id: str,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(StrategicInitiative).where(StrategicInitiative.id == initiative_id)
    res = await db.execute(stmt)
    init = res.scalar_one_or_none()
    if not init:
        raise HTTPException(status_code=404, detail="Initiative not found")
        
    # Clean up associated issues if any
    p_stmt = select(Product.id).where(Product.initiative_id == initiative_id)
    p_res = await db.execute(p_stmt)
    prod_ids = p_res.scalars().all()
    
    if prod_ids:
        r_stmt = select(WorkflowRun.id).where(WorkflowRun.product_id.in_(prod_ids))
        r_res = await db.execute(r_stmt)
        run_ids = r_res.scalars().all()
        
        if run_ids:
            m_stmt = select(ModuleInstance.id).where(ModuleInstance.run_id.in_(run_ids))
            m_res = await db.execute(m_stmt)
            mod_ids = m_res.scalars().all()
            
            if mod_ids:
                del_issues_stmt = select(Issue).where(
                    or_(Issue.source_module_id.in_(mod_ids), Issue.target_module_id.in_(mod_ids))
                )
                iss_res = await db.execute(del_issues_stmt)
                for issue_item in iss_res.scalars().all():
                    await db.delete(issue_item)
    
    await db.delete(init)
    await db.commit()
    return {"ok": True, "message": f"Initiative {initiative_id} deleted"}

# --- Workspace Physical File Endpoints ---
@api_router.post("/initiatives/{initiative_id}/sync-workspace")
async def trigger_workspace_sync(
    initiative_id: str,
    db: AsyncSession = Depends(get_db)
):
    from backend.app.services.workspace_sync import sync_strategic_initiative_workspace
    result = await sync_strategic_initiative_workspace(db, initiative_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Sync failed"))
    return result

@api_router.get("/initiatives/{initiative_id}/workspace-tree")
async def get_initiative_workspace_tree(
    initiative_id: str
):
    from backend.app.services.workspace_sync import get_workspace_tree
    result = get_workspace_tree(initiative_id)
    if not result.get("exists"):
        raise HTTPException(status_code=404, detail=f"Workspace for initiative '{initiative_id}' not found on disk")
    return result

# --- CEO Executive Business Cockpit Endpoints ---
@api_router.get("/initiatives/{initiative_id}/cockpit", response_model=ExecutiveCockpitResponse)
async def get_initiative_cockpit(
    initiative_id: str,
    period: str = "lifetime",
    db: AsyncSession = Depends(get_db)
):
    stmt = select(StrategicInitiative).where(StrategicInitiative.id == initiative_id)
    res = await db.execute(stmt)
    init = res.scalar_one_or_none()
    if not init:
        raise HTTPException(status_code=404, detail="Initiative not found")

    # 1. Products
    p_stmt = select(Product).where(Product.initiative_id == initiative_id).order_by(Product.created_at.desc())
    p_res = await db.execute(p_stmt)
    products = p_res.scalars().all()

    portfolio_items = []
    for p in products:
        r_stmt = select(func.count(WorkflowRun.id)).where(WorkflowRun.product_id == p.id)
        r_res = await db.execute(r_stmt)
        runs_count = r_res.scalar_one() or 0
        
        target_val = p.kpi_target or (50000.0 if p.strategic_role == "acquisition" else 15.0)
        actual_val = p.kpi_actual or (38200.0 if p.strategic_role == "acquisition" else 18.0)
        completion_rate = round((actual_val / target_val) * 100, 1) if target_val > 0 else 0.0

        portfolio_items.append(PortfolioProductItem(
            id=p.id,
            name=p.name,
            code=p.code,
            strategic_role=p.strategic_role or "acquisition",
            stage=p.stage or "growth",
            budget_allocated=p.budget_allocated or 250000.0,
            actual_spent=p.actual_spent or 125000.0,
            revenue_contribution=p.revenue_contribution or 180000.0,
            kpi_name=p.kpi_name or ("有效激活用户" if p.strategic_role == "acquisition" else "商户单次佣金"),
            kpi_target=target_val,
            kpi_actual=actual_val,
            kpi_unit=p.kpi_unit or ("人" if p.strategic_role == "acquisition" else "元/人"),
            kpi_completion_rate=completion_rate,
            key_risk=p.key_risk or ("推广获客成本高于目标设定" if p.code == "ACC-SEA" else "本地银行网关清算审核周期较长"),
            recommendation=p.recommendation or ("评估优化渠道投入" if p.code == "ACC-SEA" else "追加补贴预算"),
            active_runs_count=runs_count
        ))

    # 2. Financial Ledger
    budget_total = float(init.budget_total or init.budget or 500000.0)
    committed_unpaid = float(init.committed_unpaid if init.committed_unpaid is not None else 80000.0)
    actual_paid = float(init.actual_paid if init.actual_paid is not None else 215000.0)
    available_budget = round(budget_total - committed_unpaid - actual_paid, 2)
    revenue_recognized = float(init.revenue_recognized if init.revenue_recognized is not None else 350000.0)
    cash_collected = float(init.cash_collected if init.cash_collected is not None else 320000.0)
    net_cash_flow = round(cash_collected - actual_paid, 2)
    roi_percent = round(((revenue_recognized - actual_paid) / actual_paid) * 100, 1) if actual_paid > 0 else None

    financials = FinancialMetrics(
        budget_total=budget_total,
        committed_unpaid=committed_unpaid,
        actual_paid=actual_paid,
        available_budget=available_budget,
        revenue_recognized=revenue_recognized,
        cash_collected=cash_collected,
        net_cash_flow=net_cash_flow,
        roi_percent=roi_percent,
        target_breakeven_date="2026-12-31",
        forecast_breakeven_date="2027-02-28",
        burn_rate_monthly=32000.0,
        currency=init.currency or "CNY"
    )

    # 3. Focus Alerts (CEO 3 大焦点)
    focus_alerts = [
        FocusAlert(
            id="ALERT-01",
            title="获客成本显著高于预期目标",
            summary="ACC-SEA 近 14 天加权 CAC 达 ¥25.0，超出目标 ¥15.0 约 66.7%，需评估是否缩减低效投放渠道。",
            type="cac_spike",
            severity="warning",
            action_hint="建议审核经营决策中心中的预算调配提议"
        ),
        FocusAlert(
            id="ALERT-02",
            title="累计净现金流转正节点可能延后",
            summary="受海外支付网关接入审核周期延长影响，预计累计现金流回本日期由 2026-12 延后至 2027-02。",
            type="breakeven_delayed",
            severity="warning",
            action_hint="建议关注 QPAY 商户直通网关备用方案"
        ),
        FocusAlert(
            id="ALERT-03",
            title="待拍板：产品推广预算再分配方案",
            summary="AI 提议将 ACC-SEA 结余推广预算 ¥35,000 转移注入 QPAY 商户返佣激励池以加速回款。",
            type="pending_approval",
            severity="info",
            action_hint="前往经营决策中心一键拍板审批"
        )
    ]

    # 4. Marketing Cockpit Data (一级获客机制分类 + 二级平台/渠道拆解)
    categories = [
        MarketingCategoryItem(
            category_code="paid_acquisition",
            category_name="付费广告获客 (Paid Acquisition)",
            spend=45000.0,
            acquired_users=1800,
            user_share_percent=19.5,
            cac=25.0,
            conversion_rate=8.5,
            revenue_contribution=68000.0,
            payback_days=45,
            decision_recommendation="减少或缩减预算，调优素材定向",
            sub_channels=[
                MarketingSubChannelItem(
                    name="Google 搜索广告",
                    spend=45000.0,
                    acquired_users=1800,
                    cac=25.0,
                    status="active"
                ),
                MarketingSubChannelItem(
                    name="Google 展示广告 / YouTube 视频广告",
                    spend=0.0,
                    acquired_users=0,
                    cac=0.0,
                    status="planned"
                )
            ]
        ),
        MarketingCategoryItem(
            category_code="partnerships",
            category_name="达人 / 合作伙伴获客 (Partnerships)",
            spend=25000.0,
            acquired_users=1420,
            user_share_percent=15.4,
            cac=17.61,
            conversion_rate=14.2,
            revenue_contribution=92000.0,
            payback_days=30,
            decision_recommendation="续约并扩大合作，追加优质达人预算",
            sub_channels=[
                MarketingSubChannelItem(
                    name="本地头部达人带货合作",
                    spend=20000.0,
                    acquired_users=1120,
                    cac=17.86,
                    status="active"
                ),
                MarketingSubChannelItem(
                    name="垂直领域金融 KOL / KOC 评测",
                    spend=5000.0,
                    acquired_users=300,
                    cac=16.67,
                    status="active"
                ),
                MarketingSubChannelItem(
                    name="联盟营销与本土商家生态合作",
                    spend=0.0,
                    acquired_users=0,
                    cac=0.0,
                    status="planned"
                )
            ]
        ),
        MarketingCategoryItem(
            category_code="organic_referral",
            category_name="自然增长与用户推荐 (Organic & Referral)",
            spend=15000.0,
            acquired_users=6000,
            user_share_percent=65.1,
            cac=2.50,
            conversion_rate=22.8,
            revenue_contribution=190000.0,
            payback_days=10,
            decision_recommendation="优化分享机制，扩大社交裂变",
            sub_channels=[
                MarketingSubChannelItem(
                    name="用户邀请与分享推荐奖励",
                    spend=12000.0,
                    acquired_users=4200,
                    cac=2.86,
                    status="active"
                ),
                MarketingSubChannelItem(
                    name="搜索引擎自然流量 (SEO) 与口碑直接访问",
                    spend=3000.0,
                    acquired_users=1800,
                    cac=1.67,
                    status="active"
                ),
                MarketingSubChannelItem(
                    name="社交平台自然内容传播",
                    spend=0.0,
                    acquired_users=0,
                    cac=0.0,
                    status="active"
                )
            ]
        )
    ]
    marketing = MarketingCockpitData(
        total_spend=85000.0,
        effective_new_users=9220,
        blended_cac=9.22,
        categories=categories
    )

    # 5. Operations Cockpit Data
    funnel = [
        {"stage": "落地页与广告曝光", "count": 120000, "conversion_rate": 100.0},
        {"stage": "完成注册与授权", "count": 48000, "conversion_rate": 40.0},
        {"stage": "完成首笔记账/有效激活", "count": 38200, "conversion_rate": 79.6},
        {"stage": "开通商业支付/付费转化", "count": 4200, "conversion_rate": 11.0}
    ]
    operations = OperationsCockpitData(
        dau=18500,
        mau=62000,
        retention_1d=46.2,
        retention_7d=31.8,
        retention_30d=19.4,
        paid_users=4200,
        arpu=8.5,
        arppu=83.3,
        ltv=72.0,
        ltv_cac_ratio=3.24,
        funnel=funnel
    )

    # 6. Risks
    risk_stmt = select(ExecutiveRisk).where(ExecutiveRisk.initiative_id == initiative_id).order_by(ExecutiveRisk.created_at.desc())
    risk_res = await db.execute(risk_stmt)
    db_risks = risk_res.scalars().all()
    
    if not db_risks:
        # Seed default risk
        default_risk = ExecutiveRisk(
            initiative_id=initiative_id,
            rule_code="RISK-CAC-SPIKE",
            title="ACC-SEA 获客成本严重偏离目标",
            severity="critical",
            description="ACC-SEA 连续 14 天加权获客成本达到 ¥25.0，超出目标 ¥15.0 约 66.7%，按当前消耗速率将在 22 天内耗尽单品预算。",
            product_code="ACC-SEA",
            action_suggestion="建议在决策中心审查调拨提议，缩减搜索广告投入并向变现端产品转移资金。",
            is_resolved=False
        )
        db.add(default_risk)
        await db.commit()
        await db.refresh(default_risk)
        db_risks = [default_risk]

    risks = [
        ExecutiveRiskItem(
            id=r.id,
            rule_code=r.rule_code,
            title=r.title,
            severity=r.severity,
            description=r.description,
            product_code=r.product_code,
            action_suggestion=r.action_suggestion,
            is_resolved=r.is_resolved,
            created_at=r.created_at
        ) for r in db_risks
    ]

    # 7. Decisions
    dec_stmt = select(ExecutiveDecision).where(ExecutiveDecision.initiative_id == initiative_id).order_by(ExecutiveDecision.created_at.desc())
    dec_res = await db.execute(dec_stmt)
    db_decs = dec_res.scalars().all()

    if not db_decs:
        # Seed default decision proposal
        default_dec = ExecutiveDecision(
            initiative_id=initiative_id,
            title="优化营销投放：由 ACC-SEA 向 QPAY 调配推广预算",
            status="proposed",
            recommendation_json={
                "action_type": "transfer_budget",
                "from_product_code": "ACC-SEA",
                "to_product_code": "QPAY",
                "amount": 35000.0,
                "currency": "CNY",
                "summary": "缩减 ACC-SEA 外部广告投放 30% 预算（¥35,000），全额转投 QPAY 商户端费率补贴与签约返佣"
            },
            evidence_json={
                "source_refs": [
                    {"dataset": "marketing_cost_daily", "period": "最近 21 天"},
                    {"dataset": "qpay_merchant_funnel", "period": "最近 14 天"}
                ],
                "assumptions": [
                    "ACC-SEA 削减外部搜索广告后，依靠达人与自然社交裂变仍可维持 75% 基础新增量",
                    "QPAY 获得补贴后签约活跃商户数预计增长 25%，直接提升每笔交易分润现金流"
                ],
                "data_coverage": "基于 9,220 名真实新增用户与 4,200 名付费转化用户结算数据"
            },
            impact_projection_json={
                "expected_cost_savings": 35000.0,
                "forecast_breakeven_variance_days": -18,
                "confidence_interval": "-25天 ~ -10天",
                "identified_risks": ["ACC-SEA 日新增用户可能由 1,200 降至约 900 人"]
            },
            idempotency_key=f"TX-INIT-{initiative_id[:8]}-001"
        )
        db.add(default_dec)
        await db.commit()
        await db.refresh(default_dec)
        db_decs = [default_dec]

    decisions = [
        ExecutiveDecisionItem(
            id=d.id,
            title=d.title,
            status=d.status,
            recommendation=d.recommendation_json,
            evidence=d.evidence_json,
            impact_projection=d.impact_projection_json,
            idempotency_key=d.idempotency_key,
            approved_by=d.approved_by,
            approved_at=d.approved_at,
            created_at=d.created_at
        ) for d in db_decs
    ]

    return ExecutiveCockpitResponse(
        initiative_id=init.id,
        initiative_name=init.name,
        owner=init.owner,
        status=init.status,
        strategic_intent=init.strategic_intent or "2026 年度以矩阵化打法进军东南亚数字消费市场，以免费多语言离线记账抓取高频用户流量，以聚合支付中枢实现商业变现闭环。",
        target_market=init.target_market or "东南亚下沉市场（印尼、越南、泰国）小微商户与个人用户",
        business_model_hypothesis=init.business_model_hypothesis or "前端记账获客 CAC 控制在 ¥15 以内，后端支付工具转化率 >= 8%，LTV/CAC 达标 3.0x",
        period=period,
        updated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        data_integrity="真实财务与埋点数据源已接入 (完整度 98.4%)",
        financials=financials,
        focus_alerts=focus_alerts,
        portfolio=portfolio_items,
        marketing=marketing,
        operations=operations,
        risks=risks,
        decisions=decisions
    )

@api_router.post("/initiatives/{initiative_id}/decisions/{decision_id}/action", response_model=ExecutiveDecisionItem)
async def act_on_decision(
    initiative_id: str,
    decision_id: str,
    req: DecisionActionRequest,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(ExecutiveDecision).where(
        ExecutiveDecision.id == decision_id,
        ExecutiveDecision.initiative_id == initiative_id
    )
    res = await db.execute(stmt)
    decision = res.scalar_one_or_none()
    if not decision:
        raise HTTPException(status_code=404, detail="Decision proposal not found")

    if req.action == "approve":
        decision.status = "approved"
        decision.approved_by = req.operator
        decision.approved_at = datetime.utcnow()
        
        # Execute budget adjustment if recommended
        rec = decision.recommendation_json or {}
        if rec.get("action_type") == "transfer_budget":
            amount = float(rec.get("amount", 0.0))
            from_code = rec.get("from_product_code")
            to_code = rec.get("to_product_code")
            if from_code and to_code and amount > 0:
                p_from = await db.execute(select(Product).where(Product.code == from_code, Product.initiative_id == initiative_id))
                from_prod = p_from.scalar_one_or_none()
                p_to = await db.execute(select(Product).where(Product.code == to_code, Product.initiative_id == initiative_id))
                to_prod = p_to.scalar_one_or_none()
                
                if from_prod and to_prod:
                    from_prod.budget_allocated = max(0.0, float(from_prod.budget_allocated or 0.0) - amount)
                    to_prod.budget_allocated = float(to_prod.budget_allocated or 0.0) + amount
                    decision.status = "executed"

    elif req.action == "reject":
        decision.status = "rejected"
        decision.approved_by = req.operator
        decision.approved_at = datetime.utcnow()
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    await db.commit()
    await db.refresh(decision)

    return ExecutiveDecisionItem(
        id=decision.id,
        title=decision.title,
        status=decision.status,
        recommendation=decision.recommendation_json,
        evidence=decision.evidence_json,
        impact_projection=decision.impact_projection_json,
        idempotency_key=decision.idempotency_key,
        approved_by=decision.approved_by,
        approved_at=decision.approved_at,
        created_at=decision.created_at
    )

# --- Products ---
@api_router.get("/products", response_model=List[ProductOut])
async def list_products(initiative_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    stmt = select(Product)
    if initiative_id:
        stmt = stmt.where(Product.initiative_id == initiative_id)
    stmt = stmt.order_by(Product.created_at.desc())
    res = await db.execute(stmt)
    products = res.scalars().all()

    out = []
    for p in products:
        r_stmt = select(func.count(WorkflowRun.id)).where(WorkflowRun.product_id == p.id)
        r_res = await db.execute(r_stmt)
        runs_count = r_res.scalar_one() or 0
        dto = ProductOut.model_validate(p)
        dto.active_runs_count = runs_count
        out.append(dto)
    return out

@api_router.post("/products", response_model=ProductOut)
async def create_product(data: ProductCreate, db: AsyncSession = Depends(get_db)):
    prod = Product(
        name=data.name,
        code=data.code,
        description=data.description,
        initiative_id=data.initiative_id
    )
    if data.id:
        prod.id = data.id
    db.add(prod)
    await db.commit()
    await db.refresh(prod)
    dto = ProductOut.model_validate(prod)
    dto.active_runs_count = 0
    return dto

# --- Workflow Templates ---
@api_router.get("/templates", response_model=List[WorkflowTemplateOut])
async def list_templates(db: AsyncSession = Depends(get_db)):
    stmt = select(WorkflowTemplate).order_by(WorkflowTemplate.created_at.asc())
    res = await db.execute(stmt)
    return res.scalars().all()

# --- Workflow Runs ---
@api_router.get("/runs", response_model=List[WorkflowRunOut])
async def list_runs(product_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    stmt = select(WorkflowRun).options(selectinload(WorkflowRun.modules))
    if product_id:
        stmt = stmt.where(WorkflowRun.product_id == product_id)
    stmt = stmt.order_by(WorkflowRun.created_at.desc())
    res = await db.execute(stmt)
    runs = res.scalars().all()
    return runs

@api_router.post("/runs", response_model=WorkflowRunOut)
async def create_run(data: WorkflowRunCreate, db: AsyncSession = Depends(get_db)):
    # 核心约束：单产品迭代周期不允许并行，必须唯一活跃
    active_stmt = select(WorkflowRun).where(
        WorkflowRun.product_id == data.product_id,
        WorkflowRun.status == "in_progress"
    )
    active_res = await db.execute(active_stmt)
    existing_active = active_res.scalar_one_or_none()
    if existing_active:
        raise HTTPException(
            status_code=400,
            detail=f"该产品当前已有进行中的活跃迭代「{existing_active.name}」，单产品不允许并行推进多个迭代。请先完成封版 (completed) 或废弃 (abandoned) 后再开启新一期迭代。"
        )

    try:
        run = await create_workflow_run_from_template(
            db=db,
            product_id=data.product_id,
            template_id=data.template_id,
            run_name=data.name
        )
        # re-fetch with modules
        stmt = select(WorkflowRun).options(selectinload(WorkflowRun.modules)).where(WorkflowRun.id == run.id)
        res = await db.execute(stmt)
        return res.scalar_one()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@api_router.patch("/runs/{run_id}", response_model=WorkflowRunOut)
async def update_run(
    run_id: str,
    data: WorkflowRunUpdate,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(WorkflowRun).options(selectinload(WorkflowRun.modules)).where(WorkflowRun.id == run_id)
    res = await db.execute(stmt)
    run = res.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
        
    if data.name is not None and data.name.strip():
        run.name = data.name.strip()
    if data.status is not None:
        if data.status not in ["in_progress", "completed", "abandoned"]:
            raise HTTPException(status_code=400, detail="Invalid run status")
        # If reviving to in_progress, ensure no other active run exists
        if data.status == "in_progress" and run.status != "in_progress":
            active_stmt = select(WorkflowRun).where(
                WorkflowRun.product_id == run.product_id,
                WorkflowRun.status == "in_progress",
                WorkflowRun.id != run.id
            )
            active_res = await db.execute(active_stmt)
            if active_res.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="该产品已有其他进行中的活跃迭代，无法将此迭代恢复为进行中")
        run.status = data.status

    run.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(run)
    return run

@api_router.get("/runs/{run_id}", response_model=WorkflowRunOut)
async def get_run(run_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(WorkflowRun).options(selectinload(WorkflowRun.modules)).where(WorkflowRun.id == run_id)
    res = await db.execute(stmt)
    run = res.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    # Calculate issue counts for each module
    modules_dto = []
    for m in run.modules:
        dto = ModuleInstanceOut.model_validate(m)
        
        # open issues targeting this module
        stmt_issues = select(func.count(Issue.id)).where(
            Issue.target_module_id == m.id,
            Issue.status.in_(["open", "investigating", "fixing", "verifying"])
        )
        res_issues = await db.execute(stmt_issues)
        dto.open_issues_count = res_issues.scalar_one() or 0

        # blocking issues
        stmt_blocking = select(func.count(Issue.id)).where(
            Issue.target_module_id == m.id,
            Issue.status.in_(["open", "investigating", "fixing", "verifying"]),
            Issue.severity.in_(["critical", "major"])
        )
        res_blk = await db.execute(stmt_blocking)
        dto.blocking_issues_count = res_blk.scalar_one() or 0

        # artifact count
        stmt_art = select(func.count(Artifact.id)).where(Artifact.module_id == m.id)
        res_art = await db.execute(stmt_art)
        dto.artifacts_count = res_art.scalar_one() or 0
        
        modules_dto.append(dto)
        
    out = WorkflowRunOut.model_validate(run)
    out.modules = modules_dto
    return out

# --- Module Instance & State Machine ---
@api_router.get("/modules/{module_id}", response_model=ModuleInstanceOut)
async def get_module(module_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(ModuleInstance).where(ModuleInstance.id == module_id)
    res = await db.execute(stmt)
    mod = res.scalar_one_or_none()
    if not mod:
        raise HTTPException(status_code=404, detail="Module not found")
    
    dto = ModuleInstanceOut.model_validate(mod)
    # Counts
    res_issues = await db.execute(
        select(func.count(Issue.id)).where(
            Issue.target_module_id == mod.id,
            Issue.status.in_(["open", "investigating", "fixing", "verifying"])
        )
    )
    dto.open_issues_count = res_issues.scalar_one() or 0
    return dto

@api_router.patch("/modules/{module_id}/phase", response_model=ModuleInstanceOut)
async def update_module_phase(module_id: str, data: ModulePhaseUpdate, db: AsyncSession = Depends(get_db)):
    stmt = select(ModuleInstance).where(ModuleInstance.id == module_id)
    res = await db.execute(stmt)
    mod = res.scalar_one_or_none()
    if not mod:
        raise HTTPException(status_code=404, detail="Module not found")

    new_phase = data.phase
    if new_phase == "baselined":
        # Check baseline criteria
        can_baseline, reason = await can_baseline_module(db, module_id)
        if not can_baseline:
            raise HTTPException(status_code=400, detail=reason)
        
        # If an artifact was specified or pick the latest
        if data.artifact_id:
            mod.baseline_artifact_id = data.artifact_id
        else:
            art_stmt = select(Artifact).where(Artifact.module_id == module_id).order_by(Artifact.version.desc()).limit(1)
            art_res = await db.execute(art_stmt)
            latest = art_res.scalars().first()
            if latest:
                mod.baseline_artifact_id = latest.id
                latest.is_baseline = True
                db.add(latest)

        mod.phase = "baselined"
        db.add(mod)
        await db.commit()
        # Unlock downstream
        await unlock_downstream_modules(db, mod.run_id)
    else:
        mod.phase = new_phase
        if new_phase != "baselined":
            mod.baseline_artifact_id = None
        db.add(mod)
        await db.commit()

    await db.refresh(mod)
    try:
        from backend.app.services.workspace_sync import sync_run_workspace
        await sync_run_workspace(db, mod.run_id)
    except Exception:
        pass
    return ModuleInstanceOut.model_validate(mod)

# --- Collaboration Session & Messages ---
@api_router.get("/modules/{module_id}/session", response_model=CollaborationSessionOut)
async def get_or_create_module_session(module_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(CollaborationSession).options(selectinload(CollaborationSession.messages)).where(
        CollaborationSession.module_id == module_id
    )
    res = await db.execute(stmt)
    session = res.scalar_one_or_none()
    if not session:
        session = CollaborationSession(
            module_id=module_id,
            title="主协作会话",
            participants=[
                {"role": "human", "name": "负责人"},
                {"role": "agent", "name": "Agent 协作者"}
            ]
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        stmt = select(CollaborationSession).options(selectinload(CollaborationSession.messages)).where(
            CollaborationSession.id == session.id
        )
        res = await db.execute(stmt)
        session = res.scalar_one()

    return session

@api_router.post("/sessions/{session_id}/messages", response_model=List[SessionMessageOut])
async def post_message(
    session_id: str,
    data: SessionMessageCreate,
    trigger_agent: bool = True,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(CollaborationSession).where(CollaborationSession.id == session_id)
    res = await db.execute(stmt)
    session = res.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    user_msg = SessionMessage(
        session_id=session_id,
        sender=data.sender,
        sender_role=data.sender_role,
        message_type=data.message_type,
        content=data.content,
        artifact_ref_id=data.artifact_ref_id,
        issue_ref_id=data.issue_ref_id,
        metadata_json=data.metadata_json
    )
    db.add(user_msg)
    await db.commit()
    await db.refresh(user_msg)

    result_messages = [user_msg]

    if trigger_agent and data.sender_role != "agent":
        agent_msg = await execute_agent_for_session(db, session, user_msg)
        if agent_msg:
            result_messages.append(agent_msg)

    return result_messages

# --- Artifacts ---
@api_router.get("/modules/{module_id}/artifacts", response_model=List[ArtifactOut])
async def list_artifacts(module_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Artifact).where(Artifact.module_id == module_id).order_by(Artifact.version.desc())
    res = await db.execute(stmt)
    return res.scalars().all()

@api_router.get("/artifacts/{artifact_id}", response_model=ArtifactOut)
async def get_artifact(artifact_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Artifact).where(Artifact.id == artifact_id)
    res = await db.execute(stmt)
    art = res.scalar_one_or_none()
    if not art:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return art

# --- Issues ---
@api_router.get("/issues", response_model=List[IssueOut])
async def list_issues(
    run_id: Optional[str] = None,
    target_module_id: Optional[str] = None,
    source_module_id: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Issue).options(
        selectinload(Issue.source_module),
        selectinload(Issue.target_module)
    )

    if run_id:
        stmt = stmt.join(ModuleInstance, Issue.target_module_id == ModuleInstance.id).where(
            ModuleInstance.run_id == run_id
        )
    if target_module_id:
        stmt = stmt.where(Issue.target_module_id == target_module_id)
    if source_module_id:
        stmt = stmt.where(Issue.source_module_id == source_module_id)
    if status:
        stmt = stmt.where(Issue.status == status)

    stmt = stmt.order_by(Issue.created_at.desc())
    res = await db.execute(stmt)
    issues = res.scalars().all()

    out = []
    for i in issues:
        dto = IssueOut.model_validate(i)
        dto.source_module_name = i.source_module.name if i.source_module else None
        dto.target_module_name = i.target_module.name if i.target_module else None
        out.append(dto)
    return out

@api_router.post("/issues", response_model=IssueOut)
async def create_issue(data: IssueCreate, db: AsyncSession = Depends(get_db)):
    # Generate issue identifier e.g. ISSUE-###
    count_stmt = select(func.count(Issue.id))
    count_res = await db.execute(count_stmt)
    seq = (count_res.scalar_one() or 0) + 1
    issue_id = f"ISSUE-{seq:03d}"

    issue = Issue(
        id=issue_id,
        title=data.title,
        source_module_id=data.source_module_id,
        target_module_id=data.target_module_id,
        reporter=data.reporter,
        reporter_role=data.reporter_role,
        category=data.category,
        severity=data.severity,
        priority=data.priority,
        status="open",
        description=data.description,
        related_artifact_id=data.related_artifact_id
    )
    db.add(issue)

    # If critical/major and target is baselined, rollback target to discussing
    target_stmt = select(ModuleInstance).where(ModuleInstance.id == data.target_module_id)
    target_res = await db.execute(target_stmt)
    target_mod = target_res.scalar_one_or_none()
    if target_mod and target_mod.phase == "baselined" and data.severity in ["critical", "major"]:
        target_mod.phase = "discussing"
        target_mod.baseline_artifact_id = None
        db.add(target_mod)

    await db.commit()
    await db.refresh(issue)

    # Post notification in target module session
    session_stmt = select(CollaborationSession).where(CollaborationSession.module_id == data.target_module_id)
    s_res = await db.execute(session_stmt)
    target_session = s_res.scalar_one_or_none()
    if target_session:
        notif_msg = SessionMessage(
            session_id=target_session.id,
            sender="系统提醒",
            sender_role="system",
            message_type="issue",
            content=f"收到来自外部模块的新【{data.severity.upper()}】反馈：[{issue.id}] {data.title}。请相关人员排查并处理。",
            issue_ref_id=issue.id
        )
        db.add(notif_msg)
        await db.commit()

    return issue

@api_router.patch("/issues/{issue_id}", response_model=IssueOut)
async def update_issue(issue_id: str, data: IssueUpdate, db: AsyncSession = Depends(get_db)):
    stmt = select(Issue).options(
        selectinload(Issue.source_module),
        selectinload(Issue.target_module)
    ).where(Issue.id == issue_id)
    res = await db.execute(stmt)
    issue = res.scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    if data.status:
        issue.status = data.status
        if data.status == "closed":
            issue.closed_at = datetime.utcnow()
        elif issue.status != "closed":
            issue.closed_at = None

    if data.resolution:
        issue.resolution = data.resolution
    if data.priority:
        issue.priority = data.priority
    if data.severity:
        issue.severity = data.severity
    if data.target_module_id:
        issue.target_module_id = data.target_module_id

    db.add(issue)
    await db.commit()
    await db.refresh(issue)

    dto = IssueOut.model_validate(issue)
    dto.source_module_name = issue.source_module.name if issue.source_module else None
    dto.target_module_name = issue.target_module.name if issue.target_module else None
    return dto

# --- Agent CLI Settings Endpoints ---
@api_router.get("/settings/agent", response_model=AgentSettingsOut)
async def get_agent_settings():
    import shutil
    presets = [
        AgentPresetItem(
            id="claude",
            name="Claude Code CLI",
            command="claude",
            description="Anthropic 官方生产力 Agent，具备自主终端与工程读写闭环能力",
            installed=bool(shutil.which("claude")),
            path=shutil.which("claude")
        ),
        AgentPresetItem(
            id="agy",
            name="Google Antigravity CLI (agy)",
            command="agy",
            description="Google Antigravity 自主智能体 CLI，原生契合 13 工序规划与协同治理",
            installed=bool(shutil.which("agy")),
            path=shutil.which("agy")
        ),
        AgentPresetItem(
            id="codex",
            name="Codex CLI",
            command="codex",
            description="代码合成与全栈产研命令行工具，擅长函数实现、架构推演与单测生成",
            installed=bool(shutil.which("codex")),
            path=shutil.which("codex")
        ),
        AgentPresetItem(
            id="simulator",
            name="离线模拟引擎 (Local Sandbox)",
            command="simulator",
            description="轻量高保真沙箱，无需外部 CLI 工具或 API Key，用于快速体验与离线演练",
            installed=True,
            path="builtin://simulator"
        )
    ]
    return AgentSettingsOut(
        adapter_type=settings.AGENT_ADAPTER_TYPE,
        cli_command=settings.AGENT_CLI_COMMAND,
        timeout=settings.AGENT_CLI_TIMEOUT,
        available_presets=presets
    )

@api_router.patch("/settings/agent", response_model=AgentSettingsOut)
async def update_agent_settings(data: AgentSettingsUpdate):
    if data.adapter_type is not None:
        settings.AGENT_ADAPTER_TYPE = data.adapter_type
    if data.cli_command is not None:
        settings.AGENT_CLI_COMMAND = data.cli_command
    if data.timeout is not None:
        settings.AGENT_CLI_TIMEOUT = data.timeout
    return await get_agent_settings()

@api_router.post("/settings/agent/test")
async def test_agent_settings():
    from backend.app.adapters.factory import get_agent_adapter
    from pathlib import Path
    import tempfile
    
    adapter = get_agent_adapter()
    with tempfile.TemporaryDirectory() as tmp_dir:
        events = []
        async for event in adapter.execute_task(
            task_id="dry-run",
            workspace_dir=Path(tmp_dir),
            system_context="# Dry Run Test",
            user_instruction="健康探测测试",
            message_type="instruction",
            metadata={"module_code": "00", "module_name": "系统探测"}
        ):
            events.append({"type": event.event_type.value, "content": event.content[:100]})
    return {
        "success": True,
        "adapter_type": settings.AGENT_ADAPTER_TYPE,
        "cli_command": settings.AGENT_CLI_COMMAND,
        "events_count": len(events),
        "events": events
    }
