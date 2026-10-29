import hashlib
from typing import List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from backend.app.models.entities import (
    WorkflowTemplate,
    WorkflowRun,
    Product,
    ModuleInstance,
    Artifact,
    Issue,
    CollaborationSession
)

DEFAULT_TEMPLATES = [
    {
        "id": "full-product-launch",
        "name": "完整产品研发 (11 模块)",
        "description": "从全球市场摸底、精益假门验证与立项裁决、产品需求定义，到设计开发、上线获客与运营迭代的完整闭环。",
        "modules_config": [
            {"code": "01", "name": "市场研究", "required": True},
            {"code": "02", "name": "商业模式分析", "required": True},
            {"code": "03", "name": "产品方向决策", "required": True},
            {"code": "04", "name": "低成本市场验证", "required": True},
            {"code": "05", "name": "产品需求定义", "required": True},
            {"code": "06", "name": "设计实现", "required": True},
            {"code": "07", "name": "开发实现", "required": True},
            {"code": "08", "name": "测试与 QA", "required": True},
            {"code": "09", "name": "发布与上线", "required": True},
            {"code": "10", "name": "市场推广与获客", "required": False},
            {"code": "11", "name": "运营分析与持续迭代", "required": False},
        ],
        "default_dependencies": [
            {"from": "01", "to": "02"},
            {"from": "02", "to": "03"},
            {"from": "03", "to": "04"},
            {"from": "04", "to": "05", "gate": "decision"},
            {"from": "05", "to": "06"},
            {"from": "05", "to": "07"},
            {"from": "06", "to": "07"},
            {"from": "07", "to": "08"},
            {"from": "08", "to": "09", "gate": "quality"},
            {"from": "09", "to": "10"},
            {"from": "09", "to": "11"},
        ]
    },
    {
        "id": "fast-iteration",
        "name": "快速功能迭代 (6 模块)",
        "description": "适合已有产品的大版本与重要功能迭代，直接承接运营复盘 Backlog 从产品需求定义进入设计、开发、测试、发布与运营闭环。",
        "modules_config": [
            {"code": "05", "name": "产品需求定义", "required": True},
            {"code": "06", "name": "设计实现", "required": True},
            {"code": "07", "name": "开发实现", "required": True},
            {"code": "08", "name": "测试与 QA", "required": True},
            {"code": "09", "name": "发布与上线", "required": True},
            {"code": "11", "name": "运营分析与持续迭代", "required": False},
        ],
        "default_dependencies": [
            {"from": "05", "to": "06"},
            {"from": "06", "to": "07"},
            {"from": "07", "to": "08"},
            {"from": "08", "to": "09", "gate": "quality"},
            {"from": "09", "to": "11"}
        ]
    },
    {
        "id": "hotfix",
        "name": "紧急热修复 (3 模块)",
        "description": "紧急缺陷与生产问题快速通道：开发 → 测试回归 → 紧急发布。",
        "modules_config": [
            {"code": "07", "name": "开发实现", "required": True},
            {"code": "08", "name": "测试与 QA", "required": True},
            {"code": "09", "name": "发布与上线", "required": True},
        ],
        "default_dependencies": [
            {"from": "07", "to": "08"},
            {"from": "08", "to": "09", "gate": "quality"}
        ]
    }
]

async def seed_templates_if_empty(db: AsyncSession):
    stmt = select(WorkflowTemplate)
    res = await db.execute(stmt)
    existing_map = {tpl.id: tpl for tpl in res.scalars().all()}
    for t in DEFAULT_TEMPLATES:
        if t["id"] not in existing_map:
            tpl = WorkflowTemplate(
                id=t["id"],
                name=t["name"],
                description=t["description"],
                modules_config=t["modules_config"],
                default_dependencies=t["default_dependencies"]
            )
            db.add(tpl)
        else:
            tpl = existing_map[t["id"]]
            tpl.name = t["name"]
            tpl.description = t["description"]
            tpl.modules_config = t["modules_config"]
            tpl.default_dependencies = t["default_dependencies"]
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
            collaborator_role_codes=stage_cfg["collaborators"],
            execution_mode=stage_cfg.get("execution_mode", "agent_driven"),
            synced_upstream_versions={}
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

async def load_price_baseline(db: AsyncSession, mod: ModuleInstance) -> List[float]:
    """Price points of the stage 02 (ba) baseline: this run first, else the product's latest one."""
    from backend.app.services.deliverable_audit import extract_price_points

    run_obj = (await db.execute(select(WorkflowRun).where(WorkflowRun.id == mod.run_id))).scalar_one_or_none()
    stmt = (
        select(Artifact, ModuleInstance.run_id)
        .join(ModuleInstance, ModuleInstance.baseline_artifact_id == Artifact.id)
        .join(WorkflowRun, WorkflowRun.id == ModuleInstance.run_id)
        .where(ModuleInstance.module_code == "02")
    )
    if run_obj and run_obj.product_id:
        stmt = stmt.where(WorkflowRun.product_id == run_obj.product_id)
    else:
        stmt = stmt.where(ModuleInstance.run_id == mod.run_id)
    rows = (await db.execute(stmt.order_by(Artifact.created_at.desc()))).all()
    if not rows:
        return []
    same_run = [art for art, run_id in rows if run_id == mod.run_id]
    baseline = same_run[0] if same_run else rows[0][0]
    prices = extract_price_points(baseline.content or "")
    from backend.app.services.delivery_contract import read_manifest_text, iter_json_documents

    manifest_raw = read_manifest_text(getattr(baseline, "storage_rel_path", None))
    if manifest_raw:
        for doc in iter_json_documents(manifest_raw):
            tiers = (doc.get("unit_economics") or {}).get("pricing_tiers") or []
            for t in tiers:
                if isinstance(t, dict) and "price_usd" in t:
                    try:
                        p = round(float(t["price_usd"]), 2)
                        if p not in prices:
                            prices.append(p)
                    except (TypeError, ValueError):
                        continue
    return prices


async def can_baseline_module(db: AsyncSession, module_id: str) -> Tuple[bool, str]:
    """Check if a module can transition to 'baselined'."""
    # 0. Check product-level deterministic authorization & stop-loss guardrails
    from backend.app.services.authorization_engine import (
        load_product_authorization,
        check_budget_limits,
        check_time_limits,
        check_kill_criteria,
        execute_circuit_breaker
    )

    m_stmt = select(ModuleInstance).where(ModuleInstance.id == module_id)
    m_res = await db.execute(m_stmt)
    mod = m_res.scalar_one_or_none()
    if mod:
        run_stmt = select(WorkflowRun).where(WorkflowRun.id == mod.run_id)
        run_res = await db.execute(run_stmt)
        run_obj = run_res.scalar_one_or_none()
        if run_obj and run_obj.product_id:
            p_stmt = select(Product).where(Product.id == run_obj.product_id)
            p_res = await db.execute(p_stmt)
            product = p_res.scalar_one_or_none()
            if product:
                # Check paused status
                if product.stage == "paused":
                    return False, f"项目处于熔断暂停状态: {product.key_risk or '触发安全熔断'}，严禁定稿基线"

                if product.initiative_id:
                    auth_status, auth_data, auth_errors = load_product_authorization(product.initiative_id, product.code)
                    if auth_status == "needs_authorization":
                        return False, "项目尚未配置合规授权包 (authorization.yaml)，禁止定稿基线"
                    elif auth_status == "invalid_authorization":
                        return False, f"项目授权包不合规: {', '.join(auth_errors)}"
                    elif auth_status == "authorized" and auth_data:
                        # 1. Budget limit check
                        is_breached, reason, is_hard = check_budget_limits(auth_data, float(product.actual_spent or 0.0))
                        if is_breached:
                            await execute_circuit_breaker(
                                product.initiative_id,
                                product.code,
                                "budget_exceeded",
                                {"reason": reason, "actual_spent": product.actual_spent},
                                db
                            )
                            return False, f"触发确定性预算熔断: {reason}"

                        # 2. Time limit check
                        is_expired, time_reason = check_time_limits(auth_data)
                        if is_expired:
                            await execute_circuit_breaker(
                                product.initiative_id,
                                product.code,
                                "time_expired",
                                {"reason": time_reason},
                                db
                            )
                            return False, f"触发确定性时限熔断: {time_reason}"

                        # 3. Kill criteria check
                        metrics = {
                            "actual_spent": float(product.actual_spent or 0.0),
                            "revenue_contribution": float(product.revenue_contribution or 0.0),
                        }
                        if product.kpi_name and product.kpi_actual is not None:
                            metrics[product.kpi_name.lower()] = float(product.kpi_actual)
                        triggered = check_kill_criteria(auth_data, metrics)
                        if triggered:
                            desc = triggered[0].get("description") or f"Metric {triggered[0]['metric']} hit threshold"
                            await execute_circuit_breaker(
                                product.initiative_id,
                                product.code,
                                "kill_criterion_hit",
                                {"reason": desc, "triggered": triggered},
                                db
                            )
                            return False, f"触发确定性止损熔断: {desc}"

    # 1. Check Human Gate Application & Approval status (Phase 2)
    from backend.app.services.gate_keeper import check_stage_gate_passed
    gate_ok, gate_reason, gate = await check_stage_gate_passed(db, module_id)
    if not gate_ok:
        return False, gate_reason

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
        return False, f"存在未解决的严重卡点问题: {issue_titles}"

    # Check if module has at least one artifact
    art_stmt = select(Artifact).where(Artifact.module_id == module_id)
    art_res = await db.execute(art_stmt)
    artifacts = art_res.scalars().all()
    if not artifacts:
        return False, "模块尚未产出任何可作为基线的交付物 (Artifact)"

    from sqlalchemy.orm.attributes import flag_modified
    from backend.app.services.deliverable_audit import artifact_audit_texts, audit_stage
    from backend.app.services.delivery_contract import manifest_from_texts, stage_directory

    platform = "ios"
    zero_inf = True
    product = None
    module_code = mod.module_code if mod else ""
    if mod is not None:
        run_stmt = select(WorkflowRun).where(WorkflowRun.id == mod.run_id)
        run_res = await db.execute(run_stmt)
        run_obj = run_res.scalar_one_or_none()
        if run_obj and run_obj.product_id:
            p_stmt = select(Product).where(Product.id == run_obj.product_id)
            p_res = await db.execute(p_stmt)
            product = p_res.scalar_one_or_none()
            if product:
                platform = product.platform or "ios"
                zero_inf = True if product.client_zero_inference is None else bool(product.client_zero_inference)

    latest_version = artifacts[-1].version
    latest_artifacts = [a for a in artifacts if a.version == latest_version]
    texts = artifact_audit_texts(latest_artifacts)
    audit = audit_stage(
        module_code,
        texts,
        platform=platform,
        client_zero_inference=zero_inf,
        price_baseline=await load_price_baseline(db, mod) if mod is not None else None,
        manifest_root=stage_directory(artifacts),
    )
    human_signed = gate is not None and gate.status == "approved" and gate.reviewer_role == "human"
    if audit.get("red_flags") and not human_signed:
        return False, "交付物含红级标记，须人类审批后才能定稿: " + ", ".join(audit["red_flags"])
    if not audit.get("passed"):
        reasons = audit.get("reasons") or ["交付物检查未通过"]
        return False, "交付物检查未通过: " + "; ".join(str(reason) for reason in reasons[:5])

    from backend.app.services.compliance_engine import audit_module_compliance, compliance_failed_items
    latest_artifact = max(artifacts, key=lambda a: a.version or 0)
    compliance = await audit_module_compliance(
        db, module_code, product, latest_artifact.content or "", manifest=manifest_from_texts(texts),
    )
    if compliance and compliance["status"] != "passed" and not human_signed:
        items = compliance_failed_items(compliance)
        return False, f"合规风控 (cmp) 结论为 {compliance['status']}，须整改或由人类签字: " + "; ".join(items[:3])

    if gate is not None:
        evidence = list(gate.evidence or [])
        evidence.append({
            "checker": "deliverable_audit",
            "passed": True,
            "module_code": audit.get("module_code"),
            "score": audit.get("score"),
        })
        if compliance:
            evidence.append({
                "checker": "compliance_engine",
                "status": compliance["status"],
                "risk_level": compliance["risk_level"],
                "summary": compliance["summary"],
            })
        gate.evidence = evidence
        flag_modified(gate, "evidence")
        db.add(gate)
        await db.commit()

    return True, ""

async def unlock_downstream_modules(db: AsyncSession, run_id: str):
    """When a module is baselined, check and unlock dependent downstream modules."""
    stmt = select(ModuleInstance).where(ModuleInstance.run_id == run_id)
    res = await db.execute(stmt)
    all_modules = res.scalars().all()

    baselined_codes = {m.module_code for m in all_modules if m.phase == "baselined"}
    from backend.app.services.stale_checker import get_relevant_upstream_codes

    for m in all_modules:
        if not m.is_unlocked:
            # Check if all dependencies are satisfied
            if all(dep in baselined_codes for dep in m.dependencies):
                m.is_unlocked = True
                
                # Auto-sync initial upstream versions so newly unlocked module starts synchronized
                current_sync = dict(m.synced_upstream_versions or {})
                relevant_upstreams = get_relevant_upstream_codes(m.module_code, m.dependencies)
                for up_code in relevant_upstreams:
                    up_mod = next((x for x in all_modules if x.module_code == up_code), None)
                    if up_mod and up_mod.baseline_artifact_id:
                        art_res = await db.execute(select(Artifact.version).where(Artifact.id == up_mod.baseline_artifact_id))
                        v = art_res.scalar_one_or_none()
                        if v:
                            current_sync[up_code] = v
                m.synced_upstream_versions = current_sync
                db.add(m)

    await db.commit()

def calculate_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
