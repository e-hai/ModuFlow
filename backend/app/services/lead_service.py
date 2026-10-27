"""
Lead Agent Service & Shadow Mode Consistency Tracker
(backend/app/services/lead_service.py)

Enforces:
1. Lead Agent roles: dispatching, schedule tracking, handover validation, low-risk CR arbitration, daily progress digest.
2. Lead hard redlines: lead CANNOT approve yellow/red gates (G1, G2, G4, G5), cannot modify budget, cannot approve payment/privacy CRs, cannot submit to app stores.
3. Shadow Mode: In shadow mode (default True), lead only produces recommendations and does NOT execute approvals.
4. Consistency Tracking: Compares lead_recommendation vs human_decision to calculate and persist alignment metrics.
5. Protection: Shadow mode switch CAN ONLY be toggled by human accounts.
6. Audit: All lead evaluations and decisions are logged into physical decisions/ directory.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from backend.app.core.config import settings
from backend.app.models.entities import (
    Product,
    WorkflowRun,
    ModuleInstance,
    GateApplication,
    LeadShadowDecision,
    Issue,
    ExecutiveRisk
)
from backend.app.services.gate_keeper import (
    evaluate_gate_level,
    RED_ESCALATION_KEYWORDS
)


HIGH_RISK_CR_KEYWORDS = [
    "payment", "pay", "stripe", "iap", "subscription", "price", "pricing",
    "privacy", "gdpr", "user_data", "telemetry", "tracking",
    "encryption", "keychain", "security", "token", "secret",
    "合规", "支付", "订阅", "定价", "隐私", "敏感数据", "加密", "商店政策"
]


def _normalize_decision(decision_str: Optional[str]) -> str:
    if not decision_str:
        return "pending"
    d = decision_str.lower().strip()
    if d in ["approve", "approved", "pass", "passed"]:
        return "approved"
    elif d in ["reject", "rejected", "kill"]:
        return "rejected"
    elif d in ["adjust", "adjusted", "needs_adjustment", "pivot"]:
        return "adjusted"
    return d


async def evaluate_gate_by_lead(
    db: AsyncSession,
    gate_id: str,
    lead_actor: str = "agent:lead"
) -> Tuple[GateApplication, LeadShadowDecision]:
    """
    Lead evaluates a gate application:
    - If gate is yellow or red: lead ONLY outputs advice (approver is human).
    - If gate is green:
      - If product.shadow_mode is True: lead outputs advice, leaves status as pending for human confirmation.
      - If product.shadow_mode is False: lead self-approves the green gate.
    - Writes evaluation into LeadShadowDecision and physical decisions/ audit file.
    """
    gate_stmt = select(GateApplication).where(GateApplication.id == gate_id)
    res = await db.execute(gate_stmt)
    gate = res.scalar_one_or_none()
    if not gate:
        raise HTTPException(status_code=404, detail="GateApplication not found")

    # Find associated product
    run_stmt = select(WorkflowRun).where(WorkflowRun.id == gate.run_id)
    run_res = await db.execute(run_stmt)
    run = run_res.scalar_one_or_none()
    product_id = run.product_id if run else None

    product = None
    if product_id:
        p_stmt = select(Product).where(Product.id == product_id)
        p_res = await db.execute(p_stmt)
        product = p_res.scalar_one_or_none()

    shadow_mode_enabled = product.shadow_mode if product else True
    effective_level = gate.effective_level

    # 1. Lead assesses recommendation
    # If escalated or high risk triggers, recommend adjustment or reject
    if gate.is_escalated and any(t in ["payment", "privacy"] for t in gate.escalation_reasons):
        lead_recommendation = "adjusted"
        lead_rationale = (
            f"【Lead 预评估】检测到关口触发高敏感升级 ({', '.join(gate.escalation_reasons)})。"
            "依系统硬红线，Lead 严禁放行支付/隐私相关事项，建议人类负责人重点审查并要求补充合规凭证。"
        )
    elif "阻断" in gate.risk_assessment or "Critical" in gate.risk_assessment:
        lead_recommendation = "rejected"
        lead_rationale = f"【Lead 预评估】存在阻断性风险: {gate.risk_assessment}，建议打回重修。"
    else:
        lead_recommendation = "approved"
        lead_rationale = (
            f"【Lead 预评估】工序 {gate.module_code} 交付物与事实依据完备 ({len(gate.evidence)} 项佐证)，"
            "风险已建立应对预案，建议放行。"
        )

    # 2. Apply shadow mode rules
    now = datetime.now(timezone.utc)
    if effective_level == "green" and not shadow_mode_enabled:
        # Autonomous mode: lead can self-approve green gate
        gate.status = "approved"
        gate.reviewed_by = lead_actor
        gate.reviewer_role = "lead"
        gate.reviewed_at = now
        gate.decision_action = "approve"
        gate.review_comment = f"[Lead 自主放行] {lead_rationale}"
    else:
        # Shadow mode (or Yellow/Red gate): lead does NOT approve, remains pending
        gate.lead_recommendation = lead_recommendation
        gate.lead_rationale = lead_rationale

    # 3. Create or update LeadShadowDecision record
    sd_stmt = select(LeadShadowDecision).where(LeadShadowDecision.gate_application_id == gate.id)
    sd_res = await db.execute(sd_stmt)
    shadow_dec = sd_res.scalar_one_or_none()

    if not shadow_dec:
        shadow_dec = LeadShadowDecision(
            product_id=product.id if product else "unknown",
            module_id=gate.module_id,
            gate_application_id=gate.id,
            decision_type="gate_review",
            stage_code=gate.module_code,
            lead_recommendation=lead_recommendation,
            lead_rationale=lead_rationale,
            created_at=now
        )
        db.add(shadow_dec)
    else:
        shadow_dec.lead_recommendation = lead_recommendation
        shadow_dec.lead_rationale = lead_rationale

    # 4. Write audit decision file to physical workspace
    if product and product.initiative_id:
        decisions_dir = Path(settings.WORKSPACE_DIR) / product.initiative_id / "products" / product.code / "decisions"
        decisions_dir.mkdir(parents=True, exist_ok=True)
        ts_str = now.strftime("%Y%m%d_%H%M%S")
        audit_file = decisions_dir / f"{ts_str}_lead_gate_evaluation.json"
        audit_file.write_text(json.dumps({
            "event": "LEAD_GATE_EVALUATION",
            "timestamp": now.isoformat(),
            "gate_id": gate.id,
            "gate_name": gate.gate_name,
            "module_code": gate.module_code,
            "effective_level": gate.effective_level,
            "shadow_mode": shadow_mode_enabled,
            "lead_recommendation": lead_recommendation,
            "lead_rationale": lead_rationale,
            "autonomous_approved": gate.status == "approved"
        }, indent=2, ensure_ascii=False), encoding="utf-8")

    await db.commit()
    await db.refresh(gate)
    await db.refresh(shadow_dec)

    return gate, shadow_dec


async def sync_shadow_decision_upon_human_review(
    db: AsyncSession,
    gate: GateApplication,
    human_action: str,
    human_actor: str,
    human_comment: Optional[str] = None
) -> Optional[LeadShadowDecision]:
    """
    Called whenever human reviews a GateApplication:
    Finds the active LeadShadowDecision, records human_decision, computes is_consistent,
    and logs the comparison into decisions/.
    """
    sd_stmt = select(LeadShadowDecision).where(LeadShadowDecision.gate_application_id == gate.id)
    sd_res = await db.execute(sd_stmt)
    shadow_dec = sd_res.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    norm_human = _normalize_decision(human_action)

    if shadow_dec:
        norm_lead = _normalize_decision(shadow_dec.lead_recommendation)
        is_consistent = (norm_lead == norm_human)

        shadow_dec.human_decision = norm_human
        shadow_dec.human_reviewer = human_actor
        shadow_dec.human_feedback = human_comment
        shadow_dec.is_consistent = is_consistent
        shadow_dec.resolved_at = now

        gate.is_consistent = is_consistent

        # Physical disk audit comparison
        p_stmt = select(Product).where(Product.id == shadow_dec.product_id)
        p_res = await db.execute(p_stmt)
        product = p_res.scalar_one_or_none()
        if product and product.initiative_id:
            decisions_dir = Path(settings.WORKSPACE_DIR) / product.initiative_id / "products" / product.code / "decisions"
            decisions_dir.mkdir(parents=True, exist_ok=True)
            ts_str = now.strftime("%Y%m%d_%H%M%S")
            audit_file = decisions_dir / f"{ts_str}_shadow_consistency_comparison.json"
            audit_file.write_text(json.dumps({
                "event": "SHADOW_CONSISTENCY_COMPARISON",
                "timestamp": now.isoformat(),
                "gate_id": gate.id,
                "stage_code": gate.module_code,
                "lead_recommendation": shadow_dec.lead_recommendation,
                "human_decision": norm_human,
                "is_consistent": is_consistent,
                "human_reviewer": human_actor
            }, indent=2, ensure_ascii=False), encoding="utf-8")

        await db.commit()
        await db.refresh(shadow_dec)
        return shadow_dec

    return None


async def get_shadow_mode_stats(db: AsyncSession, product_id: str) -> Dict[str, Any]:
    """
    Calculates consistency metrics for a product under Shadow Mode:
    Total decisions evaluated by human, consistent count, divergent count, consistency rate.
    """
    stmt = select(LeadShadowDecision).where(
        LeadShadowDecision.product_id == product_id,
        LeadShadowDecision.human_decision.isnot(None)
    )
    res = await db.execute(stmt)
    resolved_decisions = res.scalars().all()

    total = len(resolved_decisions)
    consistent_count = sum(1 for d in resolved_decisions if d.is_consistent is True)
    divergent_count = total - consistent_count
    consistency_rate = round(consistent_count / total, 4) if total > 0 else 1.0

    # Also count pending decisions
    pending_stmt = select(func.count(LeadShadowDecision.id)).where(
        LeadShadowDecision.product_id == product_id,
        LeadShadowDecision.human_decision.is_(None)
    )
    pending_res = await db.execute(pending_stmt)
    pending_count = pending_res.scalar() or 0

    return {
        "product_id": product_id,
        "total_evaluated": total,
        "consistent_count": consistent_count,
        "divergent_count": divergent_count,
        "consistency_rate": consistency_rate,
        "consistency_percentage": f"{consistency_rate * 100:.1f}%",
        "pending_human_review_count": pending_count,
        "recent_decisions": [
            {
                "id": d.id,
                "stage_code": d.stage_code,
                "decision_type": d.decision_type,
                "lead_recommendation": d.lead_recommendation,
                "human_decision": d.human_decision,
                "is_consistent": d.is_consistent,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "resolved_at": d.resolved_at.isoformat() if d.resolved_at else None
            }
            for d in resolved_decisions[-10:]
        ]
    }


async def toggle_product_shadow_mode(
    db: AsyncSession,
    product_id: str,
    enabled: bool,
    actor_type: str,
    actor_id: str
) -> Product:
    """
    Toggles product shadow mode.
    HARD CONSTRAINT:
    Only actor_type == 'human' can change shadow mode. Any Agent attempting this is rejected with 403.
    """
    if actor_type != "human":
        raise HTTPException(
            status_code=403,
            detail="❌ 权限拒绝: 只有人类负责人 (human) 可以修改影子模式开关。Agent 严禁修改自身放权状态。"
        )

    stmt = select(Product).where(Product.id == product_id)
    res = await db.execute(stmt)
    product = res.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    old_state = product.shadow_mode
    product.shadow_mode = enabled

    # Decision audit log
    if product.initiative_id:
        decisions_dir = Path(settings.WORKSPACE_DIR) / product.initiative_id / "products" / product.code / "decisions"
        decisions_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)
        ts_str = now.strftime("%Y%m%d_%H%M%S")
        log_file = decisions_dir / f"{ts_str}_shadow_mode_toggled.json"
        log_file.write_text(json.dumps({
            "event": "SHADOW_MODE_TOGGLED",
            "timestamp": now.isoformat(),
            "actor": actor_id,
            "old_state": old_state,
            "new_state": enabled,
            "product_id": product.id,
            "product_code": product.code
        }, indent=2, ensure_ascii=False), encoding="utf-8")

    await db.commit()
    await db.refresh(product)
    return product


async def arbitrate_cr_by_lead(
    db: AsyncSession,
    issue_id: str,
    lead_actor: str = "agent:lead"
) -> Dict[str, Any]:
    """
    Lead arbitrates a Change Request (CR) Issue:
    - If CR contains payment, privacy, sensitive data, or security: auto-escalates to human.
    - If low-risk: lead arbitrates resolution recommendation.
    """
    stmt = select(Issue).where(Issue.id == issue_id)
    res = await db.execute(stmt)
    issue = res.scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    desc_text = str(issue.description)
    title_text = issue.title or ""
    combined = f"{title_text} {desc_text}".lower()

    # Check for payment/privacy/security sensitive triggers
    is_sensitive = any(kw in combined for kw in HIGH_RISK_CR_KEYWORDS)

    now = datetime.now(timezone.utc)
    if is_sensitive:
        arbitration_result = {
            "issue_id": issue.id,
            "lead_recommendation": "escalate_to_human",
            "is_escalated": True,
            "escalation_reason": "CR 涉及支付定价、隐私合规或核心安全，超出 Lead 仲裁权限，强制升级人类决策",
            "suggested_action": "提交工序 05 产品经理与人类负责人进行需求基线合规评审",
            "arbitrated_by": lead_actor,
            "timestamp": now.isoformat()
        }
    else:
        arbitration_result = {
            "issue_id": issue.id,
            "lead_recommendation": "accept_cr_revision",
            "is_escalated": False,
            "escalation_reason": None,
            "suggested_action": "低风险体验/实现优化，建议上游工序 05 采纳并在新基线中修订业务说明",
            "arbitrated_by": lead_actor,
            "timestamp": now.isoformat()
        }

    return arbitration_result


async def generate_project_daily_digest(
    db: AsyncSession,
    product_id: str
) -> Dict[str, Any]:
    """
    Generates a structured 1-page daily progress digest for management:
    - Product financial budget and burn rate
    - Active iteration and stage status
    - Pending gates and lead shadow recommendations
    - Blockages and next-step dispatch advice
    """
    stmt = select(Product).where(Product.id == product_id)
    res = await db.execute(stmt)
    product = res.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Fetch latest active workflow run
    run_stmt = select(WorkflowRun).where(
        WorkflowRun.product_id == product_id,
        WorkflowRun.status == "in_progress"
    ).order_by(WorkflowRun.created_at.desc())
    run_res = await db.execute(run_stmt)
    active_run = run_res.scalars().first()

    # Fetch pending gate applications for this product
    gate_stmt = select(GateApplication).where(
        GateApplication.product_code == product.code,
        GateApplication.status == "pending"
    )
    gate_res = await db.execute(gate_stmt)
    pending_gates = gate_res.scalars().all()

    # Get shadow mode stats
    shadow_stats = await get_shadow_mode_stats(db, product_id)

    # Calculate budget utilization
    spent = product.actual_spent
    allocated = product.budget_allocated
    burn_rate_pct = f"{(spent / allocated * 100):.1f}%" if allocated > 0 else "0.0%"

    digest = {
        "report_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "product_name": product.name,
        "product_code": product.code,
        "current_stage": product.stage,
        "shadow_mode_active": product.shadow_mode,
        "financial_summary": {
            "budget_allocated": allocated,
            "actual_spent": spent,
            "burn_rate": burn_rate_pct,
            "status": "normal" if spent <= allocated else "over_budget"
        },
        "active_sprint": {
            "run_id": active_run.id if active_run else None,
            "run_name": active_run.name if active_run else "无进行中迭代",
            "template_id": active_run.template_id if active_run else None
        },
        "pending_gates_summary": [
            {
                "gate_id": g.id,
                "gate_name": g.gate_name,
                "stage_code": g.module_code,
                "level": g.effective_level,
                "lead_recommendation": g.lead_recommendation or "待评估"
            }
            for g in pending_gates
        ],
        "shadow_consistency": {
            "consistency_rate": shadow_stats["consistency_percentage"],
            "total_evaluated": shadow_stats["total_evaluated"]
        },
        "lead_dispatch_recommendation": (
            "存在待审批关口，建议负责人先行处置" if pending_gates
            else f"当前项目处于【{product.stage}】阶段，各工序运转正常，按计划推进。"
        )
    }

    return digest
