"""
ModuFlow Human Gate Keeper Service (backend/app/services/gate_keeper.py)

Enforces:
1. Gate Level Classification: 🟢 green (lead self-approves) | 🟡 yellow (human batch) | 🔴 red (human must approve immediately)
2. Deterministic Auto-Escalation to 🔴 red: payment, privacy, user data, budget exceeded, lead permission modification, public statement.
3. One-Page Gate Application Lifecycle: recommendation, evidence, risk assessment, decision options.
4. Hard Redline Enforcement:
   - Lead (agent) CANNOT approve Yellow or Red gates (G1, G2, G4, G5, etc.).
   - Stage 09 (G4 Release) MUST have a recorded human approval before baselining/release.
5. Audit logging in decisions/ and instant 🔴 notifications via ExecutiveRisk.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from backend.app.core.config import settings
from backend.app.models.entities import (
    ModuleInstance,
    WorkflowRun,
    Product,
    GateApplication,
    ExecutiveRisk
)
from backend.app.services.agent_roles import STAGE_ROLE_CONFIGS, HOTFIX_GATE_CONFIG


# Mandatory trigger keywords for automatic escalation to 🔴 RED
RED_ESCALATION_KEYWORDS = {
    "payment": ["payment", "pay", "subscription", "pricing", "checkout", "stripe", "iap", "storekit", "支付", "充值", "定价阶梯", "退款"],
    "privacy": ["privacy", "gdpr", "ccpa", "tracking", "idfa", "ad_id", "att", "隐私", "个人隐私", "个人信息", "权限申请"],
    "user_data": ["user_data", "pii", "contacts", "location_tracking", "用户数据", "敏感数据", "通讯录", "精准定位", "生物识别"],
    "encryption": ["encryption", "keychain", "keystore", "aes", "rsa", "加密", "密钥存储", "安全凭证"],
    "modify_lead_permissions": ["modify_permissions", "modify_redlines", "lead_permissions", "修改权限", "修改红线", "越权放行"],
    "public_statement": ["public_statement", "press_release", "对外公开表态", "官方声明", "媒体发布"],
    "compliance_high_risk": ["legal_review", "compliance_violation", "需法务", "合规高风险", "侵权", "商标侵权", "未成年人隐私", "赌博违规", "g5_escalation"],
}


def get_stage_gate_config(module_code: str, template_id: Optional[str] = None) -> Dict[str, Any]:
    if template_id == "hotfix" and module_code == "07":
        return dict(HOTFIX_GATE_CONFIG)
    cfg = STAGE_ROLE_CONFIGS.get(module_code, {})
    gate = cfg.get("gate")
    if gate:
        return dict(gate)
    return {
        "name": f"工序 {module_code} 门禁",
        "level": "green",
        "approver": "lead",
        "conditions": ["符合标准工程规范"],
        "auto_escalate_triggers": []
    }


def evaluate_gate_level(
    module_code: str,
    context: Optional[Dict[str, Any]] = None,
    template_id: Optional[str] = None,
    platform: str = "ios",
    client_zero_inference: bool = True
) -> Dict[str, Any]:
    """
    Evaluates gate level and checks automatic escalation rules (Zero LLM).
    Returns:
        dict with {gate_name, base_level, base_approver, effective_level, effective_approver, is_escalated, escalation_reasons, conditions}
    """
    base_cfg = get_stage_gate_config(module_code, template_id)
    base_level = base_cfg["level"]
    base_approver = base_cfg["approver"]

    effective_level = base_level
    effective_approver = base_approver
    is_escalated = False
    escalation_reasons: List[str] = []

    ctx = context or {}
    context_str = json.dumps(ctx, ensure_ascii=False).lower()

    # 1. Check budget exceeded trigger -> 🔴 RED
    if ctx.get("is_budget_exceeded") or ctx.get("budget_exceeded"):
        is_escalated = True
        effective_level = "red"
        effective_approver = "human"
        escalation_reasons.append("触发超预算熔断红线，关口强制升级为 🔴 red (必须人类审批)")

    # 2. Check keyword-based mandatory red escalation triggers
    for trigger_cat, keywords in RED_ESCALATION_KEYWORDS.items():
        matched = []
        if ctx.get(f"is_{trigger_cat}_related") or ctx.get(trigger_cat):
            matched.append(trigger_cat)
        else:
            for kw in keywords:
                if kw in context_str:
                    matched.append(kw)
                    break
        if matched:
            is_escalated = True
            effective_level = "red"
            effective_approver = "human"
            escalation_reasons.append(f"检测到涉及【{trigger_cat}】关键敏感事项 (匹配项: {', '.join(matched[:3])})，关口强制升级为 🔴 red (必须人类审批)")

    # 3. Stage 05 specific: data dictionary / schema change -> 🔴 RED
    if module_code == "05":
        if ctx.get("data_dictionary_schema_change") or "schema_change" in context_str or "数据字典变更" in context_str:
            is_escalated = True
            effective_level = "red"
            effective_approver = "human"
            escalation_reasons.append("工序 05 涉及核心业务数据字典/实体变更，关口自动升级为 🔴 red (必须人类审批)")

    # 4. Stage 11 specific: major version / pivot -> 🟡 YELLOW
    if module_code == "11" and effective_level == "green":
        if ctx.get("is_major_version") or "major_version" in context_str or "大版本" in context_str:
            is_escalated = True
            effective_level = "yellow"
            effective_approver = "human"
            escalation_reasons.append("工序 11 涉及大版本规划 (Major Version)，关口由 🟢 升级为 🟡 yellow (需人类批量审批)")

    from backend.app.services.agent_roles import get_stage_gate_conditions
    dynamic_conditions = get_stage_gate_conditions(
        module_code,
        platform=platform,
        client_zero_inference=client_zero_inference
    )

    return {
        "gate_name": base_cfg["name"],
        "base_level": base_level,
        "base_approver": base_approver,
        "effective_level": effective_level,
        "effective_approver": effective_approver,
        "is_escalated": is_escalated,
        "escalation_reasons": escalation_reasons,
        "conditions": dynamic_conditions
    }


async def create_or_update_gate_application(
    db: AsyncSession,
    module_id: str,
    recommendation: str,
    evidence: List[Any],
    risk_assessment: str,
    decision_options: Optional[List[str]] = None,
    submitted_by: str = "agent:pm",
    context: Optional[Dict[str, Any]] = None
) -> GateApplication:
    """
    Creates or updates the 1-page GateApplication for a module.
    Automatically evaluates gate level, escalation rules, writes physical decision log,
    and creates instant 🔴 ExecutiveRisk notification if red.
    """
    m_stmt = select(ModuleInstance).where(ModuleInstance.id == module_id)
    m_res = await db.execute(m_stmt)
    mod = m_res.scalar_one_or_none()
    if not mod:
        raise ValueError(f"Module {module_id} not found")

    run_stmt = select(WorkflowRun).where(WorkflowRun.id == mod.run_id)
    run_res = await db.execute(run_stmt)
    run_obj = run_res.scalar_one_or_none()
    if not run_obj:
        raise ValueError(f"WorkflowRun {mod.run_id} not found")

    p_stmt = select(Product).where(Product.id == run_obj.product_id)
    p_res = await db.execute(p_stmt)
    product = p_res.scalar_one_or_none()
    product_code = product.code if product else "UNKNOWN"
    initiative_id = product.initiative_id if product else "platform"

    # Evaluate gate level with project profile
    prod_platform = getattr(product, "platform", "ios") or "ios"
    prod_zero_inf = getattr(product, "client_zero_inference", True)
    if prod_zero_inf is None:
        prod_zero_inf = True

    gate_eval = evaluate_gate_level(
        mod.module_code,
        context,
        run_obj.template_id,
        platform=prod_platform,
        client_zero_inference=prod_zero_inf
    )

    # Check for existing gate application
    g_stmt = select(GateApplication).where(GateApplication.module_id == module_id)
    g_res = await db.execute(g_stmt)
    gate = g_res.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    options = decision_options or ["approve", "reject", "adjust"]

    if not gate:
        gate = GateApplication(
            module_id=module_id,
            run_id=run_obj.id,
            product_code=product_code,
            module_code=mod.module_code,
            gate_name=gate_eval["gate_name"],
            base_level=gate_eval["base_level"],
            effective_level=gate_eval["effective_level"],
            is_escalated=gate_eval["is_escalated"],
            escalation_reasons=gate_eval["escalation_reasons"],
            status="pending",
            recommendation=recommendation,
            evidence=evidence,
            risk_assessment=risk_assessment,
            decision_options=options,
            submitted_by=submitted_by,
            submitted_at=now
        )
        db.add(gate)
    else:
        gate.gate_name = gate_eval["gate_name"]
        gate.base_level = gate_eval["base_level"]
        gate.effective_level = gate_eval["effective_level"]
        gate.is_escalated = gate_eval["is_escalated"]
        gate.escalation_reasons = gate_eval["escalation_reasons"]
        gate.status = "pending"
        gate.recommendation = recommendation
        gate.evidence = evidence
        gate.risk_assessment = risk_assessment
        gate.decision_options = options
        gate.submitted_by = submitted_by
        gate.submitted_at = now
        gate.reviewed_by = None
        gate.reviewer_role = None
        gate.reviewed_at = None
        gate.review_comment = None
        gate.decision_action = None

    await db.flush()

    # If Red level: emit instant 🔴 notification (ExecutiveRisk)
    if gate.effective_level == "red" and initiative_id:
        # Format human-friendly intuitive gate action title
        gate_display_name = gate.gate_name
        if "G4" in gate_display_name or "提审" in gate_display_name:
            gate_human_action = "应用商店提审发布"
        elif "G1" in gate_display_name or "立项" in gate_display_name:
            gate_human_action = "立项方向决策"
        elif "G2" in gate_display_name or "外测" in gate_display_name:
            gate_human_action = "假门市场外测决议"
        elif "05" in mod.module_code or "prd" in gate_display_name.lower():
            gate_human_action = "产品需求规格审核"
            if gate.is_escalated and any(k in gate.escalation_reasons for k in ["payment", "user_data", "privacy"]):
                gate_human_action += " (涉及内购支付与隐私)"
        elif "P0" in gate_display_name or "热修" in gate_display_name:
            gate_human_action = "紧急热修上线审批 (P0)"
        else:
            gate_human_action = gate_display_name

        prod_display = f"{product.name} ({product_code})" if product and product.name else product_code

        clean_rec = recommendation.replace("申请 G4 提审发布审批！", "申请商店提审发布").replace("G4 提审门禁", "商店提审关口")

        risk = ExecutiveRisk(
            initiative_id=initiative_id,
            rule_code=f"GATE_RED_{mod.module_code}",
            title=f"🔴 待您亲自把关：{gate_human_action} · {prod_display}",
            severity="critical",
            description=(
                f"产品「{prod_display}」在【工序 {mod.module_code}：{mod.name}】达到重大决策节点。"
                f"{'检测到敏感项触发必须由您亲自签署的条件: ' + '; '.join(gate.escalation_reasons) if gate.is_escalated else '该工序涉及重大对外发布决策，按安全规则必须由人类负责人亲自确认。'}\n"
                f"项目总控建议: {clean_rec[:120]}"
            ),
            product_code=product_code,
            action_suggestion="请核对合规审查材料与应急回滚预案后确认放行。",
            is_resolved=False
        )
        db.add(risk)

    # Write one-page application log to physical disk decisions/
    decisions_dir = Path(settings.WORKSPACE_DIR) / initiative_id / "products" / product_code / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")
    file_path = decisions_dir / f"{timestamp_str}_gate_{mod.module_code}_application.json"
    file_path.write_text(json.dumps({
        "gate_id": gate.id,
        "module_code": mod.module_code,
        "gate_name": gate.gate_name,
        "base_level": gate.base_level,
        "effective_level": gate.effective_level,
        "is_escalated": gate.is_escalated,
        "escalation_reasons": gate.escalation_reasons,
        "recommendation": recommendation,
        "evidence": evidence,
        "risk_assessment": risk_assessment,
        "submitted_by": submitted_by,
        "submitted_at": now.isoformat()
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    await db.commit()
    await db.refresh(gate)
    return gate


async def review_gate_application(
    db: AsyncSession,
    gate_id: str,
    action: str,
    comment: str = "",
    actor: str = "human:sponsor",
    actor_role: str = "human"
) -> GateApplication:
    """
    Reviews a GateApplication.
    HARD REDLINE:
    - Lead (agent) CANNOT approve Yellow or Red gates.
    - Only actor_role == 'human' can approve Yellow/Red gates.
    """
    g_stmt = select(GateApplication).where(GateApplication.id == gate_id)
    g_res = await db.execute(g_stmt)
    gate = g_res.scalar_one_or_none()
    if not gate:
        raise ValueError(f"GateApplication {gate_id} not found")

    if action not in ["approve", "reject", "adjust"]:
        raise ValueError(f"Invalid decision action: '{action}'. Must be approve, reject, or adjust.")

    # HARD CONSTRAINT: Agent (including lead) CANNOT approve Yellow or Red gates
    is_human_required = gate.effective_level in ["yellow", "red"] or gate.gate_name in [
        "G1 立项方向", "G2 外测决议", "G4 提审门禁", "P0 热修关口", "LTV/CAC 商业关口", "买量预算门禁"
    ]

    if is_human_required and actor_role != "human":
        raise PermissionError(
            f"❌ 权限拒绝: 当前关口「{gate.gate_name}」级别为 {gate.effective_level.upper()}，"
            f"系统硬约束严禁 Agent (包括 lead) 审批黄级/红级关口。必须由人类负责人 (actor_role='human') 审批。"
        )

    # For green gate: lead, qa (for stage 08), or human can approve
    if gate.effective_level == "green":
        if actor_role not in ["human", "lead", "qa"]:
            raise PermissionError(f"❌ 权限拒绝: 角色 '{actor_role}' 无权审批绿级关口。")

    now = datetime.now(timezone.utc)
    if action == "approve":
        gate.status = "approved"
    elif action == "reject":
        gate.status = "rejected"
    elif action == "adjust":
        gate.status = "needs_adjustment"

    gate.reviewed_by = actor
    gate.reviewer_role = actor_role
    gate.reviewed_at = now
    gate.review_comment = comment
    gate.decision_action = action

    # Resolve corresponding ExecutiveRisk if approved
    if action == "approve":
        r_stmt = select(ExecutiveRisk).where(
            and_(
                ExecutiveRisk.product_code == gate.product_code,
                ExecutiveRisk.rule_code == f"GATE_RED_{gate.module_code}",
                ExecutiveRisk.is_resolved == False
            )
        )
        r_res = await db.execute(r_stmt)
        for risk in r_res.scalars().all():
            risk.is_resolved = True
            risk.title = risk.title.replace("🔴 待您亲自把关：", "✅ 已确认放行：")
            risk.action_suggestion = f"已由负责人 ({actor}) 审核确认放行，流程已推进至下一阶段。"

    # Audit log in decisions/
    p_stmt = select(Product).where(Product.code == gate.product_code)
    p_res = await db.execute(p_stmt)
    prod = p_res.scalar_one_or_none()
    init_id = prod.initiative_id if prod else "platform"

    # Sync Shadow Mode consistency if human reviewed
    if actor_role == "human":
        from backend.app.services.lead_service import sync_shadow_decision_upon_human_review
        try:
            await sync_shadow_decision_upon_human_review(
                db=db,
                gate=gate,
                human_action=action,
                human_actor=actor,
                human_comment=comment
            )
        except Exception:
            pass

    decisions_dir = Path(settings.WORKSPACE_DIR) / init_id / "products" / gate.product_code / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")
    file_path = decisions_dir / f"{timestamp_str}_gate_{gate.module_code}_decision_{action}.json"
    file_path.write_text(json.dumps({
        "gate_id": gate.id,
        "module_code": gate.module_code,
        "gate_name": gate.gate_name,
        "action": action,
        "status": gate.status,
        "reviewer": actor,
        "reviewer_role": actor_role,
        "comment": comment,
        "timestamp": now.isoformat()
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    await db.commit()
    await db.refresh(gate)
    return gate


async def check_stage_gate_passed(db: AsyncSession, module_id: str) -> Tuple[bool, str, Optional[GateApplication]]:
    """
    Checks if a module's gate is satisfied for baselining:
    - Stage 09: Release strictly blocked unless approved by a human.
    - Other stages: blocked if gate is pending, rejected, or needs_adjustment.
    """
    m_stmt = select(ModuleInstance).where(ModuleInstance.id == module_id)
    m_res = await db.execute(m_stmt)
    mod = m_res.scalar_one_or_none()
    if not mod:
        return False, f"Module {module_id} not found", None

    g_stmt = select(GateApplication).where(GateApplication.module_id == module_id).order_by(GateApplication.created_at.desc())
    g_res = await db.execute(g_stmt)
    gate = g_res.scalars().first()

    # Stage 09: Release strictly requires human approval record
    if mod.module_code == "09":
        if not gate:
            return False, "❌ 工序 09 (发布上线) 缺少人类确认记录，须先提交阶段确认单并由负责人签署批准后方可上线。", None
        if gate.status != "approved":
            return False, f"❌ 工序 09 (商店提审发布) 尚未获批 (当前状态: {gate.status})，无法放行上线。", gate
        if gate.reviewer_role != "human":
            return False, "❌ 工序 09 (商店提审发布) 必须由负责人亲自签署，当前审批人非人工账号，无法放行上线。", gate
        return True, "工序 09 人类提审确认记录具备，已放行上线", gate

    # Other stages
    if gate:
        if gate.status == "pending":
            return False, f"「{gate.gate_name}」处于待审批状态，须确认通过后方可定稿推进。", gate
        elif gate.status == "rejected":
            return False, f"「{gate.gate_name}」已被驳回，暂不能定稿: {gate.review_comment or '未提供驳回原因'}", gate
        elif gate.status == "needs_adjustment":
            return False, f"「{gate.gate_name}」已被要求调整修改，须补充材料后重新提报: {gate.review_comment or '待修改'}", gate
        elif gate.status == "approved":
            return True, f"「{gate.gate_name}」已由 {gate.reviewed_by} 批准通过", gate

    return True, "无需关口拦截或默认放行", None
