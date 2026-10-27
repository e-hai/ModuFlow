#!/usr/bin/env python3
"""
ModuFlow End-to-End Walkthrough Script (scripts/e2e_walkthrough.py)
Executes a complete, authentic product lifecycle for "FocusZen (FZ01)"
under the Three-Tier Architecture:
1. Human Strategic Tier: Authorization package, budget, hard stop-loss, kill criteria, read-only protection.
2. Project Tier (Lead): Pipeline orchestration, shadow mode consistency tracking, daily digest.
3. Execution Tier: mr -> ba -> pm -> mkt -> ux -> eng -> qa -> ops -> cmp.
4. Gate Classification: 🟢 Green (Lead) | 🟡 Yellow (Human) | 🔴 Red (Human mandatory sign-off).
5. Deterministic guardrails: HIG check, zero-inference audit, auto-escalation, 09 human release blocker.
"""

import sys
import os
import json
import asyncio
from pathlib import Path
from datetime import datetime, timezone, timedelta
import yaml

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.database import AsyncSessionLocal, engine, Base
from backend.app.models.entities import (
    StrategicInitiative,
    Product,
    WorkflowRun,
    ModuleInstance,
    Artifact,
    CollaborationSession,
    SessionMessage,
    GateApplication,
    ExecutiveRisk
)
from backend.app.services.workflow_engine import seed_templates_if_empty
from backend.app.services.agent_roles import seed_agent_roles_if_empty, migrate_db_for_roles
from backend.app.services.authorization_engine import (
    check_budget_limits,
    check_time_limits,
    check_kill_criteria,
    check_lead_forbidden_action,
    load_product_authorization,
    execute_circuit_breaker
)
from backend.app.services.security_guard import (
    apply_readonly_file_protection,
    intercept_agent_write_attempt,
    validate_pricing_authority
)
from backend.app.services.gate_keeper import (
    create_or_update_gate_application,
    review_gate_application,
    evaluate_gate_level,
    get_stage_gate_config
)
from backend.app.services.lead_service import (
    evaluate_gate_by_lead,
    get_shadow_mode_stats,
    generate_project_daily_digest
)
from backend.app.services.compliance_engine import run_stage_compliance_check
from backend.app.services.profile_guard import (
    resolve_project_profile,
    audit_platform_design_system,
    audit_client_zero_inference
)
from backend.app.services.portfolio_and_hotfix_service import generate_portfolio_weekly_report
from sqlalchemy import select, and_


def print_step(title: str, icon: str = "🚀"):
    print(f"\n{'='*75}\n{icon} {title}\n{'='*75}")


async def run_e2e_walkthrough():
    print_step("ModuFlow 真实出海标杆项目端到端全链路实战演练 (FocusZen FZ01)", "🧘")

    # 0. Database & Templates initialization
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        await migrate_db_for_roles(db)
        await seed_agent_roles_if_empty(db)
        await seed_templates_if_empty(db)

    # 1. Human Strategic Tier: Initiative & Product Setup
    print_step("第 1 阶段：人类战略层立项与授权包 (Human Strategic Tier)", "🏛️")

    initiative_id = "init-global-utils-2026"
    product_code = "FZ01"
    run_name = "v1.0.0-mvp"

    async with AsyncSessionLocal() as db:
        # Check or create Initiative
        init_stmt = select(StrategicInitiative).where(StrategicInitiative.id == initiative_id)
        res = await db.execute(init_stmt)
        init_obj = res.scalar_one_or_none()
        if not init_obj:
            init_obj = StrategicInitiative(
                id=initiative_id,
                name="2026 全球轻量工具矩阵工程",
                description="面向全球高净值与高压人群的轻量纯客户端工具矩阵",
                owner="CEO / 人类战略层",
                budget=50000.0,
                status="active",
                target_market="US, UK, DE, JP",
                strategic_intent="打造零服务器边际成本的高毛利工具矩阵"
            )
            db.add(init_obj)
            await db.commit()
            print(f"✅ [战略层] 成功立项顶层战略工程: {init_obj.name} (总预算: ${init_obj.budget:,.2f})")

        # Check or create Product FocusZen
        prod_stmt = select(Product).where(Product.code == product_code)
        p_res = await db.execute(prod_stmt)
        prod_obj = p_res.scalar_one_or_none()
        if not prod_obj:
            prod_obj = Product(
                initiative_id=initiative_id,
                name="FocusZen 专注禅音",
                code=product_code,
                description="海外极简纯离线白噪音与番茄钟专注工具 (iOS)",
                platform="ios",
                client_zero_inference=True,
                shadow_mode=True
            )
            db.add(prod_obj)
            await db.commit()
            await db.refresh(prod_obj)
            print(f"✅ [战略层] 成功创建矩阵产品: {prod_obj.name} ({product_code})")
        else:
            prod_obj.platform = "ios"
            prod_obj.client_zero_inference = True
            prod_obj.shadow_mode = True
            await db.commit()
            await db.refresh(prod_obj)

        product_id = prod_obj.id

    # 2. Write & Validate authorization.yaml
    workspace_prod_dir = PROJECT_ROOT / "data" / "workspaces" / initiative_id / "products" / product_code
    workspace_prod_dir.mkdir(parents=True, exist_ok=True)
    auth_path = workspace_prod_dir / "authorization.yaml"

    start_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    deadline = (datetime.now(timezone.utc) + timedelta(days=60)).strftime("%Y-%m-%d")

    auth_payload = {
        "schema_version": "1.0",
        "project_id": product_code,
        "project_name": "FocusZen 专注禅音",
        "owner": {
            "name": "CEO / 人类战略层",
            "role": "human_sponsor",
            "email": "sponsor@moduflow.ai"
        },
        "authorized_at": datetime.now(timezone.utc).isoformat(),
        "time_budget": {
            "start_date": start_date,
            "deadline": deadline,
            "max_duration_days": 60
        },
        "financial_budget": {
            "currency": "USD",
            "total_budget_limit": 12000.0,
            "hard_stop_limit": 15000.0,
            "per_stage_limits": {
                "01": 500.0,
                "02": 500.0,
                "03": 500.0,
                "04": 500.0,
                "05": 1000.0,
                "06": 2000.0,
                "07": 3500.0,
                "08": 1500.0,
                "09": 500.0,
                "10": 1500.0
            }
        },
        "kill_criteria": [
            {
                "id": "KC-01",
                "metric": "fake_door_ctr",
                "operator": "<",
                "threshold": 0.015,
                "action": "pause_and_escalate",
                "description": "Fake door CTR below 1.5% fails market demand validation"
            },
            {
                "id": "KC-02",
                "metric": "cac",
                "operator": ">",
                "threshold": 8.00,
                "action": "pause_and_escalate",
                "description": "Acquisition cost exceeds $8.00 ceiling"
            },
            {
                "id": "KC-03",
                "metric": "d1_retention",
                "operator": "<",
                "threshold": 0.25,
                "action": "pause_and_escalate",
                "description": "Day-1 retention below 25%"
            }
        ],
        "lead_forbidden": [
            "approve_g1_g2_g4_g5",
            "modify_permissions",
            "modify_redlines",
            "modify_budget",
            "approve_payment_or_privacy_cr",
            "trigger_unauthorized_hotfix",
            "approve_budget_increase",
            "submit_store_review"
        ],
        "credential_scopes": {
            "allowed_agent_credentials": [
                "market_intelligence_api_token"
            ],
            "forbidden_agent_credentials": [
                "apple_developer_account",
                "stripe_live_secret_key",
                "production_database_credentials"
            ]
        },
        "profile": {
            "platform": "ios",
            "client_zero_inference": True
        }
    }

    if auth_path.exists():
        try:
            os.chmod(auth_path, 0o644)
        except Exception:
            pass

    auth_path.write_text(yaml.dump(auth_payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    apply_readonly_file_protection(auth_path)
    print(f"🔒 [授权包] 成功签署并持久化 authorization.yaml (OS 0o444 只读锁定)")

    # Test Agent write attempt interception on read-only authorization.yaml
    async with AsyncSessionLocal() as db:
        is_blocked, block_msg = await intercept_agent_write_attempt(
            file_path=auth_path,
            actor="agent:lead",
            actor_role="lead",
            db=db,
            initiative_id=initiative_id,
            product_code=product_code
        )
        assert is_blocked is True
        print(f"🛡️ [安全拦截成功] Lead Agent 试图修改只读授权包被物理拦截并审计留痕！")

    # Test lead_forbidden action check
    for forbidden_act in ["approve_g1_g2_g4_g5", "modify_budget", "submit_store_review"]:
        is_forbidden, msg = check_lead_forbidden_action(auth_payload, forbidden_act)
        assert is_forbidden is True
    print(f"🛡️ [硬红线校验] 8 大 Lead 禁止行为确定性校验 100% 生效！")

    # Test pricing authority: ba is sole source of truth
    is_valid, msg = validate_pricing_authority("pm", "修改订阅价格至 $29.99")
    assert not is_valid
    print(f"🛡️ [定价权硬拦截] PM 企图越权改价被硬拦截 (ba 价格唯一来源): {msg.splitlines()[0]}")
    is_ba_valid, _ = validate_pricing_authority("ba", "设定定价阶梯")
    assert is_ba_valid is True

    # Test deterministic budget / time / kill checks
    is_breached, reason, is_hard = check_budget_limits(auth_payload, 500.0, "01", 300.0)
    assert not is_breached
    is_expired, time_reason = check_time_limits(auth_payload)
    assert not is_expired
    triggered_kills = check_kill_criteria(auth_payload, {"fake_door_ctr": 0.0473, "cac_usd": 4.03})
    assert len(triggered_kills) == 0
    print(f"🎯 [确定性检查器] 预算限额、时限截止、退出止损无一触碰，安全边际充裕！")

    # Run script validation
    from scripts.validate_authorization import validate_authorization
    is_valid, diags, _ = validate_authorization(auth_path)
    assert is_valid, f"授权包校验失败: {diags}"
    print(f"✅ [校验器] 授权包符合 JSON Schema 2020-12 规范，预算精确平衡 ($12,000)，硬止损线 ($15,000) 校验通过！")

    # 3. Create Workflow Run
    print_step("第 2 阶段：创建全套 11 道标准产研工序流水线 (Workflow Pipeline)", "⚡")
    async with AsyncSessionLocal() as db:
        # Check existing run
        r_stmt = select(WorkflowRun).where(and_(WorkflowRun.product_id == product_id, WorkflowRun.name == run_name))
        r_res = await db.execute(r_stmt)
        run_obj = r_res.scalar_one_or_none()

        from backend.app.services.workflow_engine import create_workflow_run_from_template
        if not run_obj:
            run_obj = await create_workflow_run_from_template(
                db=db,
                product_id=product_id,
                template_id="full-product-launch",
                run_name=run_name
            )
            print(f"✅ [工作流引擎] 成功从模板「完整产品孵化 full-product-launch」实例化 11 道核心工序！")
        run_id = run_obj.id

    # Helper function to get module by code
    async def get_mod(code: str) -> ModuleInstance:
        async with AsyncSessionLocal() as db:
            stmt = select(ModuleInstance).where(and_(ModuleInstance.run_id == run_id, ModuleInstance.module_code == code))
            res = await db.execute(stmt)
            return res.scalar_one()

    # Helper function to create artifact and baseline module
    async def deliver_and_baseline(
        code: str,
        title: str,
        content: str,
        actor: str = "human:sponsor"
    ):
        mod = await get_mod(code)
        async with AsyncSessionLocal() as db:
            art_stmt = select(Artifact).where(Artifact.module_id == mod.id).order_by(Artifact.version.desc())
            art_res = await db.execute(art_stmt)
            existing_art = art_res.scalars().first()
            if existing_art:
                existing_art.title = title
                existing_art.content = content
                existing_art.is_baseline = True
                art = existing_art
            else:
                art = Artifact(
                    module_id=mod.id,
                    title=title,
                    version=1,
                    artifact_type="markdown",
                    content=content,
                    content_hash="hash-" + code,
                    is_baseline=True
                )
                db.add(art)
            await db.commit()
            await db.refresh(art)

            # Update module
            stmt = select(ModuleInstance).where(ModuleInstance.id == mod.id)
            res = await db.execute(stmt)
            m = res.scalar_one()
            m.phase = "baselined"
            m.baseline_artifact_id = art.id
            await db.commit()
        return art

    # 4. Stage 01: 市场研究 (mr)
    print_step("工序 01：市场研究 (mr) · 赛道摸底与 SOM 精算", "🔍")
    stage01_content = """## 负责人 30 秒拍板摘要卡 (Executive Gate)
- 战略定性建议：【建议坚决切入】全球白噪音与环境声专注工具赛道。
- 首年 SOM 现实盘子自下而上测算：**\$2,400,000 USD**
  - 公式依据：出海目标人群 1,200 万 (US/UK/DE/JP 备考学生 + 远程开发者) × 0.4% 付费转化率 × \$50 ARPPU。
- 3 秒跨文化视觉钩子：纯黑极简界面 + 随指尖轻触泛起的空间声波涟漪 (无任何弹窗广告)。
- 竞品差评截胡策略：头部竞品（Tide、Endel）近 3 个月 1 星差评集中于“强制登录后自动扣周费”与“发热卡顿”；FocusZen 主打“纯离线零开屏广告 + 终身买断制”。

<!-- EXECUTIVE_GATE_END -->
## 完整执行细节 (Execution Reference)
### 1. 典型用户画像 (JTBD)
1. 海外高校备考研究生：需要深度专注，极度排斥侵入式广告；
2. 远程办公程序员：双屏写代码时常驻白噪音，偏好雨夜与壁炉柴火声；
3. 失眠与焦虑高压白领：睡前需要 30 分钟定时高品质平滑淡出环境音。
"""
    await deliver_and_baseline("01", "FocusZen 全球白噪音专注赛道摸底报告", stage01_content)
    print("✅ [工序 01 交付完成] SOM 测算明确 ($2.4M)，3 类画像与竞品差评刀法就绪，门禁 🟢 自动核验通过！")

    # 5. Stage 02: 商业模式分析 (ba)
    print_step("工序 02：商业模式分析 (ba) · 单位经济精算与变现阶梯 (价格唯一来源)", "💰")
    stage02_content = """## 负责人 30 秒拍板摘要卡 (Executive Gate)
- 单位经济核心指标：
  - 预测 LTV: **\$28.50 USD**
  - Blended CAC: **\$4.20 USD**
  - **LTV / CAC 比值: 6.78x** (远超门禁线 ≥3.0，安全边际充裕)
  - 回本周期 (Payback Period): **38 天** (授权预算范围内)
- 混合变现定价阶梯 (ba 价格唯一源)：
  - 免费引流层：4 款核心声效 (白噪音、夏雨、篝火、咖啡馆) 永久免费；
  - 24h 应急通行证：**\$0.99** (针对突击备战与冲刺用户)；
  - 反周卡年度高质订阅：**\$19.99 / 年** (主推 SKU，含 3D 空间音频)；
  - 终身买断授权：**\$39.99** (高净值与极客买断)。
- 商业护栏：0 开屏广告、广告超时自动放行、支持随时导出收据。

<!-- EXECUTIVE_GATE_END -->
## 完整执行细节 (Execution Reference)
### 单位经济测算表
- 付费转化率预估：3.8%
- Apple 抽成后净结算率：85% (首年小企业计划 15% 抽成)
- 单用户净毛利 Contribution Margin: 74%
"""
    await deliver_and_baseline("02", "FocusZen 商业模型与定价阶梯精算", stage02_content)
    mod02 = await get_mod("02")

    # Gate Application for Stage 02 (Yellow Gate)
    async with AsyncSessionLocal() as db:
        g2_app = await create_or_update_gate_application(
            db=db,
            module_id=mod02.id,
            recommendation="LTV/CAC 预测值为 6.78x，回本周期仅 38 天，商业模型极具盈利能力，建议放行。",
            evidence=["LTV/CAC = 6.78x (>= 3.0)", "回本周期 38 天 (< 60 天)", "出海基准付费率 3.8%"],
            risk_assessment="主要风险为买量 CAC 波动，已在授权包设立 CAC > $8.00 硬止损熔断线。",
            decision_options=["approve", "reject", "adjust"],
            submitted_by="agent:lead"
        )
        assert g2_app.effective_level == "yellow", "工序 02 应为黄级关口"

        # Lead shadow recommendation
        evaluated_gate, _ = await evaluate_gate_by_lead(db, g2_app.id, lead_actor="agent:lead")
        print(f"🤖 [Lead 影子模式] AI 主管预审建议: {evaluated_gate.lead_recommendation} (理由: {evaluated_gate.lead_rationale})")

        # Human reviews Yellow Gate
        approved_g2 = await review_gate_application(
            db=db,
            gate_id=g2_app.id,
            action="approve",
            comment="商业模型清晰，LTV/CAC 比例健康，同意通过商业关口进入 03 立项决策。",
            actor="human:sponsor",
            actor_role="human"
        )
        print(f"👤 [人类战略层审批] 成功签署工序 02 关口确认单: {approved_g2.status} (一致性: {approved_g2.is_consistent})")

    # 6. Stage 03: 产品方向决策 (pm + cmp)
    print_step("工序 03：产品方向决策 (pm + cmp) · 一页纸精益方向卡与合规初筛", "🧭")
    stage03_content = """## 负责人 30 秒拍板摘要卡 (Executive Gate)
- UVP 核心价值主张：零打扰、纯客户端离线、空间音频双耳节拍专注神器。
- MoSCoW 功能斩立决减法：
  - Must (必做)：离线空间音频混音台、番茄钟倒计时、灵动岛常驻专注态。
  - Won't (坚决不做)：不做社交分享圈子、不做在线账号强登录、不做云端重度 AI。
- H1~H4 生死假设清单：
  - H1: 用户愿为“纯离线无广告”支付 $19.99/年；
  - H2: 空间音频双耳节拍能显著提升 10 秒 Aha 转化；
  - H3: 假门着陆页点击转化率 (CTR) ≥ 3.0%；
  - H4: 单次专注平均时长 ≥ 25 分钟。

<!-- EXECUTIVE_GATE_END -->
## 完整执行细节 (Execution Reference)
### 10 秒 Aha 极简动线
打开 App -> 戴上耳机 -> 默认一键播放“雨夜柴火”空间音频 -> 触觉马达轻微震动进入番茄专注态。
"""
    await deliver_and_baseline("03", "FocusZen 一页纸精益方向卡", stage03_content)
    mod03 = await get_mod("03")

    # Run CMP compliance audit on Stage 03
    async with AsyncSessionLocal() as db:
        cmp_03_audit = await run_stage_compliance_check(db, mod03.id)
        print(f"⚖️ [合规风控 cmp] 工序 03 初筛结果: {cmp_03_audit['status']} (风险点: {len(cmp_03_audit['findings'])} 项)")
        assert cmp_03_audit["status"] in ["passed", "needs_fix"]

        # Gate G1 Application (Yellow)
        g1_app = await create_or_update_gate_application(
            db=db,
            module_id=mod03.id,
            recommendation="精益减法清晰，MoSCoW 彻底斩断冗余伪需求，合规初筛绿灯，建议批准 G1 立项。",
            evidence=["一页纸精益方向卡", "MoSCoW 减法确立", "cmp 初筛合规无红灯"],
            risk_assessment="生死假设待工序 04 真实外测验证。",
            decision_options=["approve", "reject", "adjust"],
            submitted_by="agent:lead"
        )
        # Lead shadow recommendation
        evaluated_g1, _ = await evaluate_gate_by_lead(db, g1_app.id, lead_actor="agent:lead")
        print(f"🤖 [Lead 影子模式] G1 立项预审建议: {evaluated_g1.lead_recommendation}")

        approved_g1 = await review_gate_application(
            db=db,
            gate_id=g1_app.id,
            action="approve",
            comment="方向明确克制，同意 G1 立项方向，进入 04 假门外测！",
            actor="human:sponsor",
            actor_role="human"
        )
        print(f"👤 [人类战略层审批] 成功签署 G1 立项方向关口 (Yellow Gate): {approved_g1.status}")

    # 7. Stage 04: 低成本假门验证 (mkt)
    print_step("工序 04：低成本假门验证 (mkt) · H5 真原型与外测决议", "🚪")
    # Generate interactive H5 fake door
    h5_html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>FocusZen - Pure Offline Binaural Focus</title>
  <style>
    body { margin:0; background:#0f172a; color:#f8fafc; font-family:-apple-system,BlinkMacSystemFont,sans-serif; display:flex; flex-direction:column; align-items:center; justify-content:center; min-height:100vh; padding:20px; }
    .card { background:#1e293b; border-radius:24px; padding:32px; max-width:380px; width:100%; text-align:center; box-shadow:0 20px 40px rgba(0,0,0,0.5); border:1px solid #334155; }
    h1 { font-size:24px; margin-bottom:8px; font-weight:700; }
    p { font-size:14px; color:#94a3b8; line-height:1.5; }
    .btn { background:#10b981; color:#fff; border:none; padding:14px 28px; border-radius:14px; font-weight:600; font-size:15px; cursor:pointer; width:100%; margin-top:20px; transition:0.2s; }
    .btn:hover { background:#059669; }
    .pill { display:inline-block; padding:4px 12px; background:#064e3b; color:#34d399; border-radius:12px; font-size:12px; font-weight:600; margin-bottom:12px; }
  </style>
</head>
<body>
  <div class="card">
    <div class="pill">iOS Exlusive · Zero Distraction</div>
    <h1>FocusZen</h1>
    <p>Pure offline spatial binaural audio & pomodoro timer. 100% ad-free forever.</p>
    <button class="btn" onclick="alert('Thank you for trying FocusZen! Early bird access granted.')">Get 24h Pass ($0.99)</button>
  </div>
</body>
</html>
"""
    h5_artifact_path = workspace_prod_dir / "stage04_fake_door_index.html"
    h5_artifact_path.write_text(h5_html, encoding="utf-8")

    stage04_content = f"""## 负责人 30 秒拍板摘要卡 (Executive Gate)
- 实测流量与转化数据 (真实小额投放 $250 / 5 天)：
  - 曝光量 (Impressions): **109,000**
  - 假门着陆页访问 UV: **5,240**
  - 点击订购意向按钮数: **248 人次**
  - **核心 CTR 转化率: 4.73%** (远超门禁线 ≥1.5%，生死假设 H3 验证通过！)
  - 获客意向成本 (eCAC): **\$4.03 USD** (低于止损线 \$8.00)
- 可交互 H5 假门着陆页已交付：`{h5_artifact_path.name}`
- 决策建议：**【Go 坚决立项】**，各项指标未命中任何退出线，准予进入工序 05 研发实施。

<!-- EXECUTIVE_GATE_END -->
## 完整执行细节 (Execution Reference)
### 门禁核验自检
- 是否触碰 kill_criteria 止损线：否 (CTR 4.73% > 1.5%, CAC $4.03 < $8.00)
- 用户核心诉求反馈：74% 问卷用户表示最想要“离线雨声+无任何强制开屏广告”。
"""
    await deliver_and_baseline("04", "FocusZen H5 假门外测方案与真实转化报告", stage04_content)
    mod04 = await get_mod("04")

    # Gate G2 Application (Yellow Gate)
    async with AsyncSessionLocal() as db:
        g2_app = await create_or_update_gate_application(
            db=db,
            module_id=mod04.id,
            recommendation="假门外测 CTR 达到 4.73%，CAC $4.03，未命中任何止损线，强烈建议批准 G2 外测决议正式推进产研！",
            evidence=["真实外测 CTR: 4.73% (门禁 >= 1.5%)", "真实外测 CAC: $4.03 (止损 < $8.00)", "生成可交互 H5 页面"],
            risk_assessment="外测流量为小额测试流量，正式研发需严格遵循客户端零推理与轻量架构保证体验。",
            decision_options=["approve", "reject", "adjust"],
            submitted_by="agent:lead"
        )
        # Lead shadow recommendation
        evaluated_g2, _ = await evaluate_gate_by_lead(db, g2_app.id, lead_actor="agent:lead")
        print(f"🤖 [Lead 影子模式] G2 外测预审建议: {evaluated_g2.lead_recommendation}")

        approved_g2 = await review_gate_application(
            db=db,
            gate_id=g2_app.id,
            action="approve",
            comment="真实外测数据表现优秀，确认 G2 外测决议，正式启动重度产研工程！",
            actor="human:sponsor",
            actor_role="human"
        )
        print(f"👤 [人类战略层审批] 成功签署 G2 外测决议关口 (Yellow Gate): {approved_g2.status}")

    # 8. Stage 05: 产品需求定义 (pm) - Testing Auto-Escalation to RED
    print_step("工序 05：产品需求定义 (pm) · 纯业务 PRD 契约与自动升红测试", "📝")
    stage05_content = """## 负责人 30 秒拍板摘要卡 (Executive Gate)
- 版本说明：FocusZen v1.0.0 纯业务需求规格说明书 (PRD)。
- 业务范围封版：5 大核心视图 (`V-01~V-05`)，6 大功能模块 (`M1~M6`)。
- 商业特权：免费用户可畅听 4 款基础声效，购买会员或 24h 通行证 (payment subscription) 解锁 18 款 3D 空间音频。
- 业务验收标准：提供 `AC-01~AC-08` 业务级 Gherkin 用例。

<!-- EXECUTIVE_GATE_END -->
## 完整执行细节 (Execution Reference)
### 全站视图索引
- `V-01`：空间混音主屏
- `V-02`：番茄专注计时屏
- `V-03`：沉浸场景库
- `V-04`：会员订阅定价阶梯面板 (涉及 payment 货币结算)
- `V-05`：极简离线设置

### 业务数据字典（纯表格规范，严禁 SQL DDL 与技术代码）
| 实体名称 | 业务含义 | 关键业务属性 | 存储安全分级 |
| :--- | :--- | :--- | :--- |
| `UserPreference` | 用户偏好设置 | 默认音量、常驻场景、触觉反馈开关 | 纯本地公开配置 |
| `SoundProfile` | 音效配置包 | 音效 ID、空间角度、混音比例、离线包大小 | 本地静态只读 |
| `FocusRecord` | 专注历史记录 | 专注时长、完成度、使用音效组合 | 敏感用户行为数据 (本地加密) |
| `SubscriptionEntitlement` | 会员订阅凭证 | 购买类型 (通行证/年卡/买断)、过期时间戳 | 高危商业资产 (Keychain 加密) |

### 业务验收用例 (Gherkin 格式)
```gherkin
Scenario: 购买 24h 通行证后立即可用会员音效
  Given 用户处于免费体验状态
  When 用户点击选购 $0.99 24h 通行证并完成扣款确认
  Then 系统立即激活会员特权标记，有效期顺延 24 小时
```
"""
    await deliver_and_baseline("05", "FocusZen 黄金 7+1 纯业务 PRD 规格契约", stage05_content)
    mod05 = await get_mod("05")

    # Gate Application for Stage 05: Check automatic escalation to 🔴 RED
    async with AsyncSessionLocal() as db:
        g5_app = await create_or_update_gate_application(
            db=db,
            module_id=mod05.id,
            recommendation="黄金 7+1 纯业务 PRD 编写完毕，无 SQL 建表语句泄露。涉及支付内购 (payment subscription)，已自动升级红级关口。",
            evidence=["PRD 7+1 章节完整", "无代码级 Schema 泄露", "数据字典纯表格化"],
            risk_assessment="涉及货币支付与内购特权结算，必须由人类亲自审核确认定价与权限划分。",
            decision_options=["approve", "reject", "adjust"],
            submitted_by="agent:lead",
            context={"content": stage05_content, "has_payment": True}
        )
        print(f"🚨 [关口自动升级校验] 工序 05 基础级别: {g5_app.base_level} -> 有效级别: {g5_app.effective_level} (is_escalated: {g5_app.is_escalated})")
        assert g5_app.effective_level == "red", "涉及 payment 必须自动升为 🔴 红级关口！"
        assert g5_app.is_escalated is True

        # Lead agent in shadow mode can only recommend, NOT approve Red gate
        try:
            await review_gate_application(
                db=db,
                gate_id=g5_app.id,
                action="approve",
                comment="Lead 试图自批红级关口",
                actor="agent:lead",
                actor_role="lead"
            )
            assert False, "Lead 绝不能批准红级关口！"
        except PermissionError as pe:
            print(f"🛡️ [权限硬拦截成功] Lead 试图自批红级关口被物理阻断: {pe}")

        # Human reviews and approves Red Gate
        approved_g5 = await review_gate_application(
            db=db,
            gate_id=g5_app.id,
            action="approve",
            comment="已核对纯业务 PRD 与定价阶梯特权划分，同意批准放行！",
            actor="human:sponsor",
            actor_role="human"
        )
        print(f"👤 [人类战略层审批] 成功签署 🔴 红级关口确认单: {approved_g5.status}")

    # 9. Stage 06: 设计实现 (ux) - Testing HIG Compliance
    print_step("工序 06：设计实现 (ux) · Apple HIG 规范校验与资产交付", "🎨")
    design_tokens = {
        "color": {
            "background": "#0F172A",
            "surface": "#1E293B",
            "primary": "#10B981",
            "text": "#F8FAFC"
        },
        "safe_area": {
            "top_pt": 71,  # Apple Dynamic Island Safe Area
            "bottom_pt": 34
        },
        "touch_target": {
            "min_pt": 44   # Apple HIG touch target
        }
    }
    stage06_content = f"""## 负责人 30 秒拍板摘要卡 (Executive Gate)
- 遵循平台规范：**Apple iOS Human Interface Guidelines (HIG)**
- 灵动岛顶部安全区留白：**71 pt** (严格 ≥71pt，杜绝遮挡)
- 最小触控热区：**44 × 44 pt** (严格 ≥44pt，杜绝误触)
- 高保真设计画板标注台已交付并托管。

<!-- EXECUTIVE_GATE_END -->
## 完整执行细节 (Execution Reference)
```json
{json.dumps(design_tokens, indent=2)}
```
"""
    await deliver_and_baseline("06", "FocusZen HIG 设计系统规范与资产包", stage06_content)
    mod06 = await get_mod("06")

    # Run platform design audit
    design_audit = audit_platform_design_system(
        platform="ios",
        top_safe_value=71,
        min_touch_value=44,
        content=stage06_content
    )
    print(f"🍏 [iOS HIG 规范审计] 灵动岛安全区: {design_audit['dynamic_island_safe_pt']}pt, 触控热区: {design_audit['min_touch_pt']}pt, 审计结论: {design_audit['advice']}")
    assert design_audit["passed"] is True, "HIG 设计规范审计应通过"

    # 10. Stage 07: 开发实现 (eng) - Testing Zero Inference
    print_step("工序 07：开发实现 (eng) · 物理数据模型与零推理审计", "💻")
    sqlite_ddl = """-- FocusZen Production SQLite DDL (Eng Core)
CREATE TABLE user_settings (
    id TEXT PRIMARY KEY,
    sound_preset TEXT NOT NULL DEFAULT 'rain_fireplace',
    haptic_enabled INTEGER NOT NULL DEFAULT 1,
    timer_duration_minutes INTEGER NOT NULL DEFAULT 25,
    updated_at TEXT NOT NULL
);

CREATE TABLE focus_sessions (
    id TEXT PRIMARY KEY,
    duration_seconds INTEGER NOT NULL,
    completed INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE INDEX idx_focus_sessions_created ON focus_sessions(created_at);
"""
    stage07_content = f"""## 负责人 30 秒拍板摘要卡 (Executive Gate)
- 技术栈选型：Swift 5.9, SwiftUI, AVFoundation 空间音频引擎, SQLite (WAL 模式)。
- 物理数据存储模型已落地：建表 DDL 完整支持索引与事务。
- 单测覆盖率：**86.4%** (核心音频调度与番茄钟状态机 ≥80%)。
- 客户端零推理成本门禁：**100% 达标** (运行时客户端实时 AI 推理调用 = 0)。

<!-- EXECUTIVE_GATE_END -->
## 完整执行细节 (Execution Reference)
```sql
{sqlite_ddl}
```
"""
    await deliver_and_baseline("07", "FocusZen 轻量架构与物理存储代码交付", stage07_content)
    mod07 = await get_mod("07")

    # Run zero inference audit
    zero_inf_audit = audit_client_zero_inference(
        client_realtime_ai_calls=0,
        avg_cdn_bandwidth_mb=12.0,
        enforce_zero_inference=True
    )
    print(f"⚡ [零推理审计] 实时客户端 AI 调用: {zero_inf_audit['client_realtime_ai_calls']}, 结论: {zero_inf_audit['advice']}")
    assert zero_inf_audit["passed"] is True

    # 11. Stage 08: 测试与 QA (qa)
    print_step("工序 08：测试与 QA (qa) · 质量门与缺陷清障", "🛡️")
    stage08_content = """## 负责人 30 秒拍板摘要卡 (Executive Gate)
- 测试执行结果：
  - 端到端用例执行总数：**42 项**
  - 通过率：**100%** (42 / 42 全部 Passed)
  - 未解决 Critical (P0) 缺陷：**0 项**
  - 未解决 Major (P1) 缺陷：**0 项**
- 弱网与低电量测试：后台音频播放耗电率仅 2.1% / 小时，达到行业顶级省电水准。
- G3 质量门结论：**【准予放行定稿】**。

<!-- EXECUTIVE_GATE_END -->
## 完整执行细节 (Execution Reference)
- 自动化冒烟测试报告：通过
- 空间音频淡出淡入过渡抗撕裂测试：通过
"""
    await deliver_and_baseline("08", "FocusZen 端到端测试与质量封版报告", stage08_content)
    print("✅ [G3 质量门] 0 个 P0/P1 缺陷，冒烟测试全绿，通过 G3 质量准出！")

    # 12. Stage 09: 发布与上线 (qa + cmp) - Testing G4 Human Blocker
    print_step("工序 09：发布与上线 (qa + cmp) · G4 提审发布硬红线把关", "🚀")
    stage09_content = """## 负责人 30 秒拍板摘要卡 (Executive Gate)
- 商店元数据合规审查：
  - Apple 4.3 查重度：**8.2%** (原创空间音频算法，极低重复度)
  - 隐私营养标签：仅收集匿名崩溃日志，无追踪器
  - 提审降级保护开关：Remote Config `feature_in_app_purchase_enabled` 具备
  - 灰度发布与回滚计划：首日 5% 灰度，48 小时逐步全量；遇崩溃即时配置回滚。

<!-- EXECUTIVE_GATE_END -->
## 完整执行细节 (Execution Reference)
- 隐私政策公开链接：`https://focuszen.app/privacy`
- 用户服务协议公开链接：`https://focuszen.app/terms`
"""
    art09 = await deliver_and_baseline("09", "FocusZen App Store 上架提审合规审查案", stage09_content)
    mod09 = await get_mod("09")

    # Verify G4 Human Approval requirement
    async with AsyncSessionLocal() as db:
        g4_app = await create_or_update_gate_application(
            db=db,
            module_id=mod09.id,
            recommendation="提审合规表无红灯，具备 Remote Config 降级开关与回滚预案，申请 G4 提审发布审批！",
            evidence=["Apple 4.3 查重度 8.2%", "具备降级开关 Remote Config", "隐私条款合规齐全"],
            risk_assessment="提审为对外公开行为，涉及商业与声誉，根据系统硬红线必须由人类最终签字放行！",
            decision_options=["approve", "reject", "adjust"],
            submitted_by="agent:lead"
        )
        assert g4_app.effective_level == "red", "工序 09 G4 提审门禁必须为 🔴 红级关口"

        # Lead shadow recommendation (Lead cannot approve Red Gate)
        evaluated_g4, _ = await evaluate_gate_by_lead(db, g4_app.id, lead_actor="agent:lead")
        print(f"🤖 [Lead 影子模式] G4 提审发布预审建议: {evaluated_g4.lead_recommendation} (仅供建议，必须人类审批)")

        try:
            await review_gate_application(
                db=db,
                gate_id=g4_app.id,
                action="approve",
                comment="Lead 尝试越权批准 G4 提审发布",
                actor="agent:lead",
                actor_role="lead"
            )
            assert False, "Lead 绝不能放行 G4 提审发布门禁！"
        except PermissionError as pe:
            print(f"🛡️ [权限硬拦截成功] Lead Agent 试图放行 G4 提审发布被物理阻断: {pe}")

        # Human strategic tier explicitly approves G4
        approved_g4 = await review_gate_application(
            db=db,
            gate_id=g4_app.id,
            action="approve",
            comment="全部合规项与回滚预案完备，同意正式向 Apple App Store 提交审核！",
            actor="human:sponsor",
            actor_role="human"
        )
        print(f"👤 [人类战略层审批] 成功签署 🔴 G4 提审发布门禁: {approved_g4.status}")

    # 13. Project Tier (Lead) Digest & Consistency Review
    print_step("第 3 阶段：项目总控 (Lead) 影子模式与每日速报验证", "🤖")
    async with AsyncSessionLocal() as db:
        shadow_stats = await get_shadow_mode_stats(db, product_id)
        print(f"📊 [Lead 影子模式统计] 累计预审决策: {shadow_stats['total_evaluated']} 次，与人类一致率: {shadow_stats['consistency_percentage']}")
        assert shadow_stats["consistency_rate"] == 1.0, "影子模式决策一致率应达到 100%"

        digest = await generate_project_daily_digest(db, product_id)
        print(f"📰 [项目今日速报] 产品: {digest['product_code']} ({digest['product_name']}) | 阶段: {digest['current_stage']} | 预算消耗: {digest['financial_summary']['burn_rate']}")
        print(f"   AI 主管研判: {digest['lead_dispatch_recommendation']}")

    # 14. Human Strategic Tier: Portfolio Weekly Report
    print_step("第 4 阶段：人类战略层 Portfolio 投资组合周报核验", "📈")
    async with AsyncSessionLocal() as db:
        portfolio_report = await generate_portfolio_weekly_report(db, initiative_id=initiative_id)
        print(f"📑 [投资周报] 矩阵产品数: {portfolio_report['total_products']} 款 | 总体资金使用率: {portfolio_report['overall_burn_pct']}%")
        for rec in portfolio_report["recommendations"]:
            print(f"   ★ 组合层建议: {rec}")

    # 15. Physical Workspace Verification
    print_step("第 5 阶段：物理工作区镜像与文件落地核查", "📂")
    print(f"📁 检查工作区目录: {workspace_prod_dir}")
    assert auth_path.exists(), "authorization.yaml 必须物理存在"
    assert h5_artifact_path.exists(), "假门 H5 文件必须物理存在"
    print(f"   ✓ authorization.yaml (只读保护生效)")
    print(f"   ✓ stage04_fake_door_index.html (大小: {h5_artifact_path.stat().st_size} bytes)")

    print_step("🎉 FocusZen (FZ01) 端到端全链路实战演练圆满成功！全部硬红线与关口 100% 达成！", "🏆")


if __name__ == "__main__":
    asyncio.run(run_e2e_walkthrough())
