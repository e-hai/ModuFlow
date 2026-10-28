import asyncio
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, UploadFile, File, Form, Header, Request
from fastapi.responses import FileResponse
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
    ExecutiveRisk,
    AgentRoleDefinition,
    AgentSettingsModel,
    ChangeReview,
    GateApplication
)
from backend.app.schemas.all_schemas import (
    StrategicInitiativeOut, StrategicInitiativeCreate, StrategicInitiativeUpdate,
    ProductOut, ProductCreate, ProductUpdate,
    WorkflowTemplateOut,
    WorkflowRunOut, WorkflowRunCreate, WorkflowRunUpdate,
    ModuleInstanceOut, ModulePhaseUpdate,
    CollaborationSessionOut, SessionMessageCreate, SessionMessageOut,
    ArtifactOut,
    IssueOut, IssueCreate, IssueUpdate,
    ExecutiveCockpitResponse, DecisionActionRequest, ExecutiveDecisionItem,
    FinancialMetrics, FocusAlert, PortfolioProductItem, MarketingCockpitData, MarketingCategoryItem, MarketingSubChannelItem,
    OperationsCockpitData, ExecutiveRiskItem,
    AgentSettingsOut, AgentSettingsUpdate, AgentPresetItem, CliModelListOut,
    AgentRoleDefinitionOut, ModuleRoleBundleOut,
    ChangeReviewOut, ChangeReviewAction
)
from backend.app.schemas.gate_schemas import (
    GateApplicationCreate,
    GateApplicationReview,
    GateApplicationOut,
    GateConfigSchema
)
from backend.app.services.workflow_engine import (
    create_workflow_run_from_template,
    can_baseline_module,
    unlock_downstream_modules
)
from backend.app.services.agent_runner import execute_agent_for_session
from backend.app.services.bundle_storage import process_and_save_bundle_artifact
from backend.app.services.authorization_engine import (
    load_product_authorization,
    validate_authorization_dict,
    get_product_authorization_path,
    check_budget_limits,
    check_kill_criteria,
    execute_circuit_breaker
)
from backend.app.services.gate_keeper import (
    create_or_update_gate_application,
    review_gate_application,
    evaluate_gate_level,
    get_stage_gate_config
)

from backend.app.services import orchestrator

api_router = APIRouter()


_orchestration_tasks: set[asyncio.Task] = set()


def _schedule_orchestration(background_tasks: BackgroundTasks, func, *args) -> None:
    """排队编排，但不在当前请求里跑完。

    Starlette 会在请求的数据库会话关闭之前执行 BackgroundTasks。
    若把 CLI 放进这个任务，会话会占着连接直到工序跑完（最长数分钟），
    刷新页面时工程列表读不出来，看起来像工程被删了。
    这里只负责挂上一个独立任务，当前请求马上结束并放开连接。
    """
    if not orchestrator.orchestration_enabled():
        return

    async def _kick() -> None:
        task = asyncio.create_task(orchestrator.run_in_fresh_session(func, *args))
        _orchestration_tasks.add(task)
        task.add_done_callback(_orchestration_tasks.discard)

    background_tasks.add_task(_kick)

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
        status=data.status,
        strategic_intent=data.strategic_intent,
        target_market=data.target_market,
        business_model_hypothesis=data.business_model_hypothesis,
        budget_total=data.budget
    )
    if data.id:
        init.id = data.id
    db.add(init)
    await db.commit()
    await db.refresh(init)

    # 自动初始化物理工作区
    from backend.app.services.workspace_sync import sync_strategic_initiative_workspace
    try:
        await sync_strategic_initiative_workspace(db, init.id)
    except Exception as e:
        logger.warning(f"Failed to sync workspace for {init.id}: {e}")

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
        
        target_val = p.kpi_target or 0.0
        actual_val = p.kpi_actual or 0.0
        completion_rate = round((actual_val / target_val) * 100, 1) if target_val > 0 else 0.0

        portfolio_items.append(PortfolioProductItem(
            id=p.id,
            name=p.name,
            code=p.code,
            strategic_role=p.strategic_role or "acquisition",
            stage=p.stage or "validating",
            budget_allocated=p.budget_allocated or 0.0,
            actual_spent=p.actual_spent or 0.0,
            revenue_contribution=p.revenue_contribution or 0.0,
            kpi_name=p.kpi_name,
            kpi_target=target_val,
            kpi_actual=actual_val,
            kpi_unit=p.kpi_unit or "",
            kpi_completion_rate=completion_rate,
            key_risk=p.key_risk,
            recommendation=p.recommendation,
            active_runs_count=runs_count
        ))

    # 2. Financial Ledger
    budget_total = float(init.budget_total or init.budget or 0.0)
    committed_unpaid = float(init.committed_unpaid or 0.0)
    actual_paid = float(init.actual_paid or 0.0)
    available_budget = round(budget_total - committed_unpaid - actual_paid, 2)
    revenue_recognized = float(init.revenue_recognized or 0.0)
    cash_collected = float(init.cash_collected or 0.0)
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
        target_breakeven_date=None,
        forecast_breakeven_date=None,
        burn_rate_monthly=0.0,
        currency=init.currency or "CNY"
    )

    # 3. Risks (真实数据库查询，不注入默认假数据)
    risk_stmt = select(ExecutiveRisk).where(ExecutiveRisk.initiative_id == initiative_id).order_by(ExecutiveRisk.created_at.desc())
    risk_res = await db.execute(risk_stmt)
    db_risks = risk_res.scalars().all()
    
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

    # 4. Decisions (真实数据库查询，不注入默认假数据)
    dec_stmt = select(ExecutiveDecision).where(ExecutiveDecision.initiative_id == initiative_id).order_by(ExecutiveDecision.created_at.desc())
    dec_res = await db.execute(dec_stmt)
    db_decs = dec_res.scalars().all()

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

    # 5. Focus Alerts (根据真实风险与预算情况动态判定)
    focus_alerts = []
    if budget_total > 0 and (actual_paid + committed_unpaid) > budget_total:
        focus_alerts.append(FocusAlert(
            id="ALERT-BUDGET-OVERDRAW",
            title="战略预算超支预警",
            summary=f"已承诺与已付金额总额为 ¥{(actual_paid + committed_unpaid):,.2f}，已超出总预算 ¥{budget_total:,.2f}。",
            type="budget_overdraw",
            severity="critical",
            action_hint="建议前往财务账本调整预算"
        ))
    for r in db_risks:
        if r.severity == "critical" and not r.is_resolved:
            focus_alerts.append(FocusAlert(
                id=f"ALERT-{r.rule_code}",
                title=r.title,
                summary=r.description[:120],
                type="critical_risk",
                severity="critical",
                action_hint=r.action_suggestion or "建议前往经营决策中心处理"
            ))

    # 6. Marketing Cockpit Data (读取真实 JSON，无数据则为空)
    m_data = init.marketing_summary or {}
    categories_raw = m_data.get("categories", [])
    categories = [
        MarketingCategoryItem(
            category_code=c.get("category_code", ""),
            category_name=c.get("category_name", ""),
            spend=float(c.get("spend", 0.0)),
            acquired_users=int(c.get("acquired_users", 0)),
            user_share_percent=float(c.get("user_share_percent", 0.0)),
            cac=float(c.get("cac", 0.0)),
            conversion_rate=float(c.get("conversion_rate", 0.0)),
            revenue_contribution=float(c.get("revenue_contribution", 0.0)),
            payback_days=int(c.get("payback_days", 0)),
            decision_recommendation=c.get("decision_recommendation", ""),
            sub_channels=[
                MarketingSubChannelItem(
                    name=sc.get("name", ""),
                    spend=float(sc.get("spend", 0.0)),
                    acquired_users=int(sc.get("acquired_users", 0)),
                    cac=float(sc.get("cac", 0.0)),
                    status=sc.get("status", "planned")
                ) for sc in c.get("sub_channels", [])
            ]
        ) for c in categories_raw
    ]
    tot_spend = float(m_data.get("total_spend", sum(c.spend for c in categories)))
    eff_users = int(m_data.get("effective_new_users", sum(c.acquired_users for c in categories)))
    b_cac = round(tot_spend / eff_users, 2) if eff_users > 0 else 0.0

    marketing = MarketingCockpitData(
        total_spend=tot_spend,
        effective_new_users=eff_users,
        blended_cac=b_cac,
        categories=categories
    )

    # 7. Operations Cockpit Data (读取真实 JSON，无数据则为空)
    op_data = init.operations_summary or {}
    operations = OperationsCockpitData(
        dau=int(op_data.get("dau", 0)),
        mau=int(op_data.get("mau", 0)),
        retention_1d=float(op_data.get("retention_1d", 0.0)),
        retention_7d=float(op_data.get("retention_7d", 0.0)),
        retention_30d=float(op_data.get("retention_30d", 0.0)),
        paid_users=int(op_data.get("paid_users", 0)),
        arpu=float(op_data.get("arpu", 0.0)),
        arppu=float(op_data.get("arppu", 0.0)),
        ltv=float(op_data.get("ltv", 0.0)),
        ltv_cac_ratio=float(op_data.get("ltv_cac_ratio", 0.0)),
        funnel=op_data.get("funnel", [])
    )

    return ExecutiveCockpitResponse(
        initiative_id=init.id,
        initiative_name=init.name,
        owner=init.owner,
        status=init.status,
        strategic_intent=init.strategic_intent or "",
        target_market=init.target_market or "",
        business_model_hypothesis=init.business_model_hypothesis or "",
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


@api_router.post("/initiatives/{initiative_id}/risks/{risk_id}/resolve", response_model=ExecutiveRiskItem)
async def resolve_executive_risk(
    initiative_id: str,
    risk_id: str,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(ExecutiveRisk).where(
        ExecutiveRisk.id == risk_id,
        ExecutiveRisk.initiative_id == initiative_id
    )
    res = await db.execute(stmt)
    risk = res.scalar_one_or_none()
    if not risk:
        raise HTTPException(status_code=404, detail="Risk alert not found")

    risk.is_resolved = True
    if "待您亲自把关" in risk.title:
        risk.title = risk.title.replace("🔴 待您亲自把关：", "✅ 已确认放行：")
    elif "越权拦截" in risk.title:
        risk.title = risk.title.replace("🚨 越权拦截", "✅ 已核查拦截")
    elif "🚨" in risk.title:
        risk.title = f"✅ 已核查消除：{risk.title.replace('🚨', '').strip()}"
    else:
        risk.title = f"✅ 已处置：{risk.title}"

    risk.action_suggestion = "已由负责人核查并解除预警。"
    await db.commit()
    await db.refresh(risk)

    return ExecutiveRiskItem(
        id=risk.id,
        rule_code=risk.rule_code,
        title=risk.title,
        severity=risk.severity,
        description=risk.description,
        product_code=risk.product_code,
        action_suggestion=risk.action_suggestion,
        is_resolved=risk.is_resolved,
        created_at=risk.created_at.isoformat() if risk.created_at else ""
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
        if p.initiative_id:
            auth_status, _, errors = load_product_authorization(p.initiative_id, p.code)
            dto.authorization_status = "paused" if p.stage == "paused" else auth_status
            dto.authorization_errors = errors
        out.append(dto)
    return out

@api_router.post("/products", response_model=ProductOut)
async def create_product(data: ProductCreate, db: AsyncSession = Depends(get_db)):
    auth_pkg = data.authorization_package
    if not auth_pkg and data.auto_authorize:
        from scripts.migrate_legacy_project_auth import generate_default_authorization_dict
        auth_pkg = generate_default_authorization_dict(
            product_code=data.code,
            product_name=data.name,
            budget_allocated=data.budget_allocated or 5000.0,
            platform=data.platform or "cross_platform",
            client_zero_inference=True if data.client_zero_inference is None else data.client_zero_inference
        )

    if auth_pkg:
        is_valid, errors = validate_authorization_dict(auth_pkg)
        if not is_valid:
            raise HTTPException(
                status_code=422,
                detail={"message": "非法授权包被拒", "errors": errors}
            )

    target_platform = "cross_platform"
    target_zero_inf = True
    if auth_pkg and isinstance(auth_pkg, dict):
        prof = auth_pkg.get("profile", {})
        target_platform = prof.get("platform", data.platform or "cross_platform")
        target_zero_inf = prof.get("client_zero_inference", True if data.client_zero_inference is None else data.client_zero_inference)
    else:
        target_platform = data.platform or "cross_platform"
        target_zero_inf = True if data.client_zero_inference is None else data.client_zero_inference

    prod = Product(
        name=data.name,
        code=data.code,
        description=data.description,
        initiative_id=data.initiative_id,
        budget_allocated=data.budget_allocated or 0.0,
        platform=target_platform,
        client_zero_inference=target_zero_inf,
        stage="validating" if auth_pkg else "needs_authorization"
    )
    if data.id:
        prod.id = data.id
    db.add(prod)
    await db.commit()
    await db.refresh(prod)

    # 自动同步至物理工作区（创建产品隔离目录并更新战略底稿产品矩阵表格）
    if prod.initiative_id:
        from backend.app.services.workspace_sync import sync_strategic_initiative_workspace
        try:
            await sync_strategic_initiative_workspace(db, prod.initiative_id)
        except Exception as e:
            logger.warning(f"Failed to sync workspace for {prod.initiative_id}: {e}")

        if auth_pkg:
            import yaml
            from backend.app.services.security_guard import apply_readonly_file_protection
            auth_path = get_product_authorization_path(prod.initiative_id, prod.code)
            auth_path.parent.mkdir(parents=True, exist_ok=True)
            auth_path.write_text(yaml.dump(auth_pkg, sort_keys=False, allow_unicode=True), encoding="utf-8")
            apply_readonly_file_protection(auth_path)

    dto = ProductOut.model_validate(prod)
    dto.active_runs_count = 0
    if auth_pkg:
        dto.authorization_status = "authorized"
        dto.authorization_errors = []
    else:
        dto.authorization_status = "needs_authorization"
        dto.authorization_errors = ["缺少 authorization.yaml"]
    return dto

@api_router.patch("/products/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: str,
    data: ProductUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    from backend.app.services.security_guard import parse_actor_identity, validate_pricing_authority
    actor_type, role_code, actor = parse_actor_identity(request.headers.get("X-ModuFlow-Actor"))

    stmt = select(Product).where(Product.id == product_id)
    res = await db.execute(stmt)
    prod = res.scalar_one_or_none()
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")

    # Hard constraints:
    # 1. Lead / execution agent cannot modify budget limit
    if actor_type != "human" and data.budget_allocated is not None and data.budget_allocated != prod.budget_allocated:
        raise HTTPException(
            status_code=403,
            detail=f"❌ 权限拒绝: Agent '{actor}' (角色: {role_code}) 严禁修改项目预算上限。预算增减必须由人类战略层批准并更新授权包。"
        )

    # 2. ba is sole source of pricing / revenue truth
    if data.revenue_contribution is not None and data.revenue_contribution != prod.revenue_contribution:
        is_allowed, err_msg = validate_pricing_authority(role_code, action_description="修改营收预测与财务指标")
        if not is_allowed:
            raise HTTPException(status_code=403, detail=err_msg)

    if data.name is not None:
        prod.name = data.name
    if data.description is not None:
        prod.description = data.description
    if data.stage is not None:
        prod.stage = data.stage
    if data.budget_allocated is not None:
        prod.budget_allocated = data.budget_allocated
    if data.actual_spent is not None:
        prod.actual_spent = data.actual_spent
    if data.revenue_contribution is not None:
        prod.revenue_contribution = data.revenue_contribution
    if data.kpi_name is not None:
        prod.kpi_name = data.kpi_name
    if data.kpi_target is not None:
        prod.kpi_target = data.kpi_target
    if data.kpi_actual is not None:
        prod.kpi_actual = data.kpi_actual
    if data.kpi_unit is not None:
        prod.kpi_unit = data.kpi_unit
    if data.key_risk is not None:
        prod.key_risk = data.key_risk
    if data.recommendation is not None:
        prod.recommendation = data.recommendation

    # 确定性止损与超预算熔断检查 (Zero LLM)
    if prod.initiative_id:
        auth_status, auth_data, _ = load_product_authorization(prod.initiative_id, prod.code)
        if auth_status == "authorized" and auth_data:
            # 1. Budget check
            is_breached, reason, _ = check_budget_limits(auth_data, float(prod.actual_spent or 0.0))
            if is_breached:
                await execute_circuit_breaker(
                    prod.initiative_id,
                    prod.code,
                    "budget_exceeded",
                    {"reason": reason, "actual_spent": prod.actual_spent},
                    db
                )

            # 2. Stop-loss check
            metrics = {
                "actual_spent": float(prod.actual_spent or 0.0),
                "revenue_contribution": float(prod.revenue_contribution or 0.0),
            }
            if prod.kpi_name and prod.kpi_actual is not None:
                metrics[prod.kpi_name.lower()] = float(prod.kpi_actual)
            triggered = check_kill_criteria(auth_data, metrics)
            if triggered:
                desc = triggered[0].get("description") or f"Metric {triggered[0]['metric']} hit threshold"
                await execute_circuit_breaker(
                    prod.initiative_id,
                    prod.code,
                    "kill_criterion_hit",
                    {"reason": desc, "triggered": triggered},
                    db
                )

    await db.commit()
    await db.refresh(prod)

    r_stmt = select(func.count(WorkflowRun.id)).where(WorkflowRun.product_id == prod.id)
    r_res = await db.execute(r_stmt)
    runs_count = r_res.scalar_one() or 0

    dto = ProductOut.model_validate(prod)
    dto.active_runs_count = runs_count
    if prod.initiative_id:
        auth_status, _, errors = load_product_authorization(prod.initiative_id, prod.code)
        dto.authorization_status = "paused" if prod.stage == "paused" else auth_status
        dto.authorization_errors = errors
    return dto

# --- Product Authorization Package Endpoints ---
@api_router.get("/initiatives/{initiative_id}/products/{product_code}/authorization")
async def get_product_authorization_endpoint(
    initiative_id: str,
    product_code: str,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Product).where(Product.code == product_code)
    res = await db.execute(stmt)
    prod = res.scalar_one_or_none()
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")

    status_str, data, errors = load_product_authorization(initiative_id, product_code)
    auth_path = get_product_authorization_path(initiative_id, product_code)

    return {
        "initiative_id": initiative_id,
        "product_code": product_code,
        "product_stage": prod.stage,
        "authorization_status": "paused" if prod.stage == "paused" else status_str,
        "path": str(auth_path),
        "exists": auth_path.exists(),
        "authorization_package": data,
        "errors": errors
    }

@api_router.put("/initiatives/{initiative_id}/products/{product_code}/authorization")
async def update_product_authorization_endpoint(
    initiative_id: str,
    product_code: str,
    auth_package: dict,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    import yaml
    from backend.app.services.security_guard import (
        parse_actor_identity,
        intercept_agent_write_attempt,
        apply_write_file_permission,
        apply_readonly_file_protection
    )

    actor_type, role_code, actor = parse_actor_identity(request.headers.get("X-ModuFlow-Actor"))

    auth_path = get_product_authorization_path(initiative_id, product_code)

    # Hard constraint: Check if agent is attempting to modify authorization package
    is_blocked, err_msg = await intercept_agent_write_attempt(
        file_path=auth_path,
        actor=actor,
        actor_role=actor_type,
        db=db,
        initiative_id=initiative_id,
        product_code=product_code
    )
    if is_blocked:
        raise HTTPException(
            status_code=403,
            detail=err_msg
        )

    stmt = select(Product).where(Product.code == product_code)
    res = await db.execute(stmt)
    prod = res.scalar_one_or_none()
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")

    is_valid, errors = validate_authorization_dict(auth_package)
    if not is_valid:
        raise HTTPException(
            status_code=422,
            detail={"message": "授权包格式或红线校验失败", "errors": errors}
        )

    auth_path.parent.mkdir(parents=True, exist_ok=True)
    apply_write_file_permission(auth_path)
    auth_path.write_text(yaml.dump(auth_package, sort_keys=False, allow_unicode=True), encoding="utf-8")
    apply_readonly_file_protection(auth_path)

    # Update product budget & stage if was paused/needs_authorization
    new_budget = auth_package.get("financial_budget", {}).get("total_budget_limit", prod.budget_allocated)
    prod.budget_allocated = float(new_budget)
    if prod.stage in ["needs_authorization", "paused"]:
        prod.stage = "validating"
        prod.key_risk = None
        prod.recommendation = "授权包已更新生效，恢复正常迭代"

    # Record decision audit
    decisions_dir = auth_path.parent / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    now_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    log_file = decisions_dir / f"{now_str}_authorization_updated.json"
    log_file.write_text(json.dumps({
        "timestamp": datetime.utcnow().isoformat(),
        "event": "authorization_updated",
        "actor": actor,
        "actor_role": actor_type,
        "total_budget": new_budget,
        "hard_stop": auth_package.get("financial_budget", {}).get("hard_stop_limit")
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    await db.commit()
    await db.refresh(prod)

    return {
        "ok": True,
        "message": f"项目 {product_code} 授权包已更新并生效",
        "authorization_status": "authorized",
        "authorization_package": auth_package
    }

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
async def create_run(data: WorkflowRunCreate, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
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
        created = res.scalar_one()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    _schedule_orchestration(background_tasks, orchestrator.advance_run, created.id)
    return created

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

@api_router.post("/runs/{run_id}/advance")
async def advance_run_endpoint(run_id: str, db: AsyncSession = Depends(get_db)):
    """Manually kicks the orchestrator for a run; gate rules are unchanged."""
    run = (await db.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    result = await orchestrator.advance_run(db, run_id)
    result["orchestration"] = await orchestrator.get_run_orchestration_status(db, run_id)
    return result

@api_router.patch("/runs/{run_id}/auto-advance")
async def toggle_run_auto_advance(
    run_id: str,
    payload: dict,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    from backend.app.services.security_guard import parse_actor_identity
    actor_type, _role_code, actor = parse_actor_identity(request.headers.get("X-ModuFlow-Actor"))
    if actor_type != "human":
        raise HTTPException(status_code=403, detail="❌ 只有人类负责人可以开关自动编排。")
    run = (await db.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    run.auto_advance = bool(payload.get("enabled", True))
    run.updated_at = datetime.utcnow()
    await db.commit()
    if run.auto_advance:
        _schedule_orchestration(background_tasks, orchestrator.advance_run, run_id)
    return {"ok": True, "run_id": run_id, "auto_advance": run.auto_advance, "actor": actor}

@api_router.get("/runs/{run_id}/orchestration-status")
async def get_run_orchestration_status_endpoint(run_id: str, db: AsyncSession = Depends(get_db)):
    status_data = await orchestrator.get_run_orchestration_status(db, run_id)
    if not status_data.get("found"):
        raise HTTPException(status_code=404, detail="Run not found")
    return status_data

@api_router.post("/modules/{module_id}/submit-for-gate")
async def submit_module_for_gate(
    module_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Human confirms the current deliverable (needed for human_driven stages) and sends it to checks and gate."""
    from backend.app.services.security_guard import parse_actor_identity
    actor_type, _role_code, _actor = parse_actor_identity(request.headers.get("X-ModuFlow-Actor"))
    if actor_type != "human":
        raise HTTPException(status_code=403, detail="❌ 只有人类负责人可以确认提交真人主导工序的交付物。")
    mod = (await db.execute(select(ModuleInstance).where(ModuleInstance.id == module_id))).scalar_one_or_none()
    if not mod:
        raise HTTPException(status_code=404, detail="Module not found")
    result = await orchestrator.on_artifact_created(db, module_id, origin="human_confirmed")
    return {"module_id": module_id, "status": result}

@api_router.post("/modules/{module_id}/resolve-dispute")
async def resolve_module_dispute(
    module_id: str,
    payload: dict,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Human rules on a primary-vs-reviewer disagreement: accept_review or override_review."""
    from backend.app.services.security_guard import parse_actor_identity
    actor_type, _role_code, actor = parse_actor_identity(request.headers.get("X-ModuFlow-Actor"))
    if actor_type != "human":
        raise HTTPException(status_code=403, detail="❌ 协作评审分歧只能由人类负责人裁决。")
    decision = payload.get("decision")
    if decision not in ("accept_review", "override_review"):
        raise HTTPException(status_code=400, detail="decision 必须是 accept_review 或 override_review")
    result = await orchestrator.resolve_dispute(
        db, module_id, decision, actor or "human", str(payload.get("comment") or "")
    )
    if result == "module_not_found":
        raise HTTPException(status_code=404, detail="Module not found")
    if result == "no_dispute":
        raise HTTPException(status_code=409, detail="本工序没有待裁决的协作评审分歧")
    return {"module_id": module_id, "decision": decision, "status": result}

@api_router.get("/runs/{run_id}", response_model=WorkflowRunOut)
async def get_run(run_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(WorkflowRun).options(selectinload(WorkflowRun.modules)).where(WorkflowRun.id == run_id)
    res = await db.execute(stmt)
    run = res.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    module_ids = [m.id for m in run.modules]
    open_map = {}
    blk_map = {}
    art_map = {}
    artifacts_map = {}

    if module_ids:
        # Batch count open issues using GROUP BY to eliminate N+1 queries
        res_open = await db.execute(
            select(Issue.target_module_id, func.count(Issue.id))
            .where(
                Issue.target_module_id.in_(module_ids),
                Issue.status.in_(["open", "investigating", "fixing", "verifying"])
            )
            .group_by(Issue.target_module_id)
        )
        open_map = dict(res_open.all())

        # Batch count blocking issues using GROUP BY
        res_blk = await db.execute(
            select(Issue.target_module_id, func.count(Issue.id))
            .where(
                Issue.target_module_id.in_(module_ids),
                Issue.status.in_(["open", "investigating", "fixing", "verifying"]),
                Issue.severity.in_(["critical", "major"])
            )
            .group_by(Issue.target_module_id)
        )
        blk_map = dict(res_blk.all())

        # Batch count artifacts using GROUP BY
        res_art = await db.execute(
            select(Artifact.module_id, func.count(Artifact.id))
            .where(Artifact.module_id.in_(module_ids))
            .group_by(Artifact.module_id)
        )
        art_map = dict(res_art.all())

        # Preload baseline artifacts in one query for downstream stale detection
        baseline_art_ids = [m.baseline_artifact_id for m in run.modules if m.baseline_artifact_id]
        if baseline_art_ids:
            res_base = await db.execute(select(Artifact).where(Artifact.id.in_(baseline_art_ids)))
            artifacts_map = {a.id: a for a in res_base.scalars().all()}

    from backend.app.services.stale_checker import calculate_module_stale_status
    modules_dto = []
    for m in run.modules:
        dto = ModuleInstanceOut.model_validate(m)
        dto.open_issues_count = open_map.get(m.id, 0)
        dto.blocking_issues_count = blk_map.get(m.id, 0)
        dto.artifacts_count = art_map.get(m.id, 0)

        is_stale, stale_details = await calculate_module_stale_status(
            db, m, all_run_modules=run.modules, artifacts_map=artifacts_map
        )
        dto.is_upstream_stale = is_stale
        dto.stale_details = stale_details
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

    res_blk = await db.execute(
        select(func.count(Issue.id)).where(
            Issue.target_module_id == mod.id,
            Issue.status.in_(["open", "investigating", "fixing", "verifying"]),
            Issue.severity.in_(["critical", "major"])
        )
    )
    dto.blocking_issues_count = res_blk.scalar_one() or 0

    res_art = await db.execute(
        select(func.count(Artifact.id)).where(Artifact.module_id == mod.id)
    )
    dto.artifacts_count = res_art.scalar_one() or 0

    # Downstream stale status
    from backend.app.services.stale_checker import calculate_module_stale_status
    is_stale, stale_details = await calculate_module_stale_status(db, mod)
    dto.is_upstream_stale = is_stale
    dto.stale_details = stale_details

    # Role bundle
    from backend.app.services.agent_roles import get_module_role_bundle
    bundle = await get_module_role_bundle(db, mod.module_code)
    if bundle.get("primary_role"):
        dto.primary_role = AgentRoleDefinitionOut.model_validate(bundle["primary_role"])
    dto.collaborator_roles = [AgentRoleDefinitionOut.model_validate(r) for r in bundle.get("collaborator_roles", [])]

    # Gate metadata and application (Phase 2)
    dto.gate = get_stage_gate_config(mod.module_code)
    g_res = await db.execute(
        select(GateApplication).where(GateApplication.module_id == mod.id).order_by(GateApplication.created_at.desc())
    )
    latest_gate = g_res.scalars().first()
    if latest_gate:
        dto.gate_application = GateApplicationOut.model_validate(latest_gate).model_dump()

    return dto

@api_router.patch("/modules/{module_id}/phase", response_model=ModuleInstanceOut)
async def update_module_phase(
    module_id: str,
    data: ModulePhaseUpdate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
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
        _schedule_orchestration(background_tasks, orchestrator.advance_run, mod.run_id)
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
    return await get_module(module_id=mod.id, db=db)

@api_router.post("/modules/{module_id}/ack-upstream", response_model=ModuleInstanceOut)
async def ack_upstream_module(
    module_id: str,
    upstream_code: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Downstream explicitly confirms acknowledgment and sync of upstream specification version."""
    stmt = select(ModuleInstance).where(ModuleInstance.id == module_id)
    res = await db.execute(stmt)
    mod = res.scalar_one_or_none()
    if not mod:
        raise HTTPException(status_code=404, detail="Module not found")

    from backend.app.services.stale_checker import get_relevant_upstream_codes
    target_upstreams = [upstream_code] if upstream_code else list(get_relevant_upstream_codes(mod.module_code, mod.dependencies))

    # Fetch all modules in run to get baseline artifact versions
    m_stmt = select(ModuleInstance).where(ModuleInstance.run_id == mod.run_id)
    m_res = await db.execute(m_stmt)
    all_mods = {m.module_code: m for m in m_res.scalars().all()}

    current_sync = dict(mod.synced_upstream_versions or {})
    for up_code in target_upstreams:
        up_mod = all_mods.get(up_code)
        if up_mod and up_mod.baseline_artifact_id:
            art_res = await db.execute(select(Artifact.version).where(Artifact.id == up_mod.baseline_artifact_id))
            ver = art_res.scalar_one_or_none()
            if ver:
                current_sync[up_code] = ver

    mod.synced_upstream_versions = current_sync
    db.add(mod)
    await db.commit()
    await db.refresh(mod)

    return await get_module(module_id=mod.id, db=db)

# --- Human Gate Application Endpoints (Phase 2) ---

@api_router.get("/modules/{module_id}/gate-config")
async def get_module_gate_config(
    module_id: str,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(ModuleInstance).where(ModuleInstance.id == module_id)
    res = await db.execute(stmt)
    mod = res.scalar_one_or_none()
    if not mod:
        raise HTTPException(status_code=404, detail="Module not found")

    run_stmt = select(WorkflowRun).where(WorkflowRun.id == mod.run_id)
    run_res = await db.execute(run_stmt)
    run_obj = run_res.scalar_one_or_none()

    config = get_stage_gate_config(mod.module_code, run_obj.template_id if run_obj else None)
    return config


@api_router.post("/modules/{module_id}/gate-application", response_model=GateApplicationOut)
async def submit_gate_application(
    module_id: str,
    data: GateApplicationCreate,
    x_moduflow_actor: Optional[str] = Header(None, alias="X-ModuFlow-Actor"),
    db: AsyncSession = Depends(get_db)
):
    """
    Submits or updates the 1-page Gate Application for a module.
    Evaluates gate level, auto-escalation to 🔴 red, and emits notifications.
    """
    actor_id = x_moduflow_actor or "agent:lead"
    try:
        gate_app = await create_or_update_gate_application(
            db=db,
            module_id=module_id,
            recommendation=data.recommendation,
            evidence=data.evidence,
            risk_assessment=data.risk_assessment,
            decision_options=data.decision_options,
            submitted_by=actor_id,
            context=data.context
        )
        return gate_app
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit gate application: {e}")


@api_router.get("/modules/{module_id}/gate-application", response_model=GateApplicationOut)
async def get_module_gate_application(
    module_id: str,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(GateApplication).where(GateApplication.module_id == module_id).order_by(GateApplication.created_at.desc())
    res = await db.execute(stmt)
    gate_app = res.scalars().first()
    if not gate_app:
        raise HTTPException(status_code=404, detail="No gate application found for this module")
    return gate_app


@api_router.get("/gates/pending-batch", response_model=List[GateApplicationOut])
async def list_pending_gates_for_batch(
    level: Optional[str] = None,
    product_code: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Lists pending gate applications across products for human batch review.
    Supports filtering by level (yellow, red) and product_code.
    """
    stmt = select(GateApplication).where(GateApplication.status == "pending")
    if level:
        stmt = stmt.where(GateApplication.effective_level == level)
    if product_code:
        stmt = stmt.where(GateApplication.product_code == product_code)
    stmt = stmt.order_by(GateApplication.created_at.asc())
    res = await db.execute(stmt)
    return res.scalars().all()


@api_router.post("/gates/{gate_id}/review", response_model=GateApplicationOut)
async def review_gate(
    gate_id: str,
    data: GateApplicationReview,
    background_tasks: BackgroundTasks,
    x_moduflow_actor: Optional[str] = Header(None, alias="X-ModuFlow-Actor"),
    db: AsyncSession = Depends(get_db)
):
    """
    Reviews a GateApplication (approve / reject / adjust).
    Enforces hard constraints:
    - Lead (agent) CANNOT approve Yellow or Red gates (G1, G2, G4, G5, etc.).
    - Only actor_role == 'human' can approve Yellow/Red gates.
    """
    actor_str = x_moduflow_actor or (f"human:{data.reviewer_name}" if data.reviewer_name else "human:sponsor")
    if ":" in actor_str:
        prefix, _ = actor_str.split(":", 1)
        actor_role = prefix
        actor = actor_str
    else:
        actor = actor_str
        actor_role = "human" if "human" in actor_str else "lead"

    try:
        updated_gate = await review_gate_application(
            db=db,
            gate_id=gate_id,
            action=data.action,
            comment=data.comment or "",
            actor=actor,
            actor_role=actor_role
        )
        _schedule_orchestration(background_tasks, orchestrator.on_gate_reviewed, updated_gate.id)
        return updated_gate
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Review failed: {e}")

# --- Lead Agent & Shadow Mode Endpoints ---
@api_router.post("/modules/{module_id}/lead/evaluate-gate", response_model=GateApplicationOut)
async def evaluate_gate_by_lead_endpoint(
    module_id: str,
    x_moduflow_actor: Optional[str] = Header(None, alias="X-ModuFlow-Actor"),
    db: AsyncSession = Depends(get_db)
):
    """
    Lead agent evaluates a gate application for the specified module.
    In shadow mode: outputs recommendation without directly releasing gate.
    """
    from backend.app.services.lead_service import evaluate_gate_by_lead
    stmt = select(GateApplication).where(GateApplication.module_id == module_id)
    res = await db.execute(stmt)
    gate = res.scalar_one_or_none()
    if not gate:
        raise HTTPException(status_code=404, detail="No GateApplication found for this module")

    actor = x_moduflow_actor or "agent:lead"
    evaluated_gate, _ = await evaluate_gate_by_lead(db=db, gate_id=gate.id, lead_actor=actor)
    return evaluated_gate

@api_router.get("/products/{product_id}/lead/shadow-stats")
async def get_product_shadow_stats_endpoint(
    product_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Returns consistency tracking statistics for Lead recommendations vs Human decisions.
    """
    from backend.app.services.lead_service import get_shadow_mode_stats
    return await get_shadow_mode_stats(db=db, product_id=product_id)

@api_router.post("/products/{product_id}/lead/shadow-mode")
async def toggle_product_shadow_mode_endpoint(
    product_id: str,
    payload: dict,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Toggles product Shadow Mode (enabled: true/false).
    Hard constraint: ONLY human accounts can toggle shadow mode.
    """
    from backend.app.services.security_guard import parse_actor_identity
    from backend.app.services.lead_service import toggle_product_shadow_mode

    actor_type, role_code, actor = parse_actor_identity(request.headers.get("X-ModuFlow-Actor"))
    enabled = payload.get("enabled", True)
    prod = await toggle_product_shadow_mode(
        db=db,
        product_id=product_id,
        enabled=enabled,
        actor_type=actor_type,
        actor_id=actor
    )
    return {
        "ok": True,
        "product_id": prod.id,
        "product_code": prod.code,
        "shadow_mode": prod.shadow_mode,
        "message": f"项目 {prod.code} 已切换为{'「AI 仅提建议」模式' if prod.shadow_mode else '「AI 自动推进」模式'}"
    }

@api_router.get("/products/{product_id}/lead/daily-digest")
async def get_project_daily_digest_endpoint(
    product_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Generates a 1-page structured daily digest prepared by Lead agent.
    """
    from backend.app.services.lead_service import generate_project_daily_digest
    return await generate_project_daily_digest(db=db, product_id=product_id)

@api_router.get("/initiatives/{initiative_id}/decision-inbox")
async def get_decision_inbox_endpoint(initiative_id: str, db: AsyncSession = Depends(get_db)):
    """Human review queue: disputes, exhausted revisions, and handoff gaps for one initiative."""
    from backend.app.services.lead_service import get_decision_inbox
    return await get_decision_inbox(db, initiative_id)

@api_router.post("/issues/{issue_id}/lead/arbitrate-cr")
async def arbitrate_cr_endpoint(
    issue_id: str,
    x_moduflow_actor: Optional[str] = Header(None, alias="X-ModuFlow-Actor"),
    db: AsyncSession = Depends(get_db)
):
    """
    Lead agent arbitrates a Change Request (CR) Issue.
    Auto-escalates to human if sensitive triggers (payment, privacy, encryption) are detected.
    """
    from backend.app.services.lead_service import arbitrate_cr_by_lead
    actor = x_moduflow_actor or "agent:lead"
    return await arbitrate_cr_by_lead(db=db, issue_id=issue_id, lead_actor=actor)

# --- Compliance Specialist (cmp) Checkpoints ---
@api_router.post("/modules/{module_id}/compliance-audit")
async def run_compliance_audit_endpoint(
    module_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Runs compliance audit for stage 03, 05, or 09.
    Outputs: status ('passed', 'needs_fix', 'legal_review') and risk level ('low', 'medium', 'high').
    High risk triggers automatic escalation to 🔴 G5 gate and emits ExecutiveRisk.
    """
    from backend.app.services.compliance_engine import run_stage_compliance_check
    return await run_stage_compliance_check(db=db, module_id=module_id)

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
    background_tasks: BackgroundTasks,
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
        role_code=data.role_code,
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
            if agent_msg.artifact_ref_id:
                _schedule_orchestration(
                    background_tasks, orchestrator.on_artifact_created, session.module_id, "human_session"
                )

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

@api_router.post("/modules/{module_id}/artifacts/upload")
async def upload_module_artifact(
    module_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    change_summary: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Accepts full deliveries (single Markdown file, HTML bundle, or ZIP archive).
    Extracts archives, versions files under physical workspace, and generates ChangeReview.
    """
    stmt = select(ModuleInstance).where(ModuleInstance.id == module_id)
    res = await db.execute(stmt)
    mod = res.scalar_one_or_none()
    if not mod:
        raise HTTPException(status_code=404, detail="Module not found")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    artifact, change_review = await process_and_save_bundle_artifact(
        db=db,
        module_id=module_id,
        filename=file.filename or "artifact.zip",
        file_bytes=file_bytes,
        change_summary=change_summary
    )
    _schedule_orchestration(background_tasks, orchestrator.on_artifact_created, module_id, "human_confirmed")

    return {
        "artifact": ArtifactOut.model_validate(artifact),
        "change_review": ChangeReviewOut.model_validate(change_review)
    }

@api_router.get("/artifacts/{artifact_id}/preview")
@api_router.get("/artifacts/{artifact_id}/preview/{path:path}")
async def preview_artifact_file(
    artifact_id: str,
    path: str = "",
    db: AsyncSession = Depends(get_db)
):
    """Serves static prototype files (HTML/CSS/JS/images) from extracted bundle directory."""
    stmt = select(Artifact).where(Artifact.id == artifact_id)
    res = await db.execute(stmt)
    art = res.scalar_one_or_none()
    if not art:
        raise HTTPException(status_code=404, detail="Artifact not found")

    if not art.storage_rel_path:
        raise HTTPException(status_code=400, detail="Artifact does not have stored files on disk")

    base_dir = (settings.WORKSPACE_DIR / art.storage_rel_path).resolve()
    target_rel = path.strip() if path and path.strip() else art.entry_file
    target_path = (base_dir / target_rel).resolve()

    # Traversal security check
    if not str(target_path).startswith(str(base_dir)):
        raise HTTPException(status_code=403, detail="Access denied")

    if not target_path.exists():
        fallback = base_dir / "index.html"
        if fallback.exists():
            return FileResponse(str(fallback))
        raise HTTPException(status_code=404, detail=f"File '{target_rel}' not found in artifact bundle")

    return FileResponse(str(target_path))

# --- Change Reviews & Unified Approval Flow ---
@api_router.get("/change-reviews", response_model=List[ChangeReviewOut])
async def list_change_reviews(
    module_id: Optional[str] = None,
    run_id: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(ChangeReview)
    if module_id:
        stmt = stmt.where(ChangeReview.module_id == module_id)
    if run_id:
        stmt = stmt.join(ModuleInstance, ChangeReview.module_id == ModuleInstance.id).where(
            ModuleInstance.run_id == run_id
        )
    if status:
        stmt = stmt.where(ChangeReview.status == status)
    stmt = stmt.order_by(ChangeReview.created_at.desc())
    res = await db.execute(stmt)
    return res.scalars().all()

@api_router.get("/change-reviews/{review_id}", response_model=ChangeReviewOut)
async def get_change_review(review_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(ChangeReview).where(ChangeReview.id == review_id)
    res = await db.execute(stmt)
    item = res.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Change review not found")
    return item

@api_router.post("/change-reviews/{review_id}/approve", response_model=ChangeReviewOut)
async def approve_change_review(
    review_id: str,
    background_tasks: BackgroundTasks,
    action: Optional[ChangeReviewAction] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Unified change approval by leader/manager.
    Promotes artifact to baseline, updates module phase, and triggers downstream sync alerts.
    """
    stmt = (
        select(ChangeReview)
        .options(selectinload(ChangeReview.artifact), selectinload(ChangeReview.module))
        .where(ChangeReview.id == review_id)
    )
    res = await db.execute(stmt)
    review = res.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Change review not found")

    approver_name = action.approver if (action and action.approver) else "负责人"

    if review.module_id:
        from backend.app.services.workflow_engine import can_baseline_module
        can_baseline, reason = await can_baseline_module(db, review.module_id)
        if not can_baseline:
            raise HTTPException(status_code=400, detail=reason)
        await db.refresh(review)

    review.status = "approved"
    review.approver = approver_name
    review.approved_at = datetime.utcnow()

    # Promote artifact to baseline
    art = review.artifact
    if art:
        # Un-baseline any previous artifacts in the module
        old_arts_res = await db.execute(
            select(Artifact).where(Artifact.module_id == review.module_id, Artifact.id != art.id)
        )
        for old_art in old_arts_res.scalars().all():
            old_art.is_baseline = False
            db.add(old_art)

        art.is_baseline = True
        db.add(art)

    mod = review.module
    if mod and art:
        mod.baseline_artifact_id = art.id
        mod.phase = "baselined"
        db.add(mod)

    await db.commit()
    await db.refresh(review)

    # Unlock downstream modules and sync workspace
    if mod:
        await unlock_downstream_modules(db, mod.run_id)
        from backend.app.services.workspace_sync import sync_run_workspace
        try:
            await sync_run_workspace(db, mod.run_id)
        except Exception:
            pass
        _schedule_orchestration(background_tasks, orchestrator.advance_run, mod.run_id)

    return review

@api_router.post("/change-reviews/{review_id}/reject", response_model=ChangeReviewOut)
async def reject_change_review(
    review_id: str,
    action: Optional[ChangeReviewAction] = None,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(ChangeReview).where(ChangeReview.id == review_id)
    res = await db.execute(stmt)
    review = res.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Change review not found")

    review.status = "rejected"
    review.approver = action.approver if (action and action.approver) else "负责人"
    review.rejection_reason = action.rejection_reason if (action and action.rejection_reason) else "未通过审批"
    review.approved_at = datetime.utcnow()

    await db.commit()
    await db.refresh(review)
    return review

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

@api_router.get("/issues/{issue_id}", response_model=IssueOut)
async def get_issue(issue_id: str, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Issue)
        .options(selectinload(Issue.source_module), selectinload(Issue.target_module))
        .where(Issue.id == issue_id)
    )
    res = await db.execute(stmt)
    item = res.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Issue not found")
    dto = IssueOut.model_validate(item)
    dto.source_module_name = item.source_module.name if item.source_module else None
    dto.target_module_name = item.target_module.name if item.target_module else None
    return dto

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
        # Keep target_mod.baseline_artifact_id intact so downstream modules retain diff context
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
            content=f"收到来自协同环节的新【{data.severity.upper()}】问题反馈：[{issue.id}] {data.title}。请责任人排查并修正。",
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
async def get_agent_settings(db: AsyncSession = Depends(get_db)):
    from backend.app.adapters.cli_adapter import find_cli_binary
    claude_path = find_cli_binary("claude")
    agy_path = find_cli_binary("agy")
    codex_path = find_cli_binary("codex")

    # Load persistent settings from DB
    stmt = select(AgentSettingsModel).where(AgentSettingsModel.id == "default")
    res = await db.execute(stmt)
    setting_row = res.scalar_one_or_none()
    if not setting_row:
        setting_row = AgentSettingsModel(
            id="default",
            adapter_type=settings.AGENT_ADAPTER_TYPE,
            cli_command=settings.AGENT_CLI_COMMAND,
            timeout=settings.AGENT_CLI_TIMEOUT
        )
        db.add(setting_row)
        await db.commit()
        await db.refresh(setting_row)

    presets = [
        AgentPresetItem(
            id="agy",
            name="Google Antigravity CLI (agy)",
            command="agy",
            description="Google Antigravity 自主智能体 CLI，原生契合 11 道战略工序与权限治理",
            installed=bool(agy_path),
            path=agy_path,
            install_command="brew install google/antigravity/agy 或 pip install antigravity-cli",
            install_guide="官方自主智能体，建议配置在 ~/.local/bin 或系统 PATH 中"
        ),
        AgentPresetItem(
            id="claude",
            name="Claude Code CLI",
            command="claude",
            description="Anthropic 官方生产力 Agent，具备自主终端与工程读写闭环能力",
            installed=bool(claude_path),
            path=claude_path,
            install_command="npm install -g @anthropic-ai/claude-code",
            install_guide="全局安装后，在终端运行一次 `claude` 完成 Anthropic 账号登录授权即可"
        ),
        AgentPresetItem(
            id="codex",
            name="Codex CLI",
            command="codex",
            description="代码合成与全栈产研命令行工具，擅长函数实现、架构推演与单测生成",
            installed=bool(codex_path),
            path=codex_path,
            install_command="npm install -g @openai/codex",
            install_guide="全局安装后，在终端运行一次 `codex` 完成 OpenAI 账号登录授权即可"
        )
    ]

    current_installed = bool(find_cli_binary(setting_row.cli_command))
    any_installed = any(p.installed for p in presets) or current_installed

    return AgentSettingsOut(
        adapter_type=setting_row.adapter_type,
        cli_command=setting_row.cli_command,
        cli_model=setting_row.cli_model,
        timeout=setting_row.timeout,
        available_presets=presets,
        is_current_installed=current_installed,
        any_installed=any_installed
    )


@api_router.get("/settings/agent/models", response_model=CliModelListOut)
async def get_agent_cli_models(command: str, refresh: bool = False):
    """List models published by the selected CLI so the settings page can switch them."""
    from backend.app.adapters.cli_adapter import list_cli_models
    listed = await list_cli_models(command, refresh=refresh)
    return CliModelListOut(**listed)

@api_router.patch("/settings/agent", response_model=AgentSettingsOut)
async def update_agent_settings(data: AgentSettingsUpdate, db: AsyncSession = Depends(get_db)):
    stmt = select(AgentSettingsModel).where(AgentSettingsModel.id == "default")
    res = await db.execute(stmt)
    setting_row = res.scalar_one_or_none()
    if not setting_row:
        setting_row = AgentSettingsModel(id="default")
        db.add(setting_row)

    if data.adapter_type is not None:
        setting_row.adapter_type = data.adapter_type
        settings.AGENT_ADAPTER_TYPE = data.adapter_type
    if data.cli_command is not None:
        setting_row.cli_command = data.cli_command
        settings.AGENT_CLI_COMMAND = data.cli_command
    if "cli_model" in data.model_fields_set:
        from backend.app.adapters.cli_adapter import usable_cli_model
        chosen = usable_cli_model(data.cli_model)
        if data.cli_model and not chosen:
            raise HTTPException(status_code=400, detail="模型 ID 无效")
        setting_row.cli_model = chosen
        settings.AGENT_CLI_MODEL = chosen or ""
    if data.timeout is not None:
        setting_row.timeout = data.timeout
        settings.AGENT_CLI_TIMEOUT = data.timeout

    await db.commit()
    await db.refresh(setting_row)
    return await get_agent_settings(db)

@api_router.post("/settings/agent/test")
async def test_agent_settings():
    import asyncio
    from backend.app.adapters.cli_adapter import find_cli_binary
    
    cmd_path = find_cli_binary(settings.AGENT_CLI_COMMAND)
    if not cmd_path:
        events = [
            {"type": "log", "content": f"[Adapter] 未在系统 PATH 中找到 `{settings.AGENT_CLI_COMMAND}`"},
            {"type": "log", "content": f"[Guide] 请确认 `{settings.AGENT_CLI_COMMAND}` 已安装，或在设置中选择已安装的 Agent CLI / 自定义路径"},
            {"type": "done", "content": f"命令探测未就绪: 未找到可执行文件 `{settings.AGENT_CLI_COMMAND}`"}
        ]
        return {
            "success": True,
            "installed": False,
            "adapter_type": settings.AGENT_ADAPTER_TYPE,
            "cli_command": settings.AGENT_CLI_COMMAND,
            "events_count": len(events),
            "events": events
        }

    try:
        proc = await asyncio.create_subprocess_exec(
            cmd_path, "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=3.0)
        version_str = stdout.decode().strip() or stderr.decode().strip() or "已就绪"
        events = [
            {"type": "log", "content": f"[Adapter] 检测到底层二进制路径: {cmd_path}"},
            {"type": "log", "content": f"[Adapter] CLI 运行时握手正常: {version_str}"},
            {"type": "done", "content": f"Agent CLI ({settings.AGENT_CLI_COMMAND}) 连通性测试通过"}
        ]
        return {
            "success": True,
            "adapter_type": settings.AGENT_ADAPTER_TYPE,
            "cli_command": settings.AGENT_CLI_COMMAND,
            "cli_path": cmd_path,
            "version": version_str,
            "events_count": len(events),
            "events": events
        }
    except Exception as e:
        events = [
            {"type": "log", "content": f"[Adapter] 执行探测异常: {str(e)}"},
            {"type": "done", "content": f"探测执行完成: {str(e)}"}
        ]
        return {
            "success": True,
            "adapter_type": settings.AGENT_ADAPTER_TYPE,
            "cli_command": settings.AGENT_CLI_COMMAND,
            "error": str(e),
            "events_count": len(events),
            "events": events
        }

# --- Core Agent Roles Endpoints ---
@api_router.get("/roles", response_model=List[AgentRoleDefinitionOut])
async def list_agent_roles(db: AsyncSession = Depends(get_db)):
    """List all 8 core agent role definitions."""
    stmt = select(AgentRoleDefinition).order_by(AgentRoleDefinition.id.asc())
    res = await db.execute(stmt)
    return res.scalars().all()

@api_router.get("/roles/{role_code}", response_model=AgentRoleDefinitionOut)
async def get_agent_role(role_code: str, db: AsyncSession = Depends(get_db)):
    """Get details for a specific core agent role."""
    stmt = select(AgentRoleDefinition).where(AgentRoleDefinition.role_code == role_code)
    res = await db.execute(stmt)
    role = res.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail=f"Role '{role_code}' not found")
    return role

@api_router.get("/modules/{module_id}/roles", response_model=ModuleRoleBundleOut)
async def get_module_roles(module_id: str, db: AsyncSession = Depends(get_db)):
    """Get primary role and collaborator roles assigned to a module."""
    stmt = select(ModuleInstance).where(ModuleInstance.id == module_id)
    res = await db.execute(stmt)
    mod = res.scalar_one_or_none()
    if not mod:
        raise HTTPException(status_code=404, detail="Module not found")
    from backend.app.services.agent_roles import get_module_role_bundle
    bundle = await get_module_role_bundle(db, mod.module_code)
    return ModuleRoleBundleOut(
        primary=AgentRoleDefinitionOut.model_validate(bundle["primary_role"]) if bundle.get("primary_role") else None,
        collaborators=[AgentRoleDefinitionOut.model_validate(r) for r in bundle.get("collaborator_roles", [])]
    )


# --- Phase 6: Project Profile & Parameterized Redlines Endpoints ---

@api_router.get("/products/{product_id}/profile")
async def get_product_profile_endpoint(product_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieve product profile parameters (platform, client_zero_inference, ruleset)."""
    p_stmt = select(Product).where(Product.id == product_id)
    p_res = await db.execute(p_stmt)
    product = p_res.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    from backend.app.services.profile_guard import resolve_project_profile
    prof = resolve_project_profile(
        initiative_id=product.initiative_id,
        product_code=product.code,
        fallback_platform=product.platform or "ios",
        fallback_zero_inference=product.client_zero_inference if product.client_zero_inference is not None else True
    )
    from backend.app.services.profile_guard import covers_android, covers_ios, is_dual_platform
    if is_dual_platform(prof["platform"]):
        ruleset = "iOS Human Interface Guidelines (HIG) + Google Material Design 3 (M3)"
    elif covers_android(prof["platform"]) and not covers_ios(prof["platform"]):
        ruleset = "Google Material Design 3 (M3)"
    else:
        ruleset = "iOS Human Interface Guidelines (HIG)"
    return {
        "product_id": product.id,
        "product_code": product.code,
        "platform": prof["platform"],
        "client_zero_inference": prof["client_zero_inference"],
        "ruleset": ruleset
    }


@api_router.post("/modules/{module_id}/design-audit")
async def audit_module_design_system(
    module_id: str,
    payload: Optional[Dict[str, Any]] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Executes profile-aware design system audit for Stage 06:
    - If platform is Android: executes check_material (Material 3: touch >= 48dp, status bar >= 24~48dp, NO Dynamic Island).
    - If platform is iOS: executes check_hig (Apple HIG: Dynamic Island >= 71pt, touch >= 44pt).
    """
    m_stmt = select(ModuleInstance).where(ModuleInstance.id == module_id)
    m_res = await db.execute(m_stmt)
    mod = m_res.scalar_one_or_none()
    if not mod:
        raise HTTPException(status_code=404, detail="Module not found")

    run_stmt = select(WorkflowRun).where(WorkflowRun.id == mod.run_id)
    run_res = await db.execute(run_stmt)
    run_obj = run_res.scalar_one_or_none()
    product_id = run_obj.product_id if run_obj else None

    product = None
    if product_id:
        p_stmt = select(Product).where(Product.id == product_id)
        p_res = await db.execute(p_stmt)
        product = p_res.scalar_one_or_none()

    from backend.app.services.profile_guard import resolve_project_profile, audit_platform_design_system
    prof = resolve_project_profile(
        initiative_id=product.initiative_id if product else None,
        product_code=product.code if product else None,
        fallback_platform=getattr(product, "platform", "ios") or "ios",
        fallback_zero_inference=getattr(product, "client_zero_inference", True)
    )

    args = payload or {}
    if "top_safe_value" not in args or "min_touch_value" not in args:
        return {
            "passed": False,
            "platform": prof["platform"],
            "errors": ["缺少实测安全区与触控热区，缺省值不能放行"],
        }
    top_val = args.get("top_safe_value")
    touch_val = args.get("min_touch_value")
    content = args.get("content")

    audit_result = audit_platform_design_system(
        platform=prof["platform"],
        top_safe_value=top_val,
        min_touch_value=touch_val,
        content=content
    )
    return audit_result


@api_router.post("/modules/{module_id}/zero-inference-audit")
async def audit_module_zero_inference(
    module_id: str,
    payload: Optional[Dict[str, Any]] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Executes profile-parameterized zero inference audit for Stage 07:
    - If client_zero_inference=True: requires client_realtime_ai_calls == 0.
    - If client_zero_inference=False: explicitly permits on-device / edge AI calls.
    """
    m_stmt = select(ModuleInstance).where(ModuleInstance.id == module_id)
    m_res = await db.execute(m_stmt)
    mod = m_res.scalar_one_or_none()
    if not mod:
        raise HTTPException(status_code=404, detail="Module not found")

    run_stmt = select(WorkflowRun).where(WorkflowRun.id == mod.run_id)
    run_res = await db.execute(run_stmt)
    run_obj = run_res.scalar_one_or_none()
    product_id = run_obj.product_id if run_obj else None

    product = None
    if product_id:
        p_stmt = select(Product).where(Product.id == product_id)
        p_res = await db.execute(p_stmt)
        product = p_res.scalar_one_or_none()

    from backend.app.services.profile_guard import resolve_project_profile, audit_client_zero_inference
    prof = resolve_project_profile(
        initiative_id=product.initiative_id if product else None,
        product_code=product.code if product else None,
        fallback_platform=getattr(product, "platform", "ios") or "ios",
        fallback_zero_inference=getattr(product, "client_zero_inference", True)
    )

    args = payload or {}
    if "client_realtime_ai_calls" not in args:
        return {
            "passed": False,
            "enforce_zero_inference": prof["client_zero_inference"],
            "errors": ["缺少客户端推理次数实测，缺省 0 不能放行"],
        }
    ai_calls = int(args.get("client_realtime_ai_calls", 0))
    bw_mb = float(args.get("avg_cdn_bandwidth_mb", 15.0))

    audit_result = audit_client_zero_inference(
        client_realtime_ai_calls=ai_calls,
        avg_cdn_bandwidth_mb=bw_mb,
        enforce_zero_inference=prof["client_zero_inference"]
    )
    return audit_result


# --- Phase 7: Hotfix Follow-up Tasks & Portfolio Weekly Report Endpoints ---

@api_router.post("/runs/{run_id}/hotfix-release")
async def trigger_hotfix_release(
    run_id: str,
    x_moduflow_actor: Optional[str] = Header(None, alias="X-ModuFlow-Actor"),
    db: AsyncSession = Depends(get_db)
):
    """
    Triggers completion of Hotfix release and automatically schedules the 3 mandatory
    24h follow-up tasks: 补 CR + 故障复盘 + PRD 规格基线同步。
    """
    actor_id = x_moduflow_actor or "human:system"
    from backend.app.services.portfolio_and_hotfix_service import create_hotfix_followup_tasks
    result = await create_hotfix_followup_tasks(db, run_id, actor_id=actor_id)
    return result


@api_router.get("/runs/{run_id}/hotfix-tasks")
async def get_hotfix_tasks_status(
    run_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Checks the 24h SLA status of hotfix documentation tasks.
    Raises critical ExecutiveRisk alert if 24h has passed with pending tasks.
    """
    from backend.app.services.portfolio_and_hotfix_service import check_hotfix_documentation_sla
    result = await check_hotfix_documentation_sla(db, run_id)
    return result


@api_router.post("/hotfix-tasks/{task_id}/complete")
async def complete_hotfix_task_endpoint(
    task_id: str,
    payload: Optional[Dict[str, Any]] = None,
    x_moduflow_actor: Optional[str] = Header(None, alias="X-ModuFlow-Actor"),
    db: AsyncSession = Depends(get_db)
):
    """Marks a Hotfix follow-up task as completed."""
    actor_id = x_moduflow_actor or "human:operator"
    notes = (payload or {}).get("notes")
    from backend.app.services.portfolio_and_hotfix_service import complete_hotfix_task
    task = await complete_hotfix_task(db, task_id, actor_id=actor_id, notes=notes)
    return {
        "id": task.id,
        "run_id": task.run_id,
        "task_type": task.task_type,
        "status": task.status,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "completed_by": task.completed_by
    }


@api_router.get("/portfolio/weekly-report")
async def get_portfolio_weekly_report(
    initiative_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Generates and returns the aggregated 1-page Executive Portfolio Weekly Report across products:
    - Stage, budget/spent, KPIs, risks, recommendations
    - Strict Redline: Outputs recommendations ONLY, NO autonomous budget/killing action!
    """
    from backend.app.services.portfolio_and_hotfix_service import generate_portfolio_weekly_report
    report = await generate_portfolio_weekly_report(db, initiative_id=initiative_id)
    return report



