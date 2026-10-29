from typing import Tuple, Dict, Any, List, Optional
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.app.core.config import settings
from backend.app.models.entities import (
    ModuleInstance,
    WorkflowRun,
    Product,
    StrategicInitiative,
    Artifact,
    AgentRoleDefinition,
    GateApplication,
    Issue,
    CollaborationSession,
    SessionMessage,
)
from backend.app.services.stage_memory import (
    deliverable_filename,
    issue_summary_text,
    pending_revision_notes,
    render_stage_progress,
)
from backend.app.services.workspace_sync import sanitize_dirname
from backend.app.services.agent_roles import render_persona


async def _handoff_anchor_lines(
    db: AsyncSession,
    module_code: str,
    all_mods: List[ModuleInstance],
    baselined_artifacts: List[Dict[str, Any]],
) -> List[str]:
    """Contract anchors this stage must build on, plus what upstream reviewers flagged when those stages passed."""
    import re
    from backend.app.services.collaboration import HANDOFF_REQUIREMENTS, handoff_anchor_fields

    from backend.app.services.deliverable_audit import audit_som

    by_code = {b["module_code"]: b for b in baselined_artifacts}
    lines: List[str] = []
    for req in HANDOFF_REQUIREMENTS.get(str(module_code), []):
        base = by_code.get(req["upstream"])
        if not base:
            continue
        if req.get("computed") == "som":
            audit = audit_som([base["content"] or ""])
            som = audit.get("first_year_som_usd")
            shown = f"{float(som):,.2f} 美元（由月搜索量、取得比例和客单价算出）" if som is not None else "未找到"
            lines.append(f"- 工序 {req['upstream']} · {req['anchor']}：{shown}")
            continue
        hits = [ln.strip() for ln in (base["content"] or "").splitlines() if re.search(req["pattern"], ln)]
        lines.append(f"- 工序 {req['upstream']} · {req['anchor']}：" + (" / ".join(hits[:6])[:600] if hits else "未找到"))
    for code in sorted({r["upstream"] for r in HANDOFF_REQUIREMENTS.get(str(module_code), [])}):
        base = by_code.get(code)
        fields = handoff_anchor_fields(base["content"] or "") if base else {}
        if fields:
            lines.append(f"- 工序 {code} 结构化字段：" + ", ".join(f"{k}={v}" for k, v in list(fields.items())[:12]))

    upstream_ids = {m.id: m.module_code for m in all_mods if m.module_code in by_code}
    if upstream_ids:
        gates = (await db.execute(
            select(GateApplication).where(GateApplication.module_id.in_(list(upstream_ids)))
        )).scalars().all()
        for gate in gates:
            for ev in gate.evidence or []:
                if not isinstance(ev, dict) or ev.get("checker") != "collaboration_review":
                    continue
                for r in ev.get("results") or []:
                    if r.get("findings"):
                        lines.append(
                            f"- 工序 {upstream_ids[gate.module_id]} 评审备注（{r.get('reviewer')}）："
                            + "；".join(map(str, r["findings"]))[:300]
                        )
                for cr in ev.get("change_requests") or []:
                    lines.append(f"- 遗留 CR（{cr.get('reviewer')} → 工序 {cr.get('target_stage')}）：{cr.get('summary')}")
    return lines


async def assemble_module_context(
    db: AsyncSession,
    module_id: str,
    user_instruction: str,
    role_override: Optional[str] = None,
) -> Tuple[str, Path, Dict[str, Any]]:
    """
    Assembles a complete, multi-layered strategic context for the Agent:
    - Layer 1: Mother Strategic Initiative Blueprint (Macro intent, target market, business model hypothesis)
    - Layer 2: Product Role & Commercial Positioning
    - Layer 3: Upstream Baselined Artifacts (PRD, Architecture, etc. that have been locked)
    - Layer 4: This stage's own draft, open issues, and feedback not yet written into that draft
    - Layer 5: Current Module Requirements & Human Instruction

    Returns:
    - context_markdown: Full context string to feed into Agent CLI / LLM
    - workspace_path: Specific physical directory on disk for this module
    - metadata: Dictionary containing product_code, module_code, etc.
    """
    # 1. Query module with full hierarchy
    stmt = (
        select(ModuleInstance)
        .options(
            selectinload(ModuleInstance.workflow_run)
            .selectinload(WorkflowRun.product)
            .selectinload(Product.initiative)
        )
        .where(ModuleInstance.id == module_id)
    )
    res = await db.execute(stmt)
    mod = res.scalar_one_or_none()
    if not mod:
        raise ValueError(f"Module '{module_id}' not found")

    run = mod.workflow_run
    prod = run.product
    init = prod.initiative

    # 2. Query all upstream baselined artifacts in the same run
    all_mods_stmt = (
        select(ModuleInstance)
        .options(selectinload(ModuleInstance.artifacts))
        .where(ModuleInstance.run_id == run.id)
        .order_by(ModuleInstance.order_index.asc())
    )
    all_mods_res = await db.execute(all_mods_stmt)
    all_mods = all_mods_res.scalars().all()

    baselined_artifacts: List[Dict[str, str]] = []
    for m in all_mods:
        if m.order_index < mod.order_index and (m.phase == "baselined" or m.baseline_artifact_id):
            # Find the baseline artifact
            baseline_art = next((a for a in m.artifacts if a.is_baseline), None)
            if not baseline_art and m.artifacts:
                baseline_art = m.artifacts[0]
            if baseline_art:
                from backend.app.services.delivery_contract import read_manifest_text

                content = baseline_art.content or ""
                manifest_text = read_manifest_text(getattr(baseline_art, "storage_rel_path", None))
                if manifest_text.strip() and manifest_text.strip() not in content:
                    content = f"{content}\n```json\n{manifest_text.strip()}\n```\n"
                baselined_artifacts.append({
                    "module_name": m.name,
                    "module_code": m.module_code,
                    "title": baseline_art.title,
                    "version": baseline_art.version,
                    "content": content,
                })

    # 3. Compute physical workspace directory
    init_dir_name = sanitize_dirname(init.id if init else "standalone")
    prod_code_name = sanitize_dirname(prod.code)
    run_name = sanitize_dirname(run.name)
    mod_dir_name = f"{mod.order_index:02d}_{mod.module_code}_{sanitize_dirname(mod.name)}"

    workspace_path = settings.WORKSPACE_DIR / init_dir_name / "products" / prod_code_name / run_name / mod_dir_name
    workspace_path.mkdir(parents=True, exist_ok=True)

    # 4. Retrieve Agent Role Persona and Collaboration Bundle
    from backend.app.services.agent_roles import get_module_role_bundle
    from backend.app.services.skill_mcp_mounter import mount_role_skills_and_mcp
    role_bundle = await get_module_role_bundle(db, mod.module_code)
    primary_role = role_bundle.get("primary_role")
    collab_roles = role_bundle.get("collaborator_roles", [])
    stage_cfg = role_bundle.get("config", {})

    primary_role_code = primary_role.role_code if primary_role else "pm"
    collab_role_codes = [c.role_code for c in collab_roles]
    arsenal_info = mount_role_skills_and_mcp(
        workspace_dir=workspace_path,
        primary_role_code=primary_role_code,
        collaborator_role_codes=collab_role_codes,
        platform=getattr(prod, "platform", "ios") or "ios",
        client_zero_inference=getattr(prod, "client_zero_inference", True)
    )

    collab_desc = "、".join([f"{c.name} ({c.title})" for c in collab_roles]) if collab_roles else "无"

    if role_override and role_override != primary_role_code:
        override_role = (await db.execute(
            select(AgentRoleDefinition).where(AgentRoleDefinition.role_code == role_override)
        )).scalar_one_or_none()
        if override_role is not None:
            collab_desc = f"本次以协作评审身份驻场，主责角色为 {primary_role.name if primary_role else primary_role_code}"
            primary_role = override_role

    # 5. Format multi-layered context
    context_lines = [
        f"# 【ModuFlow 智能体研发上下文】",
        f"> 当前工序：`{mod.module_code}` - **{mod.name}**",
        f"> 目标产品：`{prod.code}` - **{prod.name}**",
        f"> 迭代周期：**{run.name}**",
        f"> 物理工作空间：`{workspace_path}`",
        f"> 当前驻场主责 Agent：**{primary_role.name if primary_role else 'AI 智能体'}** ({primary_role.title if primary_role else ''})",
        "",
        "---",
        "## 一、战略工程顶层底稿 (Mother Strategic Blueprint)",
    ]

    if init:
        context_lines.extend([
            f"- **所属战略工程**：{init.name} (`{init.id}`)",
            f"- **战略负责人**：{init.owner}",
            f"- **战略状态**：`{init.status.upper()}`",
            f"- **战略定性 (Strategic Intent)**：{init.strategic_intent or '未设定'}",
            f"- **目标市场 (Target Market)**：{init.target_market or '未设定'}",
            f"- **商业模式假设 (Business Model Hypothesis)**：{init.business_model_hypothesis or '未设定'}",
        ])
    else:
        context_lines.append("- *(当前产品为独立产品，未关联战略工程)*")

    context_lines.extend([
        "",
        "---",
        "## 二、本单品商业角色与定位 (Product Positioning)",
        f"- **产品代码**：`{prod.code}`",
        f"- **产品全称**：{prod.name}",
        f"- **在战役矩阵中的角色**：`{prod.strategic_role}` (流量入口/变现中枢/留存/基建)",
        f"- **当前生命周期阶段**：`{prod.stage}`",
        f"- **核心 KPI 预期**：{prod.kpi_name or 'KPI'} 目标 {prod.kpi_target or 0} {prod.kpi_unit or ''}",
        f"- **重点风险防范**：{prod.key_risk or '无显著风险'}",
        "",
        "---",
        "## 三、前序已封版工序交付物 (Upstream Baselined Facts)",
    ])

    if baselined_artifacts:
        from backend.app.services.deliverable_audit import handoff_som_text

        for b in baselined_artifacts:
            content = b["content"].strip()
            if b["module_code"] == "01":
                content = handoff_som_text(content).strip()
            context_lines.extend([
                f"### 📍 工序 {b['module_code']}：{b['module_name']} (基线: {b['title']} v{b['version']})",
                "```markdown",
                content,
                "```",
                ""
            ])
    else:
        context_lines.append("- *(当前无前序封版基线交付物，本工序为当前链条首道或前序正在论证中)*")

    handoff_lines = await _handoff_anchor_lines(db, mod.module_code, all_mods, baselined_artifacts)
    if handoff_lines:
        context_lines.extend(["", "---", "## 上游交接锚点 (Handoff Anchors)", *handoff_lines])

    # Role Persona Injection
    if primary_role:
        context_lines.extend([
            "",
            "---",
            "## 四、本次工序驻场 Agent 角色档案与独有 Skill / MCP 武器库 (Resident Agent Role & Arsenal)",
            f"- **当前执业角色**：**{primary_role.name}**（{primary_role.title}）",
            f"- **核心岗位职责**：{primary_role.responsibilities}",
            f"- **工序战略重点**：{stage_cfg.get('mission_focus', '业务规范推演')}",
            f"- **协同作战参谋**：{collab_desc}",
            f"- **已挂载独有 Skill 技能包**：`{', '.join(arsenal_info['mounted_skills'])}`（路径：`.agents/skills/`）",
            f"- **已挂载专属 MCP 服务**：`{', '.join(arsenal_info['mounted_mcp_servers'])}`（配置：`.agents/mcp_config.json`）",
            "",
            "**专业作业守则与思维准则**：",
            render_persona(primary_role.role_code, primary_role.system_persona, prod.platform, prod.client_zero_inference),
        ])

    current_mod = next((m for m in all_mods if m.id == mod.id), None)
    latest = None
    if current_mod and current_mod.artifacts:
        latest = max(current_mod.artifacts, key=lambda item: item.version or 0)
    draft_text = (latest.content or "") if latest else ""
    draft_filename = deliverable_filename(mod.module_code, mod.name)
    open_issue_rows = (await db.execute(
        select(Issue).where(Issue.target_module_id == mod.id, Issue.status != "closed")
    )).scalars().all()
    message_rows = (await db.execute(
        select(SessionMessage)
        .join(CollaborationSession, CollaborationSession.id == SessionMessage.session_id)
        .where(CollaborationSession.module_id == mod.id)
        .order_by(SessionMessage.created_at.asc())
    )).scalars().all()
    progress = render_stage_progress(
        filename=draft_filename,
        draft_version=latest.version if latest else None,
        draft_content=draft_text,
        issues=[
            {
                "title": row.title,
                "category": row.category,
                "severity": row.severity,
                "status": row.status,
                "summary": issue_summary_text(row.description),
            }
            for row in open_issue_rows
        ],
        pending_notes=pending_revision_notes(
            [
                {
                    "message_type": row.message_type,
                    "content": row.content,
                    "created_at": row.created_at,
                }
                for row in message_rows
            ],
            draft_created_at=latest.created_at if latest else None,
            current_instruction=user_instruction,
        ),
        current_instruction=user_instruction,
    )
    context_lines.extend(["", "---", progress])

    context_lines.extend([
        "",
        "---",
        "## 五、人类指令与本次交付目标 (Human Instruction)",
        f"**人类负责人指令**：",
        f"> {user_instruction}",
        "",
        "**智能体履职守则（双层分层与反冗余铁律）**：",
        "1. 【置顶 30 秒拍板摘要卡】：交付物最顶部（标题正下方）必须固定输出 `## 负责人 30 秒拍板摘要卡 (Executive Gate)`（严格控制在 300 字以内），用极简要点列出：①本工序 3 条核心量化结论；②需人类负责人拍板确认的 2~3 个关键决策项；③移交下游的核心指标锚点。",
        "2. 【严禁跨工序复述抄写】：前序已封版基线中定稿的内容（如用户画像、竞品背景、价格阶梯），本工序直接写“继承工序 XX 基线”，绝对禁止再次画表重复抄写！",
        "3. 【篇幅克制与高密度干货】：剔除一切教科书式的长篇铺垫，工序 01~05 全文总篇幅严格控制在 2,000~3,500 字以内，下方执行层仅保留供下游 AI 读取的高密度表格与关键参数。",
        "4. 如发现前序基线与当前需求存在重大逻辑漏洞或商业风险，必须明确指出并建议提报问题单。",
    ])
    from backend.app.services.delivery_contract import manifest_instruction

    contract_rule = manifest_instruction(mod.module_code, draft_filename)
    if contract_rule:
        context_lines.append(contract_rule)

    context_markdown = "\n".join(context_lines)

    metadata = {
        "initiative_id": init.id if init else None,
        "initiative_name": init.name if init else None,
        "target_market": init.target_market if init else None,
        "strategic_intent": init.strategic_intent if init else None,
        "business_model_hypothesis": init.business_model_hypothesis if init else None,
        "product_id": prod.id,
        "product_name": prod.name,
        "product_code": prod.code,
        "platform": getattr(prod, "platform", "ios") or "ios",
        "client_zero_inference": True if getattr(prod, "client_zero_inference", True) is None else bool(prod.client_zero_inference),
        "run_id": run.id,
        "run_name": run.name,
        "module_id": mod.id,
        "module_code": mod.module_code,
        "module_name": mod.name,
        "workspace_path": str(workspace_path),
        "role_code": primary_role.role_code if primary_role else "pm",
        "role_name": primary_role.name if primary_role else "产品经理 Agent",
        "role_title": primary_role.title if primary_role else "高级产品总监",
        "mounted_skills": arsenal_info["mounted_skills"],
        "mounted_mcp_servers": arsenal_info["mounted_mcp_servers"],
        "has_stage_draft": bool(draft_text.strip()),
        "draft_filename": draft_filename,
        "draft_version": latest.version if latest and draft_text.strip() else None,
    }

    return context_markdown, workspace_path, metadata
