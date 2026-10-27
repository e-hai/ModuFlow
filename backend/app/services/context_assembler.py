from typing import Tuple, Dict, Any, List
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
    Artifact
)
from backend.app.services.workspace_sync import sanitize_dirname

async def assemble_module_context(
    db: AsyncSession,
    module_id: str,
    user_instruction: str
) -> Tuple[str, Path, Dict[str, Any]]:
    """
    Assembles a complete, multi-layered strategic context for the Agent:
    - Layer 1: Mother Strategic Initiative Blueprint (Macro intent, target market, business model hypothesis)
    - Layer 2: Product Role & Commercial Positioning
    - Layer 3: Upstream Baselined Artifacts (PRD, Architecture, etc. that have been locked)
    - Layer 4: Current Module Requirements & Human Instruction

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
                baselined_artifacts.append({
                    "module_name": m.name,
                    "module_code": m.module_code,
                    "title": baseline_art.title,
                    "version": baseline_art.version,
                    "content": baseline_art.content
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
        for b in baselined_artifacts:
            context_lines.extend([
                f"### 📍 工序 {b['module_code']}：{b['module_name']} (基线: {b['title']} v{b['version']})",
                "```markdown",
                b["content"].strip(),
                "```",
                ""
            ])
    else:
        context_lines.append("- *(当前无前序封版基线交付物，本工序为当前链条首道或前序正在论证中)*")

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
            primary_role.system_persona,
        ])

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
        "4. 如发现前序基线与当前需求存在重大逻辑漏洞或商业风险，必须明确指出并建议提报问题单。"
    ])

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
    }

    return context_markdown, workspace_path, metadata
