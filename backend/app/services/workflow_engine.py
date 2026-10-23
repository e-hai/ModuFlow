import hashlib
from typing import List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from backend.app.models.entities import (
    WorkflowTemplate,
    WorkflowRun,
    ModuleInstance,
    Artifact,
    Issue,
    CollaborationSession
)

DEFAULT_TEMPLATES = [
    {
        "id": "full-product-launch",
        "name": "完整产品研发 (13 模块)",
        "description": "从市场调研到运营分析的完整闭环流程，适合从零开始的全新业务线。",
        "modules_config": [
            {"code": "01", "name": "市场研究", "required": True},
            {"code": "02", "name": "商业模式分析", "required": True},
            {"code": "03", "name": "产品方向决策", "required": True},
            {"code": "04", "name": "低成本市场验证", "required": True},
            {"code": "05", "name": "产品方向确认", "required": True},
            {"code": "06", "name": "MVP 定义与 PRD", "required": True},
            {"code": "07", "name": "设计与可用性验证", "required": True},
            {"code": "08", "name": "技术可行性评估", "required": True},
            {"code": "09", "name": "开发实现", "required": True},
            {"code": "10", "name": "测试与 QA", "required": True},
            {"code": "11", "name": "发布与上线", "required": True},
            {"code": "12", "name": "市场推广与获客", "required": False},
            {"code": "13", "name": "运营分析与持续迭代", "required": False},
        ],
        "default_dependencies": [
            {"from": "01", "to": "02"},
            {"from": "02", "to": "03"},
            {"from": "03", "to": "04"},
            {"from": "04", "to": "05", "gate": "decision"},
            {"from": "05", "to": "06"},
            {"from": "06", "to": "07"},
            {"from": "06", "to": "08"},
            {"from": "07", "to": "09"},
            {"from": "08", "to": "09", "gate": "approval"},
            {"from": "09", "to": "10"},
            {"from": "10", "to": "11", "gate": "quality"},
            {"from": "11", "to": "12"},
            {"from": "11", "to": "13"},
        ]
    },
    {
        "id": "fast-iteration",
        "name": "快速功能迭代 (7 模块)",
        "description": "适合已有产品的大版本与重要功能迭代，跳过前期商业调研，直接进入 PRD 与开发。",
        "modules_config": [
            {"code": "06", "name": "MVP 定义与 PRD", "required": True},
            {"code": "07", "name": "设计与可用性验证", "required": True},
            {"code": "08", "name": "技术可行性评估", "required": False},
            {"code": "09", "name": "开发实现", "required": True},
            {"code": "10", "name": "测试与 QA", "required": True},
            {"code": "11", "name": "发布与上线", "required": True},
            {"code": "13", "name": "运营分析与持续迭代", "required": False},
        ],
        "default_dependencies": [
            {"from": "06", "to": "07"},
            {"from": "07", "to": "09"},
            {"from": "09", "to": "10"},
            {"from": "10", "to": "11", "gate": "quality"},
            {"from": "11", "to": "13"}
        ]
    },
    {
        "id": "hotfix",
        "name": "紧急热修复 (3 模块)",
        "description": "紧急缺陷与生产问题快速通道：开发 → 测试回归 → 紧急发布。",
        "modules_config": [
            {"code": "09", "name": "开发实现", "required": True},
            {"code": "10", "name": "测试与 QA", "required": True},
            {"code": "11", "name": "发布与上线", "required": True},
        ],
        "default_dependencies": [
            {"from": "09", "to": "10"},
            {"from": "10", "to": "11", "gate": "quality"}
        ]
    }
]

async def seed_templates_if_empty(db: AsyncSession):
    stmt = select(WorkflowTemplate)
    res = await db.execute(stmt)
    existing = res.scalars().all()
    if not existing:
        for t in DEFAULT_TEMPLATES:
            tpl = WorkflowTemplate(
                id=t["id"],
                name=t["name"],
                description=t["description"],
                modules_config=t["modules_config"],
                default_dependencies=t["default_dependencies"]
            )
            db.add(tpl)
        await db.commit()

async def create_workflow_run_from_template(
    db: AsyncSession, product_id: str, template_id: str, run_name: str
) -> WorkflowRun:
    stmt = select(WorkflowTemplate).where(WorkflowTemplate.id == template_id)
    res = await db.execute(stmt)
    template = res.scalar_one_or_none()
    if not template:
        raise ValueError(f"Template {template_id} not found")

    run = WorkflowRun(
        product_id=product_id,
        template_id=template_id,
        name=run_name,
        status="in_progress"
    )
    db.add(run)
    await db.flush()

    # Build dependency map
    deps_map: Dict[str, List[str]] = {}
    for dep in template.default_dependencies:
        target = dep["to"]
        src = dep["from"]
        if target not in deps_map:
            deps_map[target] = []
        deps_map[target].append(src)

    # Instantiate modules
    from backend.app.services.agent_roles import STAGE_ROLE_CONFIGS

    for idx, m in enumerate(template.modules_config, start=1):
        code = m["code"]
        mod_deps = deps_map.get(code, [])
        is_unlocked = len(mod_deps) == 0 # Entry modules unlock immediately
        stage_cfg = STAGE_ROLE_CONFIGS.get(code, {"primary": "pm", "collaborators": []})

        mod_inst = ModuleInstance(
            run_id=run.id,
            module_code=code,
            name=m["name"],
            order_index=idx,
            phase="draft",
            is_unlocked=is_unlocked,
            dependencies=mod_deps,
            primary_role_code=stage_cfg["primary"],
            collaborator_role_codes=stage_cfg["collaborators"]
        )
        db.add(mod_inst)
        await db.flush()

        # Create default collaboration session for each module
        session = CollaborationSession(
            module_id=mod_inst.id,
            title=f"{m['name']} 协作讨论室",
            status="active",
            participants=[
                {"role": "human", "name": "业务负责人"},
                {"role": "agent", "name": f"AI Agent ({stage_cfg['primary']})"}
            ]
        )
        db.add(session)

    await db.commit()
    await db.refresh(run)
    return run

async def can_baseline_module(db: AsyncSession, module_id: str) -> Tuple[bool, str]:
    """Check if a module can transition to 'baselined'."""
    # Check open critical/major issues targeting this module
    stmt = select(Issue).where(
        Issue.target_module_id == module_id,
        Issue.status.in_(["open", "investigating", "fixing", "verifying"]),
        Issue.severity.in_(["critical", "major"])
    )
    res = await db.execute(stmt)
    blocking_issues = res.scalars().all()
    if blocking_issues:
        issue_titles = ", ".join([f"{i.id} ({i.title})" for i in blocking_issues[:3]])
        return False, f"存在未解决的阻塞性 Issue: {issue_titles}"

    # Check if module has at least one artifact
    art_stmt = select(Artifact).where(Artifact.module_id == module_id)
    art_res = await db.execute(art_stmt)
    artifacts = art_res.scalars().all()
    if not artifacts:
        return False, "模块尚未产出任何可作为基线的交付物 (Artifact)"

    return True, ""

async def unlock_downstream_modules(db: AsyncSession, run_id: str):
    """When a module is baselined, check and unlock dependent downstream modules."""
    stmt = select(ModuleInstance).where(ModuleInstance.run_id == run_id)
    res = await db.execute(stmt)
    all_modules = res.scalars().all()

    baselined_codes = {m.module_code for m in all_modules if m.phase == "baselined"}

    for m in all_modules:
        if not m.is_unlocked:
            # Check if all dependencies are satisfied
            if all(dep in baselined_codes for dep in m.dependencies):
                m.is_unlocked = True
                db.add(m)

    await db.commit()

def calculate_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
