"""
自动编排器：交接锚点检查（缺了就发回上游补，最多 2 次）→ 派活 → 交付物确定性检查
→ 关口申请 → lead 评估 → 定稿 → 解锁下游。

只减少"推一下"的人工动作，不改关口规则：黄/红级关口、工序 09、影子模式下的绿级关口
仍停在 pending 等人类签字；熔断与授权检查仍由 can_baseline_module 确定性执行。
已签字的上游补锚点时，原签字继续有效；补写带上新的红级标记才重新请人批。
"""
import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.models.entities import (
    Artifact,
    ChangeReview,
    CollaborationSession,
    ExecutiveRisk,
    GateApplication,
    Issue,
    ModuleInstance,
    Product,
    SessionMessage,
    WorkflowRun,
)

MAX_AUTO_REVISIONS = 2
ORCH_SENDER = "项目总控 lead (自动编排)"
STUCK_RULE_PREFIX = "ORCH_STUCK_"
DISPUTE_RULE_PREFIX = "ORCH_DISPUTE_"
CONTEXT_FLAG_KEYS = ("is_major_version", "major_version")

_run_locks: Dict[str, asyncio.Lock] = {}
_reviewing: set = set()


def get_run_lock(run_id: str) -> asyncio.Lock:
    if run_id not in _run_locks:
        _run_locks[run_id] = asyncio.Lock()
    return _run_locks[run_id]


def orchestration_enabled() -> bool:
    return bool(settings.ORCHESTRATOR_ENABLED)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _load_module_context(
    db: AsyncSession, module_id: str
) -> Tuple[Optional[ModuleInstance], Optional[WorkflowRun], Optional[Product]]:
    mod = (await db.execute(select(ModuleInstance).where(ModuleInstance.id == module_id))).scalar_one_or_none()
    if not mod:
        return None, None, None
    run = (await db.execute(select(WorkflowRun).where(WorkflowRun.id == mod.run_id))).scalar_one_or_none()
    product = None
    if run:
        product = (await db.execute(select(Product).where(Product.id == run.product_id))).scalar_one_or_none()
    return mod, run, product


async def _load_run(db: AsyncSession, run_id: str) -> Tuple[Optional[WorkflowRun], Optional[Product]]:
    run = (await db.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))).scalar_one_or_none()
    product = None
    if run:
        product = (await db.execute(select(Product).where(Product.id == run.product_id))).scalar_one_or_none()
    return run, product


def _run_block_reason(run: Optional[WorkflowRun], product: Optional[Product]) -> Optional[str]:
    if run is None:
        return "run_not_found"
    if run.status != "in_progress":
        return "run_not_active"
    if not run.auto_advance:
        return "auto_advance_off"
    if product is not None and product.stage == "paused":
        return "paused"
    return None


def dispatch_block_reason(run: Optional[WorkflowRun]) -> Optional[str]:
    """派活前就能判定的拦截原因，排队之前先问一次，别排一个注定不派活的任务。"""
    if run is None:
        return "run_not_found"
    if run.status != "in_progress":
        return "run_not_active"
    if not run.auto_advance:
        return "auto_advance_off"
    return None


def _write_audit(product: Optional[Product], event: str, payload: Dict[str, Any]) -> None:
    if not product or not product.initiative_id:
        return
    now = datetime.now(timezone.utc)
    decisions_dir = Path(settings.WORKSPACE_DIR) / product.initiative_id / "products" / product.code / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    file_path = decisions_dir / f"{now.strftime('%Y%m%d_%H%M%S_%f')}_orchestrator_{event.lower()}.json"
    file_path.write_text(json.dumps(
        {"event": event, "timestamp": now.isoformat(), **payload},
        indent=2, ensure_ascii=False, default=str,
    ), encoding="utf-8")


async def _get_or_create_session(db: AsyncSession, module_id: str) -> CollaborationSession:
    session = (await db.execute(
        select(CollaborationSession).where(CollaborationSession.module_id == module_id)
    )).scalars().first()
    if session:
        return session
    session = CollaborationSession(
        module_id=module_id,
        title="主协作会话",
        participants=[
            {"role": "human", "name": "负责人"},
            {"role": "agent", "name": "Agent 协作者"},
        ],
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def _module_artifacts(db: AsyncSession, module_id: str) -> List[Artifact]:
    res = await db.execute(select(Artifact).where(Artifact.module_id == module_id).order_by(Artifact.version.asc()))
    return list(res.scalars().all())


async def _module_gate(db: AsyncSession, module_id: str) -> Optional[GateApplication]:
    res = await db.execute(
        select(GateApplication).where(GateApplication.module_id == module_id).order_by(GateApplication.created_at.desc())
    )
    return res.scalars().first()


async def _open_risk(
    db: AsyncSession, product: Optional[Product], mod: ModuleInstance, prefix: str
) -> Optional[ExecutiveRisk]:
    if not product:
        return None
    res = await db.execute(
        select(ExecutiveRisk).where(and_(
            ExecutiveRisk.product_code == product.code,
            ExecutiveRisk.rule_code == f"{prefix}{mod.module_code}",
            ExecutiveRisk.is_resolved == False,  # noqa: E712
        )).order_by(ExecutiveRisk.created_at.desc())
    )
    return res.scalars().first()


def _orch_kind(msg: SessionMessage) -> str:
    return str((msg.metadata_json or {}).get("orchestrator") or "")


async def _session_messages_newest(db: AsyncSession, session_id: str) -> List[SessionMessage]:
    res = await db.execute(
        select(SessionMessage)
        .where(SessionMessage.session_id == session_id)
        .order_by(SessionMessage.created_at.desc())
    )
    return list(res.scalars().all())


async def _dispatch_hold(db: AsyncSession, session_id: str) -> bool:
    """自动重派已经用完，且人还没有点「重新派活」。"""
    for msg in await _session_messages_newest(db, session_id):
        kind = _orch_kind(msg)
        if kind == "redispatch":
            return False
        if kind == "dispatch_exhausted":
            return True
    return False


async def _dispatch_misses(db: AsyncSession, session_id: str) -> int:
    count = 0
    for msg in await _session_messages_newest(db, session_id):
        kind = _orch_kind(msg)
        if kind == "redispatch":
            break
        if kind == "dispatch_miss":
            count += 1
    return count


async def close_iteration_risks(db: AsyncSession, product: Optional[Product], note: str) -> int:
    """迭代废弃或封版后，这一轮仍开着的卡住与分歧不再挡住下一次迭代。"""
    if product is None:
        return 0
    rows = (await db.execute(select(ExecutiveRisk).where(and_(
        ExecutiveRisk.product_code == product.code,
        ExecutiveRisk.is_resolved == False,  # noqa: E712
        or_(
            ExecutiveRisk.rule_code.like(f"{STUCK_RULE_PREFIX}%"),
            ExecutiveRisk.rule_code.like(f"{DISPUTE_RULE_PREFIX}%"),
        ),
    )))).scalars().all()
    for risk in rows:
        risk.is_resolved = True
        risk.action_suggestion = note
        db.add(risk)
    if rows:
        await db.commit()
    return len(rows)


async def _stuck_risk(db: AsyncSession, product: Optional[Product], mod: ModuleInstance) -> Optional[ExecutiveRisk]:
    return await _open_risk(db, product, mod, STUCK_RULE_PREFIX) or await _open_risk(db, product, mod, DISPUTE_RULE_PREFIX)


async def _resolve_stuck(db: AsyncSession, product: Optional[Product], mod: ModuleInstance, actor: str) -> None:
    for prefix in (STUCK_RULE_PREFIX, DISPUTE_RULE_PREFIX):
        risk = await _open_risk(db, product, mod, prefix)
        if risk:
            risk.is_resolved = True
            risk.action_suggestion = f"{actor} 已介入，自动编排恢复。"
            db.add(risk)
    await db.commit()


async def _raise_dispute(
    db: AsyncSession,
    product: Optional[Product],
    mod: ModuleInstance,
    session: CollaborationSession,
    blocking: List[Dict[str, Any]],
) -> None:
    """Primary Agent and reviewer still disagree after the revision budget: a human picks a side."""
    positions = [
        f"{r['reviewer']}（{'确定性交叉检查' if r.get('kind') == 'check' else '协作评审'}）：" + "；".join(r.get("findings") or ["要求修订"])
        for r in blocking
    ]
    if product and product.initiative_id and not await _open_risk(db, product, mod, DISPUTE_RULE_PREFIX):
        db.add(ExecutiveRisk(
            initiative_id=product.initiative_id,
            rule_code=f"{DISPUTE_RULE_PREFIX}{mod.module_code}",
            title=f"🟠 协作评审分歧：工序 {mod.module_code} {mod.name} · {product.code}",
            severity="major",
            description=f"主责 {mod.primary_role_code} 修订 {MAX_AUTO_REVISIONS} 次后评审仍不通过。" + " | ".join(positions)[:900],
            product_code=product.code,
            action_suggestion="请在工序页裁决：采纳评审意见（发回主责修订）或否决评审意见（按当前交付物继续检查）。",
            is_resolved=False,
        ))
    db.add(SessionMessage(
        session_id=session.id,
        sender=ORCH_SENDER,
        sender_role="system",
        role_code="lead",
        message_type="error",
        content=(
            f"⚖️ 主责 {mod.primary_role_code} 与评审方意见未收敛，已停下等负责人裁决。\n"
            + "\n".join(f"- {p}" for p in positions)
        ),
        metadata_json={"orchestrator": "dispute", "reviews": blocking},
    ))
    await db.commit()
    _write_audit(product, "STAGE_DISPUTE", {
        "module_code": mod.module_code,
        "module_id": mod.id,
        "reviews": blocking,
    })


async def _upstream_baselines(db: AsyncSession, run_id: str) -> Dict[str, str]:
    modules = (await db.execute(select(ModuleInstance).where(ModuleInstance.run_id == run_id))).scalars().all()
    texts: Dict[str, str] = {}
    for m in modules:
        if not m.baseline_artifact_id:
            continue
        art = (await db.execute(select(Artifact).where(Artifact.id == m.baseline_artifact_id))).scalar_one_or_none()
        if art:
            from backend.app.services.delivery_contract import read_manifest_text

            body = art.content or ""
            manifest_text = read_manifest_text(art.storage_rel_path)
            if manifest_text.strip() and manifest_text.strip() not in body:
                body = f"{body}\n```json\n{manifest_text.strip()}\n```\n"
            texts[m.module_code] = body
    return texts


def _authorization_data(product: Optional[Product]) -> Dict[str, Any]:
    from backend.app.services.authorization_engine import load_product_authorization

    if not product or not product.initiative_id:
        return {}
    try:
        _status, data, _errors = load_product_authorization(product.initiative_id, product.code)
    except Exception:
        return {}
    return data or {}


async def _collaboration_reviews(
    db: AsyncSession,
    mod: ModuleInstance,
    product: Optional[Product],
    session: CollaborationSession,
    latest: Artifact,
) -> List[Dict[str, Any]]:
    """Deterministic cross-checks first; collaborator Agents only review once those pass."""
    from backend.app.services.agent_runner import execute_collaborator_review
    from backend.app.services.collaboration import review_mode, reviews_for_stage, run_check

    mode = review_mode()
    if mode == "off":
        return []
    specs = reviews_for_stage(mod.module_code)
    if not specs:
        return []
    upstream = await _upstream_baselines(db, mod.run_id)
    auth_data = _authorization_data(product)
    results = [
        run_check(spec, [latest.content or ""], upstream, auth_data)
        for spec in specs if spec["kind"] == "check"
    ]
    if mode != "full" or any(r["verdict"] == "request_changes" for r in results):
        return results
    _reviewing.add(mod.id)
    try:
        for spec in specs:
            if spec["kind"] == "llm":
                results.append(await execute_collaborator_review(db, session, mod, spec, latest))
    finally:
        _reviewing.discard(mod.id)
    return results


async def _handoff_gaps(db: AsyncSession, mod: ModuleInstance) -> List[Dict[str, str]]:
    from backend.app.services.collaboration import check_handoff

    upstream = await _upstream_baselines(db, mod.run_id)
    return check_handoff(mod.module_code, upstream, list(upstream.keys()))


async def _flag_handoff_gaps(
    db: AsyncSession, product: Optional[Product], mod: ModuleInstance, gaps: List[Dict[str, str]]
) -> None:
    modules = (await db.execute(select(ModuleInstance).where(ModuleInstance.run_id == mod.run_id))).scalars().all()
    by_code = {m.module_code: m for m in modules}
    created = []
    for code in sorted({g["upstream"] for g in gaps}):
        upstream = by_code.get(code)
        if upstream is None:
            continue
        exists = (await db.execute(select(Issue).where(and_(
            Issue.source_module_id == mod.id,
            Issue.target_module_id == upstream.id,
            Issue.category == "handoff_gap",
            Issue.status.in_(["open", "investigating", "fixing", "verifying"]),
        )))).scalars().first()
        if exists:
            continue
        anchors = [g["anchor"] for g in gaps if g["upstream"] == code]
        db.add(Issue(
            source_module_id=mod.id,
            target_module_id=upstream.id,
            title=f"[交接缺口] 工序 {code} 基线缺少工序 {mod.module_code} 所需锚点：{'、'.join(anchors)}",
            description={"summary": f"工序 {mod.module_code} 开工前需要上游基线提供：{'、'.join(anchors)}", "anchors": anchors},
            category="handoff_gap",
            severity="minor",
            priority="P2",
            status="open",
            reporter=ORCH_SENDER,
            reporter_role="lead",
        ))
        created.append({"upstream": code, "anchors": anchors})
    if created:
        await db.commit()
        _write_audit(product, "HANDOFF_INCOMPLETE", {"module_code": mod.module_code, "module_id": mod.id, "gaps": created})


async def _close_resolved_handoff_gaps(db: AsyncSession, mod: ModuleInstance) -> None:
    issues = (await db.execute(select(Issue).where(and_(
        Issue.source_module_id == mod.id,
        Issue.category == "handoff_gap",
        Issue.status.in_(["open", "investigating", "fixing", "verifying"]),
    )))).scalars().all()
    if not issues:
        return
    for issue in issues:
        issue.status = "closed"
        issue.resolution = "fixed"
        issue.closed_at = datetime.utcnow()
        db.add(issue)
    await db.commit()


async def _file_review_crs(
    db: AsyncSession,
    mod: ModuleInstance,
    results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """raise_cr verdicts become requirement CRs on the upstream stage; lead arbitrates, red only on structured flags."""
    from backend.app.services.deliverable_audit import RED_FLAG_FIELDS
    from backend.app.services.lead_service import arbitrate_cr_by_lead

    records: List[Dict[str, Any]] = []
    modules = (await db.execute(select(ModuleInstance).where(ModuleInstance.run_id == mod.run_id))).scalars().all()
    by_code = {m.module_code: m for m in modules}
    for r in results:
        if r.get("verdict") != "raise_cr":
            continue
        target = by_code.get(str(r.get("cr_target_stage") or "05")) or mod
        summary = "；".join(r.get("findings") or ["协作评审提出需求变更"])
        flags = {k: True for k, v in (r.get("cr_flags") or {}).items() if v and k in RED_FLAG_FIELDS}
        issue = (await db.execute(select(Issue).where(and_(
            Issue.source_module_id == mod.id,
            Issue.target_module_id == target.id,
            Issue.category == "requirement_cr",
            Issue.reporter == f"agent:{r['reviewer']}",
            Issue.status.in_(["open", "investigating", "fixing", "verifying"]),
        )))).scalars().first()
        if issue is None:
            issue = Issue(
                source_module_id=mod.id,
                target_module_id=target.id,
                title=f"[CR] {r['reviewer']} 评审工序 {mod.module_code} 时对工序 {target.module_code} 提出变更",
                description={"summary": summary, "cr_flags": sorted(flags), "source": "collaboration_review"},
                category="requirement_cr",
                severity="minor",
                priority="P2",
                status="open",
                reporter=f"agent:{r['reviewer']}",
                reporter_role=r["reviewer"],
            )
        else:
            issue.description = {**(issue.description or {}), "summary": summary, "cr_flags": sorted(flags)}
        db.add(issue)
        await db.commit()
        await db.refresh(issue)
        arbitration = await arbitrate_cr_by_lead(db, issue.id)
        records.append({
            "issue_id": issue.id,
            "reviewer": r["reviewer"],
            "target_stage": target.module_code,
            "summary": summary[:300],
            "flags": sorted(flags),
            "lead_recommendation": arbitration.get("lead_recommendation"),
            "escalated": bool(flags),
        })
    return records


async def _raise_stuck(
    db: AsyncSession,
    product: Optional[Product],
    mod: ModuleInstance,
    session: CollaborationSession,
    reasons: List[str],
    *,
    exhausted: bool = False,
    headline: Optional[str] = None,
) -> None:
    if headline is None:
        headline = (
            f"已自动修订 {MAX_AUTO_REVISIONS} 次，交付物仍未通过检查"
            if exhausted else
            "这一轮没有产出新的交付物"
        )
    if product and product.initiative_id and not await _stuck_risk(db, product, mod):
        db.add(ExecutiveRisk(
            initiative_id=product.initiative_id,
            rule_code=f"{STUCK_RULE_PREFIX}{mod.module_code}",
            title=f"🟠 {headline}：工序 {mod.module_code} {mod.name} · {product.code}",
            severity="major",
            description=headline + "：" + "; ".join(reasons[:5]),
            product_code=product.code,
            action_suggestion="请在工序会话里补充指令或上传交付物，系统会重新检查并继续推进。",
            is_resolved=False,
        ))
    db.add(SessionMessage(
        session_id=session.id,
        sender=ORCH_SENDER,
        sender_role="system",
        role_code="lead",
        message_type="error",
        content=(
            f"⛔ {headline}，自动编排在本工序停下等人处理。\n"
            + "\n".join(f"- {r}" for r in reasons[:8])
        ),
        metadata_json={"orchestrator": "stuck", "reasons": reasons[:8]},
    ))
    await db.commit()
    _write_audit(product, "STAGE_STUCK", {
        "module_code": mod.module_code,
        "module_id": mod.id,
        "reasons": reasons[:8],
    })


async def _revisions_since_boundary(db: AsyncSession, session_id: str) -> int:
    """已经改完并交回的修订次数。

    只统计这次派活（或负责人重新介入）之后、Agent 已经给出回复的修订。
    进程在半路被杀掉、稿子根本没改出来的那次不占次数，否则重启之后
    预算会被没用掉的尝试耗尽，工序停住不再往下走。
    """
    res = await db.execute(
        select(SessionMessage).where(SessionMessage.session_id == session_id).order_by(SessionMessage.created_at.desc())
    )
    window: List[SessionMessage] = []
    for msg in res.scalars().all():
        kind = (msg.metadata_json or {}).get("orchestrator")
        if kind in (
            "dispatch", "gate_feedback", "human_resume", "handoff_repair", "handoff_repair_done",
        ) or msg.sender_role == "human":
            break
        window.append(msg)
    window.reverse()
    count = 0
    for index, msg in enumerate(window):
        if (msg.metadata_json or {}).get("orchestrator") != "revision":
            continue
        for later in window[index + 1:]:
            if (later.metadata_json or {}).get("orchestrator") == "revision":
                break
            if later.artifact_ref_id or later.message_type in ("draft_artifact", "revised_artifact"):
                count += 1
                break
            # CLI 自己报错也算一次用掉的修订；编排器写的「停下等人」不算。
            if later.message_type == "error" and later.sender_role == "agent":
                count += 1
                break
    return count


def _dispatch_brief(mod: ModuleInstance, product: Optional[Product]) -> str:
    from backend.app.services.agent_roles import STAGE_ROLE_CONFIGS, get_stage_gate_conditions

    cfg = STAGE_ROLE_CONFIGS.get(mod.module_code, {})
    platform = (product.platform if product else None) or "ios"
    zero_inf = True if not product or product.client_zero_inference is None else bool(product.client_zero_inference)
    conditions = get_stage_gate_conditions(mod.module_code, platform=platform, client_zero_inference=zero_inf)
    lines = [
        f"【自动派活】工序 {mod.module_code} {mod.name}",
        f"任务重点：{cfg.get('mission_focus', mod.name)}",
        "放行条件（定稿时由确定性脚本读取交付物复核）：",
    ]
    lines += [f"- {c}" for c in conditions] or ["- 按本工序契约产出完整交付物"]
    lines.append("涉及支付、隐私、密钥、数据字典变更时，请在交付物里写结构化标记（如 is_payment_related: true）。")
    return "\n".join(lines)


async def _post_and_run(
    db: AsyncSession,
    session: CollaborationSession,
    content: str,
    message_type: str,
    kind: str,
    extra_meta: Optional[Dict[str, Any]] = None,
) -> Optional[SessionMessage]:
    from backend.app.services.agent_runner import execute_agent_for_session

    msg = SessionMessage(
        session_id=session.id,
        sender=ORCH_SENDER,
        sender_role="agent",
        role_code="lead",
        message_type=message_type,
        content=content,
        metadata_json={"orchestrator": kind, **(extra_meta or {})},
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return await execute_agent_for_session(db, session, msg)


def _structured_context(fields: Dict[str, Any]) -> Dict[str, Any]:
    from backend.app.services.deliverable_audit import RED_FLAG_FIELDS

    keys = list(RED_FLAG_FIELDS.keys()) + list(CONTEXT_FLAG_KEYS)
    return {k: fields[k] for k in keys if k in fields}


async def _qa_quality_gate(
    db: AsyncSession,
    gate: GateApplication,
    product: Optional[Product],
    audit: Dict[str, Any],
) -> GateApplication:
    """G3 belongs to qa: qa releases it from the deterministic quality report, lead never does."""
    from backend.app.services.gate_keeper import get_designated_approver, review_gate_application

    if gate.status != "pending" or gate.effective_level != "green":
        return gate
    if await get_designated_approver(db, gate) != "qa":
        return gate
    if product is None or product.shadow_mode is not False:
        return gate
    if not audit.get("passed"):
        return gate
    open_blockers = (await db.execute(select(Issue).where(
        Issue.target_module_id == gate.module_id,
        Issue.status.in_(["open", "investigating", "fixing", "verifying"]),
        Issue.severity.in_(["critical", "major"]),
    ))).scalars().all()
    if open_blockers:
        return gate
    comment = (
        f"[qa 质量门] 确定性检查通过：open_p0={audit.get('open_p0')}, open_p1={audit.get('open_p1')}，"
        "无未关闭 Critical/Major 缺陷。"
    )
    return await review_gate_application(db, gate.id, "approve", comment, actor="agent:qa", actor_role="qa")


# ---------------------------------------------------------------------------
# Core steps (caller holds the run lock)
# ---------------------------------------------------------------------------

async def _finalize(db: AsyncSession, module_id: str) -> Tuple[bool, str]:
    from backend.app.services.workflow_engine import can_baseline_module, unlock_downstream_modules
    from backend.app.services.workspace_sync import sync_run_workspace

    ok, reason = await can_baseline_module(db, module_id)
    mod, _run, product = await _load_module_context(db, module_id)
    if not ok or mod is None:
        _write_audit(product, "FINALIZE_BLOCKED", {"module_id": module_id, "reason": reason})
        return False, reason

    artifacts = await _module_artifacts(db, module_id)
    latest = artifacts[-1]
    for art in artifacts:
        art.is_baseline = art.id == latest.id
        db.add(art)
    mod.baseline_artifact_id = latest.id
    mod.phase = "baselined"
    db.add(mod)

    reviews = (await db.execute(select(ChangeReview).where(
        ChangeReview.module_id == module_id, ChangeReview.status == "pending"
    ))).scalars().all()
    for review in reviews:
        review.status = "approved"
        review.approver = ORCH_SENDER
        review.approved_at = datetime.utcnow()
        db.add(review)

    await db.commit()
    await unlock_downstream_modules(db, mod.run_id)
    try:
        await sync_run_workspace(db, mod.run_id)
    except Exception:
        pass

    gate = await _module_gate(db, module_id)
    _write_audit(product, "STAGE_FINALIZED", {
        "module_code": mod.module_code,
        "module_id": mod.id,
        "artifact_version": latest.version,
        "gate_status": gate.status if gate else None,
        "gate_reviewer": gate.reviewed_by if gate else None,
    })
    return True, ""


async def _process_artifact(
    db: AsyncSession,
    module_id: str,
    origin: str,
    review_override: Optional[str] = None,
) -> str:
    """origin: agent（编排器派活产出）/ human_session（人类在会话里指挥产出）/ human_confirmed（人类上传或确认提交）。
    review_override: 人类否决评审意见时的操作人，本次跳过协作评审并在证据里留痕。"""
    from backend.app.services.compliance_engine import (
        audit_module_compliance,
        compliance_failed_items,
        run_stage_compliance_check,
    )
    from backend.app.services.deliverable_audit import artifact_audit_texts, audit_stage, merged_fields
    from backend.app.services.gate_keeper import create_or_update_gate_application, get_stage_gate_config
    from backend.app.services.lead_service import evaluate_gate_by_lead
    from backend.app.services.workflow_engine import load_price_baseline

    if origin != "agent":
        mod, _run, product = await _load_module_context(db, module_id)
        if mod:
            await _resolve_stuck(db, product, mod, "负责人")
            session = await _get_or_create_session(db, module_id)
            db.add(SessionMessage(
                session_id=session.id,
                sender=ORCH_SENDER,
                sender_role="system",
                role_code="lead",
                message_type="instruction",
                content="负责人已介入，重新检查当前交付物。",
                metadata_json={"orchestrator": "human_resume", "origin": origin},
            ))
            await db.commit()

    while True:
        mod, run, product = await _load_module_context(db, module_id)
        if mod is None:
            return "module_not_found"
        blocked = _run_block_reason(run, product)
        if blocked:
            return blocked
        if mod.phase == "baselined":
            return "baselined"
        if mod.execution_mode == "human_driven" and origin != "human_confirmed":
            return "awaiting_human_confirm"

        artifacts = await _module_artifacts(db, module_id)
        if not artifacts:
            return "no_artifact"

        platform = (product.platform if product else None) or "ios"
        zero_inf = True if not product or product.client_zero_inference is None else bool(product.client_zero_inference)
        latest_version = artifacts[-1].version
        latest_artifacts = [a for a in artifacts if a.version == latest_version]
        texts = artifact_audit_texts(latest_artifacts)
        from backend.app.services.delivery_contract import manifest_from_texts, stage_directory

        audit = audit_stage(
            mod.module_code,
            texts,
            platform=platform,
            client_zero_inference=zero_inf,
            price_baseline=await load_price_baseline(db, mod),
            manifest_root=stage_directory(artifacts),
        )
        session = await _get_or_create_session(db, module_id)
        compliance = await audit_module_compliance(
            db, mod.module_code, product, artifacts[-1].content or "",
            manifest=manifest_from_texts(texts),
        )
        base_gate = get_stage_gate_config(mod.module_code, run.template_id if run else None)
        compliance_blocks_lead = (
            compliance is not None
            and compliance["status"] == "needs_fix"
            and base_gate.get("level") == "green"
        )

        if not audit.get("passed") or compliance_blocks_lead:
            reasons = [str(r) for r in (audit.get("reasons") or [])] if not audit.get("passed") else []
            if compliance_blocks_lead:
                reasons += compliance_failed_items(compliance)
            reasons = reasons or ["交付物检查未通过"]
            if origin == "human_confirmed":
                await _raise_stuck(db, product, mod, session, reasons, headline="重新检查仍未通过")
                return "stuck"
            if await _revisions_since_boundary(db, session.id) >= MAX_AUTO_REVISIONS:
                await _raise_stuck(db, product, mod, session, reasons, exhausted=True)
                return "stuck"
            feedback = "【自动检查未通过，请修订】\n" + "\n".join(f"- {r}" for r in reasons[:8])
            reply = await _post_and_run(db, session, feedback, "feedback", "revision", {"reasons": reasons[:8]})
            if not reply or not reply.artifact_ref_id:
                await _raise_stuck(db, product, mod, session, ["Agent 修订后没有产出交付物"] + reasons)
                return "stuck"
            continue

        signed = await _module_gate(db, module_id)
        if origin == "human_confirmed" and signed is not None and signed.status == "approved":
            ok, _reason = await _finalize(db, module_id)
            return "baselined" if ok else "finalize_blocked"

        reviews = [] if review_override else await _collaboration_reviews(db, mod, product, session, artifacts[-1])
        blocking = [r for r in reviews if r.get("verdict") == "request_changes"]
        if blocking:
            reasons = [
                f"【{r['reviewer']} 评审：需修订】{f}"
                for r in blocking for f in (r.get("findings") or ["要求修订"])
            ]
            if origin == "human_confirmed":
                await _raise_stuck(db, product, mod, session, reasons, headline="重新检查仍未通过")
                return "stuck"
            if await _revisions_since_boundary(db, session.id) >= MAX_AUTO_REVISIONS:
                await _raise_dispute(db, product, mod, session, blocking)
                return "dispute"
            feedback = "【协作评审未通过，请修订】\n" + "\n".join(f"- {r}" for r in reasons[:8])
            reply = await _post_and_run(
                db, session, feedback, "feedback", "revision", {"reasons": reasons[:8], "from_review": True}
            )
            if not reply or not reply.artifact_ref_id:
                await _raise_stuck(db, product, mod, session, ["Agent 修订后没有产出交付物"] + reasons)
                return "stuck"
            continue

        context = _structured_context(merged_fields(texts))
        from backend.app.services.gate_copy import (
            compliance_note, describe_passed_stage, flag_note, review_note,
        )
        brief = describe_passed_stage(mod.module_code, mod.name, audit)
        evidence: List[Any] = [{
            "checker": "deliverable_audit",
            "passed": True,
            "module_code": mod.module_code,
            "score": audit.get("score"),
            "artifact_version": artifacts[-1].version,
            "summary": brief["evidence"],
        }]
        risk_parts = [brief["risk"]]
        if audit.get("red_flags"):
            risk_parts.append(flag_note(list(audit["red_flags"])))
        if compliance:
            failed = compliance_failed_items(compliance)
            note = "\n".join(failed) if failed else compliance_note(compliance)
            evidence.append({
                "checker": "compliance_engine",
                "status": compliance["status"],
                "risk_level": compliance["risk_level"],
                "summary": note,
                "findings": failed,
            })
            if compliance["status"] == "legal_review":
                risk_parts.append(note)
            if compliance["is_g5_escalated"]:
                context["is_compliance_high_risk_related"] = True
        if reviews or review_override:
            crs = await _file_review_crs(db, mod, reviews)
            for cr in crs:
                if cr["escalated"]:
                    context["is_high_risk_cr_related"] = True
                    for flag in cr["flags"]:
                        context[flag] = True
            note = review_note(reviews, review_override, crs)
            evidence.append({
                "checker": "collaboration_review",
                "artifact_version": artifacts[-1].version,
                "summary": note,
                "results": [
                    {k: r.get(k) for k in ("reviewer", "kind", "focus", "verdict", "findings")}
                    for r in reviews
                ],
                "change_requests": crs,
                "overridden_by": review_override,
            })
            if note:
                risk_parts.append(note)
        gate = await create_or_update_gate_application(
            db=db,
            module_id=module_id,
            recommendation=brief["recommendation"],
            evidence=evidence,
            risk_assessment="\n".join(part for part in risk_parts if part),
            submitted_by=f"agent:{mod.primary_role_code or 'lead'}",
            context=context,
        )
        if compliance:
            await run_stage_compliance_check(db, module_id)
            gate = await _module_gate(db, module_id) or gate
        gate, _ = await evaluate_gate_by_lead(db=db, gate_id=gate.id)
        gate = await _qa_quality_gate(db, gate, product, audit)
        _write_audit(product, "GATE_SUBMITTED", {
            "module_code": mod.module_code,
            "gate_id": gate.id,
            "effective_level": gate.effective_level,
            "status": gate.status,
            "lead_recommendation": gate.lead_recommendation,
        })
        if gate.status != "approved":
            return "awaiting_gate"
        ok, _reason = await _finalize(db, module_id)
        return "baselined" if ok else "finalize_blocked"


def _handoff_repair_brief(upstream: ModuleInstance, downstream: ModuleInstance, anchors: List[str]) -> str:
    return "\n".join([
        f"【交接补缺】工序 {downstream.module_code} {downstream.name} 开工前，"
        f"工序 {upstream.module_code} 已定稿基线缺少：{'、'.join(anchors)}。",
        "请在现有基线上升成新版本，补上这些锚点，并让本工序确定性检查能够通过。",
        "工序 04、05 的锚点写在 delivery.manifest.json 的对应字段里，并与正文一起改。",
        "不要改已经由负责人签过字的支付、隐私、密钥或数据字典结论。",
        "只有补写本身新出现这类事项时，才在交付物里写对应的结构化标记。",
    ])


async def _ensure_handoff_repair_boundary(db: AsyncSession, session: CollaborationSession) -> None:
    """One marker per repair cycle, so earlier revisions do not spend this cycle's budget."""
    res = await db.execute(
        select(SessionMessage).where(SessionMessage.session_id == session.id).order_by(SessionMessage.created_at.desc())
    )
    for msg in res.scalars().all():
        kind = (msg.metadata_json or {}).get("orchestrator")
        if kind == "revision":
            continue
        if kind == "handoff_repair":
            return
        if kind in ("dispatch", "gate_feedback", "human_resume", "handoff_repair_done") or msg.sender_role == "human":
            break
    db.add(SessionMessage(
        session_id=session.id,
        sender=ORCH_SENDER,
        sender_role="system",
        role_code="lead",
        message_type="instruction",
        content="下游开工时发现本工序基线缺少交接锚点，开始补缺。",
        metadata_json={"orchestrator": "handoff_repair"},
    ))
    await db.commit()


async def _restore_baseline(db: AsyncSession, mod: ModuleInstance, artifact_id: str) -> None:
    mod.baseline_artifact_id = artifact_id
    mod.phase = "baselined"
    for art in await _module_artifacts(db, mod.id):
        art.is_baseline = art.id == artifact_id
        db.add(art)
    db.add(mod)
    await db.commit()


async def _hold_revision_for_new_flags(
    db: AsyncSession,
    product: Optional[Product],
    upstream: ModuleInstance,
    session: CollaborationSession,
    previous_id: str,
    new_text: str,
    added: List[str],
) -> None:
    """Keep the signed baseline in place and ask a human to approve the new flags."""
    from backend.app.services.deliverable_audit import merged_fields
    from backend.app.services.gate_keeper import create_or_update_gate_application

    upstream.baseline_artifact_id = previous_id
    upstream.phase = "discussing"
    for art in await _module_artifacts(db, upstream.id):
        art.is_baseline = art.id == previous_id
        db.add(art)
    db.add(upstream)
    db.add(SessionMessage(
        session_id=session.id,
        sender=ORCH_SENDER,
        sender_role="system",
        role_code="lead",
        message_type="error",
        content=(
            "补写带上新的红级标记（" + "、".join(added) + "），已停下等负责人确认。"
            "原先的签字不能覆盖这次新增的标记。"
        ),
        metadata_json={"orchestrator": "handoff_hold", "added_flags": added},
    ))
    await db.commit()
    await create_or_update_gate_application(
        db=db,
        module_id=upstream.id,
        recommendation=f"补上的交接内容里新出现了需要您看的事项（{'、'.join(added)}）。原来签过的部分仍然有效。",
        evidence=[{
            "checker": "handoff_repair",
            "added_flags": added,
            "summary": "补写带上了新的敏感事项。您之前的签字仍然覆盖旧内容，只需要确认这次新加的部分。",
        }],
        risk_assessment="原来的签字继续有效。这次只请您确认补写里新出现的事项。",
        submitted_by=f"agent:{upstream.primary_role_code or 'lead'}",
        context=_structured_context(merged_fields([new_text])),
    )
    await db.commit()
    _write_audit(product, "HANDOFF_REPAIR_NEEDS_SIGNATURE", {
        "module_code": upstream.module_code,
        "module_id": upstream.id,
        "added_flags": added,
    })


async def _repair_handoff(
    db: AsyncSession,
    product: Optional[Product],
    downstream: ModuleInstance,
    gaps: List[Dict[str, str]],
) -> str:
    """Send missing anchors back to a baselined upstream. Returns repaired, stuck, awaiting_gate, or busy."""
    from backend.app.services.agent_runner import get_session_lock
    from backend.app.services.compliance_engine import audit_module_compliance, compliance_failed_items
    from backend.app.services.deliverable_audit import artifact_audit_texts, audit_stage
    from backend.app.services.workflow_engine import load_price_baseline

    modules = (await db.execute(
        select(ModuleInstance).where(ModuleInstance.run_id == downstream.run_id)
    )).scalars().all()
    by_code = {m.module_code: m for m in modules}
    upstream_code = gaps[0]["upstream"]
    owned = [g for g in gaps if g["upstream"] == upstream_code]
    anchors = [g["anchor"] for g in owned]
    upstream = by_code.get(upstream_code)
    if upstream is None or not upstream.baseline_artifact_id:
        return "stuck"

    if await _stuck_risk(db, product, upstream):
        return "stuck"
    gate = await _module_gate(db, upstream.id)
    if upstream.phase != "baselined" and gate is not None and gate.status == "pending":
        return "awaiting_gate"

    session = await _get_or_create_session(db, upstream.id)
    if get_session_lock(session.id).locked():
        return "busy"
    await _ensure_handoff_repair_boundary(db, session)

    platform = (product.platform if product else None) or "ios"
    zero_inf = True if product is None or product.client_zero_inference is None else bool(product.client_zero_inference)
    while True:
        await db.refresh(upstream)
        if await _revisions_since_boundary(db, session.id) >= MAX_AUTO_REVISIONS:
            await _raise_stuck(
                db, product, upstream, session, [f"交接补缺仍缺少：{a}" for a in anchors], exhausted=True,
            )
            return "stuck"
        previous_id = upstream.baseline_artifact_id
        previous = (await db.execute(select(Artifact).where(Artifact.id == previous_id))).scalar_one_or_none()
        old_text = previous.content if previous else ""
        from backend.app.services.delivery_contract import manifest_from_texts, stage_directory

        old_texts = artifact_audit_texts([previous]) if previous else [old_text]
        old_root = stage_directory([previous] if previous else [])
        reply = await _post_and_run(
            db, session, _handoff_repair_brief(upstream, downstream, anchors), "feedback", "revision",
            {"handoff_repair": True, "anchors": anchors},
        )
        await db.refresh(upstream)
        if not reply or not reply.artifact_ref_id:
            if previous_id:
                await _restore_baseline(db, upstream, previous_id)
            continue
        new_art = (await db.execute(select(Artifact).where(Artifact.id == reply.artifact_ref_id))).scalar_one_or_none()
        new_text = new_art.content if new_art else ""
        from backend.app.services.collaboration import anchor_satisfied

        new_texts = artifact_audit_texts([new_art]) if new_art else [new_text]
        missing = [g["anchor"] for g in owned if not anchor_satisfied(g, "\n".join(new_texts))]
        price_baseline = await load_price_baseline(db, upstream)
        audit = audit_stage(
            upstream.module_code,
            new_texts,
            platform=platform,
            client_zero_inference=zero_inf, price_baseline=price_baseline,
            manifest_root=stage_directory([new_art] if new_art else []),
        )
        old_audit = audit_stage(
            upstream.module_code,
            old_texts,
            platform=platform,
            client_zero_inference=zero_inf, price_baseline=price_baseline,
            manifest_root=old_root,
        )
        reasons = list(missing)
        if not audit.get("passed"):
            reasons.extend(str(r) for r in (audit.get("reasons") or ["交付物检查未通过"])[:5])
        compliance = await audit_module_compliance(
            db, upstream.module_code, product, new_text, manifest=manifest_from_texts(new_texts),
        )
        legal_review = bool(compliance and compliance.get("status") == "legal_review")
        if compliance and compliance.get("status") == "needs_fix":
            reasons.extend(compliance_failed_items(compliance)[:5])
        if reasons:
            if previous_id:
                await _restore_baseline(db, upstream, previous_id)
            continue
        added = sorted(set(audit.get("red_flags") or []) - set(old_audit.get("red_flags") or []))
        if legal_review and "compliance_high_risk" not in added:
            added.append("compliance_high_risk")
        if added:
            await _hold_revision_for_new_flags(db, product, upstream, session, previous_id, new_text, added)
            return "awaiting_gate"
        ok, _reason = await _finalize(db, upstream.id)
        if not ok:
            if previous_id:
                await _restore_baseline(db, upstream, previous_id)
            continue
        db.add(SessionMessage(
            session_id=session.id,
            sender=ORCH_SENDER,
            sender_role="system",
            role_code="lead",
            message_type="instruction",
            content=f"交接锚点已补上（{'、'.join(anchors)}），基线已更新。",
            metadata_json={"orchestrator": "handoff_repair_done", "anchors": anchors},
        ))
        await db.commit()
        _write_audit(product, "HANDOFF_REPAIRED", {
            "module_code": upstream.module_code,
            "module_id": upstream.id,
            "downstream": downstream.module_code,
            "anchors": anchors,
        })
        return "repaired"


async def _advance(db: AsyncSession, run_id: str) -> Dict[str, Any]:
    from backend.app.services.agent_runner import get_session_lock

    dispatched: List[str] = []
    processed: List[str] = []
    attempted: set = set()
    task_error: Optional[str] = None

    def outcome(status: str) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "run_id": run_id, "status": status, "dispatched": dispatched, "processed": processed,
        }
        if task_error:
            payload["task_error"] = task_error
        return payload

    while True:
        run, product = await _load_run(db, run_id)
        blocked = _run_block_reason(run, product)
        if blocked:
            return outcome(blocked)

        from backend.app.services.workflow_engine import unlock_downstream_modules
        await unlock_downstream_modules(db, run_id)

        modules = (await db.execute(
            select(ModuleInstance).where(ModuleInstance.run_id == run_id).order_by(ModuleInstance.order_index.asc())
        )).scalars().all()

        target = None
        action = None
        repaired = False
        for m in modules:
            if m.id in attempted or not m.is_unlocked or m.phase == "baselined":
                continue
            if await _stuck_risk(db, product, m):
                continue
            artifacts = await _module_artifacts(db, m.id)
            gate = await _module_gate(db, m.id)
            if not artifacts:
                held = (await db.execute(
                    select(CollaborationSession).where(CollaborationSession.module_id == m.id)
                )).scalars().first()
                if held and await _dispatch_hold(db, held.id):
                    continue
                gaps = await _handoff_gaps(db, m)
                if gaps:
                    await _flag_handoff_gaps(db, product, m, gaps)
                    status = await _repair_handoff(db, product, m, gaps)
                    if status == "repaired":
                        repaired = True
                        break
                    attempted.add(m.id)
                    continue
                await _close_resolved_handoff_gaps(db, m)
                target, action = m, "dispatch"
                break
            if gate is None and m.execution_mode != "human_driven":
                target, action = m, "process"
                break
        if target is None:
            if repaired:
                continue
            return outcome("idle")

        attempted.add(target.id)
        session = await _get_or_create_session(db, target.id)
        if get_session_lock(session.id).locked():
            continue

        if action == "dispatch":
            dispatched.append(target.module_code)
            _write_audit(product, "STAGE_DISPATCHED", {"module_code": target.module_code, "module_id": target.id})
            reply = await _post_and_run(db, session, _dispatch_brief(target, product), "instruction", "dispatch")
            if not reply or not reply.artifact_ref_id:
                detail = reply.content if reply else "Agent 无响应"
                db.add(SessionMessage(
                    session_id=session.id,
                    sender=ORCH_SENDER,
                    sender_role="system",
                    role_code="lead",
                    message_type="error",
                    content=detail,
                    metadata_json={"orchestrator": "dispatch_miss"},
                ))
                await db.commit()
                if await _dispatch_misses(db, session.id) < MAX_AUTO_REVISIONS:
                    attempted.discard(target.id)
                    continue
                db.add(SessionMessage(
                    session_id=session.id,
                    sender=ORCH_SENDER,
                    sender_role="system",
                    role_code="lead",
                    message_type="error",
                    content="这一次执行没有产出",
                    metadata_json={"orchestrator": "dispatch_exhausted"},
                ))
                await db.commit()
                task_error = detail
                continue
        processed.append(target.module_code)
        await _process_artifact(db, target.id, origin="agent")


# ---------------------------------------------------------------------------
# Public entrypoints (each takes the per-run lock)
# ---------------------------------------------------------------------------

async def runs_waiting_for_push(db: AsyncSession) -> List[str]:
    """自动编排开着、却没有人接着推的迭代。

    审批或重新检查若在半路被打断，工序会停在「等待派活 / 等待检查」，
    队列里却没有任务。执行器用这个名单把它们捡回来。
    已经在等人类签字、或已经卡死的工序不在名单里。
    """
    runs = (await db.execute(select(WorkflowRun).where(and_(
        WorkflowRun.status == "in_progress",
        WorkflowRun.auto_advance == True,  # noqa: E712
    )))).scalars().all()
    waiting: List[str] = []
    for run in runs:
        product = (await db.execute(select(Product).where(Product.id == run.product_id))).scalar_one_or_none()
        if _run_block_reason(run, product):
            continue
        modules = (await db.execute(
            select(ModuleInstance).where(ModuleInstance.run_id == run.id).order_by(ModuleInstance.order_index.asc())
        )).scalars().all()
        for mod in modules:
            if not mod.is_unlocked or mod.phase == "baselined":
                continue
            if await _stuck_risk(db, product, mod):
                continue
            artifacts = await _module_artifacts(db, mod.id)
            gate = await _module_gate(db, mod.id)
            if not artifacts:
                held = (await db.execute(
                    select(CollaborationSession).where(CollaborationSession.module_id == mod.id)
                )).scalars().first()
                if held and await _dispatch_hold(db, held.id):
                    continue
            if not artifacts or (gate is None and mod.execution_mode != "human_driven"):
                waiting.append(run.id)
                break
    return waiting


async def advance_run(db: AsyncSession, run_id: str) -> Dict[str, Any]:
    async with get_run_lock(run_id):
        return await _advance(db, run_id)


async def request_redispatch(db: AsyncSession, module_id: str) -> str:
    """人要求把「没有产出」的工序再派一次。只清掉用尽标记，不提交关口。"""
    mod, run, product = await _load_module_context(db, module_id)
    if mod is None:
        return "module_not_found"
    if _run_block_reason(run, product):
        return "blocked"
    if await _module_artifacts(db, module_id):
        return "has_artifact"
    session = await _get_or_create_session(db, module_id)
    if not await _dispatch_hold(db, session.id):
        return "not_exhausted"
    db.add(SessionMessage(
        session_id=session.id,
        sender=ORCH_SENDER,
        sender_role="system",
        role_code="lead",
        message_type="instruction",
        content="请重新派活",
        metadata_json={"orchestrator": "redispatch"},
    ))
    await db.commit()
    return "ready"


async def on_artifact_created(db: AsyncSession, module_id: str, origin: str = "agent") -> str:
    mod, _run, _product = await _load_module_context(db, module_id)
    if mod is None:
        return "module_not_found"
    async with get_run_lock(mod.run_id):
        status = await _process_artifact(db, module_id, origin)
        if status == "baselined":
            await _advance(db, mod.run_id)
        return status


async def finalize_and_advance(db: AsyncSession, module_id: str) -> Tuple[bool, str]:
    mod, _run, _product = await _load_module_context(db, module_id)
    if mod is None:
        return False, "module_not_found"
    async with get_run_lock(mod.run_id):
        if mod.phase == "baselined":
            ok, reason = True, ""
        else:
            ok, reason = await _finalize(db, module_id)
        if ok:
            await _advance(db, mod.run_id)
        return ok, reason


async def on_gate_reviewed(db: AsyncSession, gate_id: str) -> str:
    gate = (await db.execute(select(GateApplication).where(GateApplication.id == gate_id))).scalar_one_or_none()
    if not gate or gate.status == "pending":
        return "ignored"
    if gate.status == "approved":
        ok, _ = await finalize_and_advance(db, gate.module_id)
        return "baselined" if ok else "finalize_blocked"

    mod, run, product = await _load_module_context(db, gate.module_id)
    if mod is None or _run_block_reason(run, product):
        return "skipped"
    async with get_run_lock(mod.run_id):
        session = await _get_or_create_session(db, mod.id)
        verdict = "打回" if gate.status == "rejected" else "要求调整"
        feedback = f"【负责人{verdict}关口「{gate.gate_name}」】\n{gate.review_comment or '请根据关口意见修订交付物。'}"
        reply = await _post_and_run(db, session, feedback, "feedback", "gate_feedback", {"gate_id": gate.id})
        if not reply or not reply.artifact_ref_id:
            return "no_revision"
        status = await _process_artifact(db, mod.id, origin="agent")
        if status == "baselined":
            await _advance(db, mod.run_id)
        return status


async def resolve_dispute(
    db: AsyncSession, module_id: str, decision: str, actor: str, comment: str = ""
) -> str:
    """Human ruling on an ORCH_DISPUTE: accept_review sends the reviewer's findings back; override_review proceeds without them."""
    mod, run, product = await _load_module_context(db, module_id)
    if mod is None:
        return "module_not_found"
    dispute = await _open_risk(db, product, mod, DISPUTE_RULE_PREFIX)
    if dispute is None:
        return "no_dispute"
    async with get_run_lock(mod.run_id):
        session = await _get_or_create_session(db, mod.id)
        dispute.is_resolved = True
        dispute.action_suggestion = f"{actor} 裁决：{'采纳评审意见' if decision == 'accept_review' else '否决评审意见'}"
        db.add(dispute)
        db.add(SessionMessage(
            session_id=session.id,
            sender=actor,
            sender_role="human",
            role_code="human",
            message_type="instruction",
            content=(
                f"【负责人裁决协作评审分歧：{'采纳评审意见，请按评审意见修订' if decision == 'accept_review' else '否决评审意见，按当前交付物继续'}】"
                + (f"\n{comment}" if comment else "")
            ),
            metadata_json={"orchestrator": "dispute_resolution", "decision": decision},
        ))
        await db.commit()
        _write_audit(product, "DISPUTE_RESOLVED", {
            "module_code": mod.module_code, "module_id": mod.id, "decision": decision, "actor": actor, "comment": comment,
        })
        if _run_block_reason(run, product):
            return "recorded"
        if decision == "override_review":
            status = await _process_artifact(db, mod.id, origin="human_confirmed", review_override=actor)
        else:
            last = (await db.execute(
                select(SessionMessage).where(SessionMessage.session_id == session.id)
                .order_by(SessionMessage.created_at.desc())
            )).scalars().all()
            blocking = next(
                ((m.metadata_json or {}).get("reviews") or [] for m in last
                 if (m.metadata_json or {}).get("orchestrator") == "dispute"),
                [],
            )
            findings = [f"【{r['reviewer']} 评审：需修订】{f}" for r in blocking for f in (r.get("findings") or [])]
            feedback = "【负责人采纳评审意见，请按以下意见修订】\n" + "\n".join(f"- {f}" for f in findings[:8])
            reply = await _post_and_run(db, session, feedback, "feedback", "revision", {"reasons": findings[:8]})
            if mod.execution_mode == "human_driven":
                return "awaiting_human_confirm"
            if not reply or not reply.artifact_ref_id:
                await _raise_stuck(db, product, mod, session, ["Agent 修订后没有产出交付物"] + findings)
                return "stuck"
            status = await _process_artifact(db, mod.id, origin="agent")
        if status == "baselined":
            await _advance(db, mod.run_id)
        return status


async def get_run_orchestration_status(db: AsyncSession, run_id: str) -> Dict[str, Any]:
    from backend.app.services.agent_runner import get_session_lock

    run, product = await _load_run(db, run_id)
    if run is None:
        return {"run_id": run_id, "found": False}

    run_block = _run_block_reason(run, product)
    modules = (await db.execute(
        select(ModuleInstance).where(ModuleInstance.run_id == run_id).order_by(ModuleInstance.order_index.asc())
    )).scalars().all()

    stages: List[Dict[str, Any]] = []
    for m in modules:
        if m.phase == "baselined" or not m.is_unlocked:
            continue
        gate = await _module_gate(db, m.id)
        artifacts = await _module_artifacts(db, m.id)
        session = (await db.execute(
            select(CollaborationSession).where(CollaborationSession.module_id == m.id)
        )).scalars().first()
        stuck = await _open_risk(db, product, m, STUCK_RULE_PREFIX)
        dispute = await _open_risk(db, product, m, DISPUTE_RULE_PREFIX)
        gaps = await _handoff_gaps(db, m) if not artifacts else []

        if m.id in _reviewing:
            state, detail = "in_review", "协作角色正在评审交付物"
        elif session and get_session_lock(session.id).locked():
            state, detail = "running", "Agent 正在产出交付物"
        elif product is not None and product.stage == "paused":
            state, detail = "paused", product.key_risk or "项目已熔断暂停"
        elif dispute:
            state, detail = "dispute", dispute.description
        elif stuck:
            state, detail = "revision_failed", stuck.description
        elif gaps:
            state = "handoff_incomplete"
            detail = "上游基线缺少交接锚点：" + "、".join(f"工序 {g['upstream']} {g['anchor']}" for g in gaps)
        elif gate is not None and gate.status == "pending":
            who = "人类负责人" if gate.effective_level in ("yellow", "red") or m.module_code == "09" else "人类（影子模式下确认绿级）"
            state = "awaiting_human_gate"
            detail = f"{gate.gate_name}（{gate.effective_level}）待{who}审批"
        elif gate is not None and gate.status in ("rejected", "needs_adjustment"):
            state, detail = "gate_returned", gate.review_comment or "关口被打回，等待修订"
        elif artifacts and m.execution_mode == "human_driven" and gate is None:
            state, detail = "awaiting_human_confirm", "真人主导工序：请上传或确认交付物后提交检查"
        elif not artifacts and session and await _dispatch_hold(db, session.id):
            state, detail = "dispatch_failed", "这一次执行没有产出"
        elif not artifacts:
            state, detail = "ready", "等待派活"
        else:
            state, detail = "ready", "等待检查"
        stages.append({
            "module_id": m.id,
            "module_code": m.module_code,
            "name": m.name,
            "execution_mode": m.execution_mode,
            "state": state,
            "detail": detail,
            "gate_id": gate.id if gate else None,
        })

    from backend.app.services.job_queue import queue_snapshot

    queue = await queue_snapshot(db, run_id)
    if queue["running"]:
        for stage in stages:
            if stage["state"] != "ready":
                continue
            stage["state"] = "running"
            stage["detail"] = (
                "正在派给这一工序的主责"
                if stage["detail"] == "等待派活"
                else "正在检查这一版交付物"
            )
            break

    return {
        "run_id": run_id,
        "found": True,
        "auto_advance": bool(run.auto_advance),
        "orchestrator_enabled": orchestration_enabled(),
        "run_block_reason": run_block,
        "current_stage": stages[0] if stages else None,
        "active_stages": stages,
        "queue": queue,
    }
