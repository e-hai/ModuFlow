import os
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.app.core.config import settings
from backend.app.models.entities import (
    StrategicInitiative,
    Product,
    WorkflowRun,
    ModuleInstance,
    Artifact,
    ExecutiveDecision,
    ExecutiveRisk
)

def sanitize_dirname(name: str) -> str:
    """Sanitize names for directory paths."""
    for ch in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
        name = name.replace(ch, '_')
    return name.strip()

async def sync_strategic_initiative_workspace(db: AsyncSession, initiative_id: str) -> Dict[str, Any]:
    """
    Syncs an entire Strategic Initiative and all its products, iterations,
    modules, and artifacts to physical isolated workspaces on disk:
    data/workspaces/{initiative_id}/
    """
    stmt = (
        select(StrategicInitiative)
        .options(
            selectinload(StrategicInitiative.products)
            .selectinload(Product.workflow_runs)
            .selectinload(WorkflowRun.modules)
            .selectinload(ModuleInstance.artifacts),
            selectinload(StrategicInitiative.decisions),
            selectinload(StrategicInitiative.risks)
        )
        .where(StrategicInitiative.id == initiative_id)
    )
    res = await db.execute(stmt)
    init = res.scalar_one_or_none()
    if not init:
        return {"success": False, "error": f"Strategic Initiative '{initiative_id}' not found"}

    init_dir = settings.WORKSPACE_DIR / init.id
    init_dir.mkdir(parents=True, exist_ok=True)

    # 1. 战略工程底稿与公共资产 (Shared Assets)
    shared_dir = init_dir / "00_战略工程底稿与公共资产"
    shared_dir.mkdir(parents=True, exist_ok=True)

    # 00_主体身份与战略底稿.md
    net_cash_flow = (init.cash_collected or 0.0) - (init.actual_paid or 0.0)
    blueprint_content = f"""# 【战略工程底稿】{init.name}

> 本文件由 ModuFlow 战略驾驶舱自动同步生成。
> 同步时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

## 1. 主体身份与基本概况
- **战略工程 ID**：`{init.id}`
- **战略名称**：{init.name}
- **负责人**：{init.owner}
- **当前战略状态**：`{init.status.upper()}`
- **工程概述**：{init.description or '暂无详细描述'}

---

## 2. 战略底稿三要素
### ① 战略定性 (Strategic Intent)
> {init.strategic_intent or '未设定战略定性'}

### ② 目标市场 (Target Market)
> {init.target_market or '未设定目标市场'}

### ③ 商业模式假设 (Business Model Hypothesis)
> {init.business_model_hypothesis or '未设定商业模式假设'}

---

## 3. 财务与资金池账本 ({init.currency})
- **批准总预算**：¥{init.budget_total:,.2f}
- **实际已付现金**：¥{init.actual_paid:,.2f}
- **已承诺未付**：¥{init.committed_unpaid:,.2f}
- **营业确认收入**：¥{init.revenue_recognized:,.2f}
- **实际到账回款**：¥{init.cash_collected:,.2f}
- **真实净现金流**：{"¥" if net_cash_flow >= 0 else "-¥"}{abs(net_cash_flow):,.2f}

---

## 4. 产品矩阵构成
| 产品代码 | 产品名称 | 战略角色 | 阶段 | 分配预算 | 实际支出 | 贡献营收 | 核心 KPI 目标与现状 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""
    for p in init.products:
        blueprint_content += f"| `{p.code}` | {p.name} | `{p.strategic_role}` | `{p.stage}` | ¥{p.budget_allocated:,.0f} | ¥{p.actual_spent:,.0f} | ¥{p.revenue_contribution:,.0f} | {p.kpi_name or 'KPI'}: 目标 {p.kpi_target or 0} / 当前 {p.kpi_actual or 0} {p.kpi_unit or ''} |\n"

    blueprint_path = shared_dir / "00_主体身份与战略底稿.md"
    blueprint_path.write_text(blueprint_content, encoding="utf-8")

    # 01_宏观市场与政策合规备忘录.md (共享市场底座)
    market_memo = f"""# 【公共资产】宏观市场研究与合规备忘录

> 本文档为战略工程 `{init.id}`（{init.name}）旗下所有子产品的**公共输入底盘**。
> 各单品在进行工序 01 市场研究时，默认继承此文档结论，仅需特化自身微观用户痛点，严禁从零重复调研。

---

## 1. 目标市场与宏观大盘
> {init.target_market or '尚未录入宏观市场与目标群体描述。'}

## 2. 监管与政策合规红线
> 尚未录入政策监管与合规要求。可根据目标市场法规、数据合规标准在此补充。
"""
    (shared_dir / "01_宏观市场与政策合规备忘录.md").write_text(market_memo, encoding="utf-8")

    # 02_顶层生态商业模型闭环.md (共享商业底座)
    flywheel_memo = f"""# 【公共资产】战略工程顶层生态商业模型闭环

> 本文档定义 `{init.id}`（{init.name}）矩阵产品的协同机制与商业模式假设。
> 各产品在工序 02 商业可行性论证时，需在此商业闭环中明确自身定位。

---

## 1. 商业模式与协同假设
> {init.business_model_hypothesis or '尚未录入顶层商业模型假设。'}

## 2. 战略意图
> {init.strategic_intent or '尚未录入战略意图。'}
"""
    (shared_dir / "02_顶层生态商业模型闭环.md").write_text(flywheel_memo, encoding="utf-8")

    # 2. 产品目录隔离：products/{product_code}/
    products_base = init_dir / "products"
    products_base.mkdir(parents=True, exist_ok=True)

    synced_artifacts_count = 0

    for prod in init.products:
        prod_dir = products_base / prod.code
        prod_dir.mkdir(parents=True, exist_ok=True)

        # 产品概况说明 README.md
        prod_readme = f"""# 产品工作区：{prod.name} (`{prod.code}`)

- **所属战略工程**：{init.name} (`{init.id}`)
- **商业定位角色**：`{prod.strategic_role}`
- **生命周期阶段**：`{prod.stage}`
- **已分配预算**：¥{prod.budget_allocated:,.2f}
- **实际已支出**：¥{prod.actual_spent:,.2f}
- **营业收入贡献**：¥{prod.revenue_contribution:,.2f}
- **核心 KPI**：{prod.kpi_name or 'KPI'} (目标 {prod.kpi_target or 0} / 当前 {prod.kpi_actual or 0} {prod.kpi_unit or ''})
- **当前核心风险**：{prod.key_risk or '无显著风险'}
- **经营建议**：{prod.recommendation or '继续推进'}

---

## 迭代周期 (Iterations)
"""
        for run in prod.workflow_runs:
            status_emoji = "🟢" if run.status == "in_progress" else ("🏁" if run.status == "completed" else "⚪")
            prod_readme += f"- {status_emoji} [{run.name}](./{sanitize_dirname(run.name)}) (状态: `{run.status}`)\n"

        (prod_dir / "README.md").write_text(prod_readme, encoding="utf-8")

        # 各迭代周期目录
        for run in prod.workflow_runs:
            run_dirname = sanitize_dirname(run.name)
            run_dir = prod_dir / run_dirname
            run_dir.mkdir(parents=True, exist_ok=True)

            run_readme = f"""# 迭代工作区：{run.name}

- **产品**：{prod.name} (`{prod.code}`)
- **迭代状态**：`{run.status}`
- **创建时间**：{run.created_at.strftime("%Y-%m-%d %H:%M:%S") if run.created_at else 'N/A'}

---

## 工序模块清单
| 序号 | 工序名称 | 代码 | 当前状态 | 是否锁定 | 交付物版本 |
| :--- | :--- | :--- | :--- | :--- | :--- |
"""
            for m in run.modules:
                art_count = len(m.artifacts)
                latest_ver = f"v{m.artifacts[0].version}" if art_count > 0 else "暂无"
                run_readme += f"| {m.order_index:02d} | [{m.name}](./{m.order_index:02d}_{m.module_code}_{sanitize_dirname(m.name)}) | `{m.module_code}` | `{m.phase}` | {'已解锁' if m.is_unlocked else '锁定中'} | {latest_ver} |\n"

            (run_dir / "README.md").write_text(run_readme, encoding="utf-8")

            # 各工序模块目录
            from backend.app.services.agent_roles import STAGE_ROLE_CONFIGS
            from backend.app.services.skill_mcp_mounter import mount_role_skills_and_mcp
            for m in run.modules:
                mod_dirname = f"{m.order_index:02d}_{m.module_code}_{sanitize_dirname(m.name)}"
                mod_dir = run_dir / mod_dirname
                mod_dir.mkdir(parents=True, exist_ok=True)

                stage_cfg = STAGE_ROLE_CONFIGS.get(m.module_code, {})
                primary_rc = stage_cfg.get("primary", "pm")
                collab_rcs = stage_cfg.get("collaborators", [])
                mount_role_skills_and_mcp(
                    workspace_dir=mod_dir,
                    primary_role_code=primary_rc,
                    collaborator_role_codes=collab_rcs
                )

                mod_readme = f"""# 工序 {m.module_code}：{m.name}

- **当前流转状态**：`{m.phase}` (draft / discussing / reviewing / baselined)
- **前置依赖模块**：{', '.join([f'`{d}`' for d in m.dependencies]) if m.dependencies else '无 (首道工序)'}
- **交付物数量**：共 {len(m.artifacts)} 个版本

---

## 交付物归档
"""
                if not m.artifacts:
                    mod_readme += "*(当前工序尚未生成交付物，将在产研协作中自动产出)*\n"
                else:
                    for art in m.artifacts:
                        baseline_tag = "【封版基线】" if art.is_baseline else ""
                        art_filename = f"{sanitize_dirname(art.title)}_v{art.version}.md"
                        mod_readme += f"- [{baseline_tag}{art.title} (v{art.version})](./{art_filename})\n"

                        # 写入具体交付物文件
                        art_file_content = f"""# {art.title}

> 版本：v{art.version} {"(当前基线)" if art.is_baseline else ""}
> 内容哈希 (SHA256)：`{art.content_hash}`
> 生成时间：{art.created_at.strftime("%Y-%m-%d %H:%M:%S") if art.created_at else 'N/A'}

---

{art.content}
"""
                        (mod_dir / art_filename).write_text(art_file_content, encoding="utf-8")
                        synced_artifacts_count += 1

                (mod_dir / "README.md").write_text(mod_readme, encoding="utf-8")

    return {
        "success": True,
        "initiative_id": init.id,
        "workspace_root": str(init_dir),
        "products_count": len(init.products),
        "artifacts_synced": synced_artifacts_count
    }

def get_workspace_tree(initiative_id: str) -> Dict[str, Any]:
    """Inspects the physical workspace folder structure on disk."""
    init_dir = settings.WORKSPACE_DIR / initiative_id
    if not init_dir.exists():
        return {"exists": False, "path": str(init_dir)}

    def build_tree(path: Path) -> Dict[str, Any]:
        node: Dict[str, Any] = {
            "name": path.name,
            "path": str(path.relative_to(settings.WORKSPACE_DIR)),
            "is_dir": path.is_dir()
        }
        if path.is_dir():
            children = []
            for item in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name)):
                if not item.name.startswith("."):
                    children.append(build_tree(item))
            node["children"] = children
        else:
            node["size"] = path.stat().st_size
        return node

    return {
        "exists": True,
        "root_path": str(init_dir),
        "tree": build_tree(init_dir)
    }

async def sync_run_workspace(db: AsyncSession, run_id: str):
    """Convenience helper to sync an entire initiative workspace given a run_id."""
    stmt = (
        select(Product.initiative_id)
        .join(WorkflowRun, WorkflowRun.product_id == Product.id)
        .where(WorkflowRun.id == run_id)
    )
    res = await db.execute(stmt)
    init_id = res.scalar_one_or_none()
    if init_id:
        await sync_strategic_initiative_workspace(db, init_id)

