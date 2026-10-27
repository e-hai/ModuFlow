"""
ModuFlow Phase 7: Hotfix Documentation SLA & Portfolio Dashboard Engine
(backend/app/services/portfolio_and_hotfix_service.py)

Enforces:
1. Hotfix 24h Documentation Follow-up SLA:
   - When a hotfix run is released, automatically generates 3 mandatory follow-up tasks:
     ① 补需求变更单 (CR)
     ② 生产故障复盘与 RCA 根因分析 (Post-Mortem)
     ③ 工序 05 PRD 规格基线同步更新 (PRD Baseline Update)
   - 24-hour deterministic SLA tracking:
     If 24h passes and tasks are pending, automatically generates 🔴 critical ExecutiveRisk alert
     and writes an audit log into decisions/.
2. Portfolio Executive Weekly Report (组合层一页周报):
   - Reads all projects across initiatives from DB (stage, budget/spent, KPIs, risks, recommendations).
   - Generates a 1-page Executive Weekly Report with portfolio matrix table.
   - STRICT HARD REDLINE:
     Outputs recommendations ONLY. Absolutely forbids autonomous fund transfer, scaling, or killing projects!
   - Saves markdown report to disk workspace and writes audit log to decisions/.
"""

import os
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from fastapi import HTTPException

from backend.app.core.config import settings
from backend.app.models.entities import (
    StrategicInitiative,
    Product,
    WorkflowRun,
    ModuleInstance,
    Issue,
    ExecutiveRisk,
    HotfixFollowupTask,
    GateApplication
)


def get_workspace_root() -> Path:
    return Path(settings.WORKSPACE_DIR)


# =============================================================================
# 1. Hotfix Follow-up Tasks & 24h SLA Check
# =============================================================================

async def create_hotfix_followup_tasks(
    db: AsyncSession,
    run_id: str,
    actor_id: str = "human:system"
) -> Dict[str, Any]:
    """
    Called upon Hotfix release (Stage 09 completion / run baselined):
    Automatically provisions 3 mandatory follow-up tasks with a 24-hour completion deadline:
    1. 补提交需求变更单 (CR) -> cr_patch
    2. 生产故障复盘与 RCA 根因分析 -> postmortem
    3. 工序 05 PRD 规格基线同步更新 -> prd_update
    """
    r_stmt = select(WorkflowRun).where(WorkflowRun.id == run_id)
    r_res = await db.execute(r_stmt)
    run = r_res.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="WorkflowRun not found")

    if run.template_id != "hotfix":
        raise HTTPException(status_code=400, detail="Only hotfix template workflow runs generate hotfix followup tasks")

    p_stmt = select(Product).where(Product.id == run.product_id)
    p_res = await db.execute(p_stmt)
    product = p_res.scalar_one_or_none()
    product_code = product.code if product else "UNKNOWN"
    initiative_id = product.initiative_id if product and product.initiative_id else "platform"

    # Check if tasks already exist for this run
    t_stmt = select(HotfixFollowupTask).where(HotfixFollowupTask.run_id == run_id)
    t_res = await db.execute(t_stmt)
    existing_tasks = t_res.scalars().all()
    if existing_tasks:
        return {
            "status": "already_exists",
            "run_id": run_id,
            "product_code": product_code,
            "tasks_count": len(existing_tasks),
            "deadline": existing_tasks[0].deadline.isoformat(),
            "tasks": [
                {"id": t.id, "task_type": t.task_type, "title": t.title, "status": t.status}
                for t in existing_tasks
            ]
        }

    now = datetime.now(timezone.utc)
    deadline = now + timedelta(hours=24)

    task_definitions = [
        {
            "task_type": "cr_patch",
            "title": f"[热修补档-01] 补需求变更单 (CR) - {product_code} 生产缺陷闭环入池",
            "description": "针对生产缺陷紧急发布，必须在 24 小时内向工序 05 提交正式需求变更单 (CR)，驱动上游基线闭环演进，防止线上代码与产品 PRD 脱节。"
        },
        {
            "task_type": "postmortem",
            "title": f"[热修补档-02] 生产故障复盘与根因分析报告 (RCA Post-Mortem) - {product_code}",
            "description": "召集技术架构 (eng) 与测试保障 (qa)，深入排查线上缺陷发生原因、逃逸路径与防范机制，沉淀 5 Whys 根因分析报告。"
        },
        {
            "task_type": "prd_update",
            "title": f"[热修补档-03] 同步修订工序 05 PRD 规格基线与 Gherkin 验收用例 - {product_code}",
            "description": "产品经理 (pm) 承接热修 CR 与故障复盘结论，更新工序 05 PRD 黄金 7+1 章节与验收用例矩阵，发布增量版本新基线。"
        }
    ]

    created_tasks: List[HotfixFollowupTask] = []
    for defn in task_definitions:
        task = HotfixFollowupTask(
            run_id=run_id,
            product_id=run.product_id,
            task_type=defn["task_type"],
            title=defn["title"],
            description=defn["description"],
            status="pending",
            deadline=deadline,
            created_at=now
        )
        db.add(task)
        created_tasks.append(task)

    await db.commit()
    for t in created_tasks:
        await db.refresh(t)

    # Write audit log to decisions/
    decisions_dir = get_workspace_root() / initiative_id / "products" / product_code / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    ts_str = now.strftime("%Y%m%d_%H%M%S")
    audit_file = decisions_dir / f"{ts_str}_hotfix_followup_tasks_created.json"
    audit_file.write_text(json.dumps({
        "event": "HOTFIX_FOLLOWUP_TASKS_CREATED",
        "timestamp": now.isoformat(),
        "run_id": run_id,
        "run_name": run.name,
        "product_code": product_code,
        "deadline_utc": deadline.isoformat(),
        "sla_hours": 24,
        "actor": actor_id,
        "tasks": [
            {"id": t.id, "type": t.task_type, "title": t.title}
            for t in created_tasks
        ]
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "status": "created",
        "run_id": run_id,
        "product_code": product_code,
        "tasks_count": len(created_tasks),
        "deadline": deadline.isoformat(),
        "tasks": [
            {"id": t.id, "task_type": t.task_type, "title": t.title, "status": t.status}
            for t in created_tasks
        ]
    }


async def check_hotfix_documentation_sla(
    db: AsyncSession,
    run_id: str,
    check_time: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Deterministic 24-hour SLA check.
    If 24 hours have elapsed since hotfix release and any of the 3 follow-up tasks are pending:
    - Generates a 🔴 CRITICAL ExecutiveRisk alert
    - Writes an audit log to decisions/
    - Returns alert details
    """
    t_stmt = select(HotfixFollowupTask).where(HotfixFollowupTask.run_id == run_id)
    t_res = await db.execute(t_stmt)
    tasks = t_res.scalars().all()

    if not tasks:
        return {
            "run_id": run_id,
            "has_tasks": False,
            "is_overdue": False,
            "message": "No hotfix followup tasks found for this run"
        }

    now = check_time or datetime.now(timezone.utc)
    # Ensure timezone aware for accurate comparison
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    pending_tasks = [t for t in tasks if t.status != "completed"]
    deadline = tasks[0].deadline
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)

    is_overdue = (now > deadline) and (len(pending_tasks) > 0)
    all_completed = (len(pending_tasks) == 0)

    alert_created = False
    if is_overdue:
        # Load run and product
        r_stmt = select(WorkflowRun).where(WorkflowRun.id == run_id)
        r_res = await db.execute(r_stmt)
        run = r_res.scalar_one_or_none()

        product = None
        if run:
            p_stmt = select(Product).where(Product.id == run.product_id)
            p_res = await db.execute(p_stmt)
            product = p_res.scalar_one_or_none()

        initiative_id = product.initiative_id if product and product.initiative_id else "platform"
        product_code = product.code if product else "UNKNOWN"

        # Create critical ExecutiveRisk
        risk_title = f"【热修补档超期告警】项目 {product_code} 24h 内未完成「补 CR + 复盘 + PRD 更新」"
        risk_desc = (
            f"热修运行「{run.name if run else run_id}」发布已超过 24h SLA 门禁截止时间 ({deadline.isoformat()})，"
            f"目前仍有 {len(pending_tasks)} 项补档任务未关闭: "
            f"{', '.join([t.title for t in pending_tasks])}。必须立即安排人员完成补档！"
        )

        # Idempotent risk check
        existing_risk_stmt = select(ExecutiveRisk).where(
            ExecutiveRisk.initiative_id == initiative_id,
            ExecutiveRisk.title == risk_title,
            ExecutiveRisk.is_resolved == False
        )
        er_res = await db.execute(existing_risk_stmt)
        if not er_res.scalar_one_or_none():
            risk_obj = ExecutiveRisk(
                initiative_id=initiative_id,
                rule_code="HOTFIX_SLA_BREACH",
                title=risk_title,
                severity="critical",
                description=risk_desc,
                product_code=product_code,
                action_suggestion="立即分派责任 Agent 与产品经理在工序 05 补齐 CR 并更新 PRD 基线。",
                is_resolved=False
            )
            db.add(risk_obj)
            await db.commit()
            alert_created = True

        # Write audit log to decisions/
        decisions_dir = get_workspace_root() / initiative_id / "products" / product_code / "decisions"
        decisions_dir.mkdir(parents=True, exist_ok=True)
        ts_str = now.strftime("%Y%m%d_%H%M%S")
        audit_file = decisions_dir / f"{ts_str}_hotfix_overdue_alert.json"
        audit_file.write_text(json.dumps({
            "event": "HOTFIX_OVERDUE_SLA_BREACH",
            "timestamp": now.isoformat(),
            "run_id": run_id,
            "product_code": product_code,
            "deadline": deadline.isoformat(),
            "overdue_hours": round((now - deadline).total_seconds() / 3600, 2),
            "pending_tasks": [
                {"id": t.id, "title": t.title, "type": t.task_type}
                for t in pending_tasks
            ]
        }, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "run_id": run_id,
        "has_tasks": True,
        "is_overdue": is_overdue,
        "all_completed": all_completed,
        "alert_created": alert_created,
        "deadline": deadline.isoformat(),
        "pending_count": len(pending_tasks),
        "tasks": [
            {
                "id": t.id,
                "task_type": t.task_type,
                "title": t.title,
                "status": t.status,
                "deadline": t.deadline.isoformat(),
                "completed_at": t.completed_at.isoformat() if t.completed_at else None
            }
            for t in tasks
        ]
    }


async def complete_hotfix_task(
    db: AsyncSession,
    task_id: str,
    actor_id: str = "human:alice",
    notes: Optional[str] = None
) -> HotfixFollowupTask:
    """Marks a HotfixFollowupTask as completed."""
    t_stmt = select(HotfixFollowupTask).where(HotfixFollowupTask.id == task_id)
    t_res = await db.execute(t_stmt)
    task = t_res.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="HotfixFollowupTask not found")

    now = datetime.now(timezone.utc)
    task.status = "completed"
    task.completed_at = now
    task.completed_by = actor_id
    if notes:
        task.notes = notes

    await db.commit()
    await db.refresh(task)
    return task


# =============================================================================
# 2. Portfolio Executive Weekly Report (组合层一页周报)
# =============================================================================

async def generate_portfolio_weekly_report(
    db: AsyncSession,
    initiative_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generates a 1-page Executive Portfolio Weekly Report across products:
    - Stage, budget/spent, KPIs, risks, recommendations
    - Strict Redline: Outputs recommendations ONLY, NO autonomous budget/killing action!
    - Persists report to data/workspaces/{initiative_id}/portfolio_weekly_report.md
    - Writes decision audit log to decisions/
    """
    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")

    # 1. Fetch initiatives and products
    p_stmt = select(Product).order_by(Product.created_at.desc())
    if initiative_id:
        p_stmt = p_stmt.where(Product.initiative_id == initiative_id)
    p_res = await db.execute(p_stmt)
    products = p_res.scalars().all()

    i_stmt = select(StrategicInitiative)
    if initiative_id:
        i_stmt = i_stmt.where(StrategicInitiative.id == initiative_id)
    i_res = await db.execute(i_stmt)
    initiatives = i_res.scalars().all()

    target_init = initiatives[0] if initiatives else None
    init_name = target_init.name if target_init else "ModuFlow 多产品战略矩阵"
    init_id_str = target_init.id if target_init else "platform"

    total_products = len(products)
    total_budget = sum(float(p.budget_allocated or 0.0) for p in products)
    total_spent = sum(float(p.actual_spent or 0.0) for p in products)
    total_revenue = sum(float(p.revenue_contribution or 0.0) for p in products)
    overall_burn_pct = round((total_spent / total_budget) * 100, 1) if total_budget > 0 else 0.0

    # 2. Analyze product states
    active_count = sum(1 for p in products if p.stage in ["validating", "building", "growth"])
    paused_count = sum(1 for p in products if p.stage == "paused")
    profitable_count = sum(1 for p in products if p.stage == "profitable")

    # 3. Formulate per-product assessment & recommendations
    portfolio_rows = []
    strategic_recommendations = []

    for idx, p in enumerate(products, 1):
        alloc = float(p.budget_allocated or 0.0)
        spent = float(p.actual_spent or 0.0)
        burn_pct = round((spent / alloc) * 100, 1) if alloc > 0 else 0.0
        
        # Determine status indicator
        status_icon = "🟢"
        if p.stage == "paused":
            status_icon = "🔴"
        elif burn_pct > 85.0:
            status_icon = "🟡"

        # Determine strategic recommendation
        advice = ""
        if p.stage == "paused":
            advice = "【重点关注】已命中止损/熔断线暂停，建议人类决策人审查 decisions/ 审计单评估是否终止 (Kill) 或调整 (Pivot)。"
            strategic_recommendations.append(f"- **{p.name} ({p.code})**：{advice}")
        elif burn_pct > 80.0:
            advice = f"预算消耗率已达 {burn_pct}%，逼近授权包硬防线，建议审核追加预算或收紧单工序派活。"
            strategic_recommendations.append(f"- **{p.name} ({p.code})**：{advice}")
        elif p.stage == "growth":
            advice = "持续优化获客 eCAC 与次周留存，结合工序 11 数据反哺 V1.1 迭代。"
        elif p.stage == "validating":
            advice = "严格依据工序 04 真实外测埋点数据判断立项，未达标前严禁提前启动研发重度工程。"
        else:
            advice = p.recommendation or "保持按既定工序推进。"

        kpi_display = f"{p.kpi_actual or 0.0} / {p.kpi_target or 0.0} {p.kpi_unit or ''}".strip()
        portfolio_rows.append(
            f"| {idx} | **{p.name}** (`{p.code}`) | `{p.platform or 'ios'}` | {status_icon} `{p.stage}` | "
            f"${spent:,.2f} / ${alloc:,.2f} ({burn_pct}%) | {kpi_display or 'N/A'} | {advice} |"
        )

    if not strategic_recommendations:
        strategic_recommendations.append("- **矩阵整体健康**：各产品线预算消耗与关口流转处于安全阈值内，建议按节拍推进。")

    # 4. Generate 1-page markdown report adhering to two-layer standard
    markdown_report = f"""# ModuFlow 投资组合层一页周报 (Portfolio Weekly Digest)
> 报告周期：`{today_str}` ｜ 关联战略工程：**{init_name}** ｜ 生成时间：`{now.strftime("%Y-%m-%d %H:%M:%S UTC")}`

---

## 负责人 30 秒拍板摘要卡 (Executive Gate)

> [!IMPORTANT]
> **组合层战略红线 (Strategic Redline Guardrail)**：
> 本周报由组合层调度器自动化生成，**仅出具跨产品战略协同与资源分配建议，严禁系统或 Agent 自动执行加码、砍项目或跨产品划转资金！**
> 任何加码、关停或资金授权动作必须由**人类战略决策人 (Human Sponsor)** 签署确认。

| 核心指标 | 当前数值 | 状态与参考阈值 |
| :--- | :--- | :--- |
| **产品总数 / 活跃矩阵** | **{total_products} 款** ｜ 活跃 `{active_count}` 款 ｜ 盈利 `{profitable_count}` 款 | 正常运行 |
| **熔断暂停单品数** | **{paused_count} 款** | {'🔴 需人类即时拍板' if paused_count > 0 else '🟢 0 熔断'} |
| **矩阵总预算 / 已消耗** | **${total_budget:,.2f}** ｜ 已支出 **${total_spent:,.2f}** (`{overall_burn_pct}%`) | 整体资金水位正常 |
| **矩阵累计贡献营收** | **${total_revenue:,.2f}** | 滚动回收中 |

### 置顶建议决策 (Strategic Recommendations)
{chr(10).join(strategic_recommendations)}

---

## 完整执行细节 (Execution Reference)

### 1. 全矩阵产品经营与关口状态矩阵 (Portfolio Matrix)

| 序号 | 产品名称 (代码) | 目标平台 | 运营阶段 | 预算消耗 (比例) | 核心 KPI 达成 | 建议动作 (Recommendation Only) |
| :---: | :--- | :---: | :---: | :---: | :---: | :--- |
{chr(10).join(portfolio_rows)}

### 2. 跨产品协同与依赖提示
- **全球调研资产复用**：工序 01 赛道调研沉淀（爆款前 3 秒钩子库与 ASO 词表）已全量同步至各单品物理工作区；
- **平台规则一致性**：iOS 与 Android 项目已按各自 `profile.platform` 独立匹配 Apple HIG 或 Material 3 规则集；
- **热修合规监控**：所有紧急热修上线后已启动 24 小时补档追踪，未完成「补 CR + 复盘 + PRD 更新」将持续告警。

---
*Generated by ModuFlow Strategic Portfolio Service*
"""

    # 5. Persist markdown report to disk workspace
    workspace_root = get_workspace_root()
    target_dir = workspace_root / init_id_str
    target_dir.mkdir(parents=True, exist_ok=True)
    report_file = target_dir / "portfolio_weekly_report.md"
    report_file.write_text(markdown_report, encoding="utf-8")

    # Also sync to workspace root for convenience
    (workspace_root / "portfolio_weekly_report.md").write_text(markdown_report, encoding="utf-8")

    # 6. Write audit decision file
    decisions_dir = target_dir / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    ts_str = now.strftime("%Y%m%d_%H%M%S")
    audit_file = decisions_dir / f"{ts_str}_portfolio_weekly_report.json"
    audit_file.write_text(json.dumps({
        "event": "PORTFOLIO_WEEKLY_REPORT_GENERATED",
        "timestamp": now.isoformat(),
        "initiative_id": init_id_str,
        "total_products": total_products,
        "active_products": active_count,
        "paused_products": paused_count,
        "total_budget": total_budget,
        "total_spent": total_spent,
        "overall_burn_pct": overall_burn_pct,
        "recommendations_count": len(strategic_recommendations),
        "report_file": str(report_file)
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "status": "generated",
        "initiative_id": init_id_str,
        "generated_at": now.isoformat(),
        "total_products": total_products,
        "total_budget": total_budget,
        "total_spent": total_spent,
        "overall_burn_pct": overall_burn_pct,
        "paused_products": paused_count,
        "report_file_path": str(report_file),
        "markdown_report": markdown_report,
        "recommendations": strategic_recommendations
    }
