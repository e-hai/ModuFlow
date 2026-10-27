import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.tests.conftest import (
    test_engine as engine,
    TestingSessionLocal as AsyncSessionLocal,
    ensure_test_product_authorization
)
from backend.app.core.database import Base
from backend.app.services.workflow_engine import seed_templates_if_empty, create_workflow_run_from_template
from backend.app.services.agent_roles import seed_agent_roles_if_empty
from backend.app.models.entities import StrategicInitiative, Product, ExecutiveRisk, ExecutiveDecision
from backend.app.core.config import settings
from sqlalchemy import select

@pytest_asyncio.fixture(autouse=True)
async def init_test_db():
    settings.AGENT_ADAPTER_TYPE = "simulator"
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        await seed_templates_if_empty(db)
        await seed_agent_roles_if_empty(db)
        stmt = select(StrategicInitiative).where(StrategicInitiative.id == "sea-2026")
        res = await db.execute(stmt)
        if not res.scalar_one_or_none():
            demo_init = StrategicInitiative(
                id="sea-2026",
                name="进军东南亚市场战略工程",
                description="2026 年度核心战略",
                owner="创始人",
                budget=500000.0,
                status="validating",
                strategic_intent="以轻量记账为高频获客切口，聚合支付沉淀商户资金池，打通'记账->收单->增值金融'商业闭环。",
                target_market="印尼、越南下沉市场中小微商户 (MSME) 及个人记账用户",
                business_model_hypothesis="前端记账获客 CAC 控制在 ¥15 以内，后端支付工具转化率 >= 8%，LTV/CAC 达标 3.0x",
                budget_total=500000.0,
                committed_unpaid=80000.0,
                actual_paid=215000.0,
                revenue_recognized=350000.0,
                cash_collected=320000.0,
                currency="CNY",
                marketing_summary={
                    "total_spend": 215000.0,
                    "effective_new_users": 18500,
                    "blended_cac": 11.62,
                    "categories": [
                        {
                            "category_code": "paid_acquisition",
                            "category_name": "付费广告投放 (Paid Acquisition)",
                            "spend": 85000.0,
                            "acquired_users": 4200,
                            "user_share_percent": 22.7,
                            "cac": 20.24,
                            "conversion_rate": 3.8,
                            "revenue_contribution": 45000.0,
                            "payback_days": 180,
                            "decision_recommendation": "优化买量创意并调减超标渠道预算",
                            "sub_channels": []
                        },
                        {
                            "category_code": "partnerships",
                            "category_name": "达人与异业渠道 (Partnerships)",
                            "spend": 60000.0,
                            "acquired_users": 4800,
                            "user_share_percent": 25.9,
                            "cac": 12.50,
                            "conversion_rate": 6.2,
                            "revenue_contribution": 92000.0,
                            "payback_days": 90,
                            "decision_recommendation": "追加高转化达人独家合作",
                            "sub_channels": []
                        },
                        {
                            "category_code": "organic_referral",
                            "category_name": "自然流量与裂变 (Organic & Referral)",
                            "spend": 70000.0,
                            "acquired_users": 9500,
                            "user_share_percent": 51.4,
                            "cac": 7.37,
                            "conversion_rate": 12.5,
                            "revenue_contribution": 213000.0,
                            "payback_days": 45,
                            "decision_recommendation": "持续扩大推荐返佣",
                            "sub_channels": []
                        }
                    ]
                },
                operations_summary={
                    "dau": 18500,
                    "mau": 62000,
                    "retention_1d": 42.5,
                    "retention_7d": 28.0,
                    "retention_30d": 19.4,
                    "paid_users": 2850,
                    "arpu": 18.9,
                    "arppu": 122.8,
                    "ltv": 45.0,
                    "ltv_cac_ratio": 3.87,
                    "funnel": [
                        {"stage": "应用安装/访问", "count": 65000, "conversion_rate": 100.0},
                        {"stage": "完成首次记账", "count": 28500, "conversion_rate": 43.8},
                        {"stage": "连续记账 7 天", "count": 18500, "conversion_rate": 64.9},
                        {"stage": "开通聚合收款", "count": 4200, "conversion_rate": 22.7},
                        {"stage": "完成首笔扫码", "count": 2850, "conversion_rate": 67.9}
                    ]
                }
            )
            db.add(demo_init)
            await db.flush()

            risk_1 = ExecutiveRisk(
                id="RISK-001",
                initiative_id=demo_init.id,
                product_code="ACC-SEA",
                rule_code="CAC_SPIKE",
                title="付费获客 CAC 偏离警戒线",
                description="Google 搜索广告获客成本超标",
                severity="critical",
                action_suggestion="建议调减预算转投高 ROI 渠道",
                is_resolved=False
            )
            dec_1 = ExecutiveDecision(
                id="DEC-001",
                initiative_id=demo_init.id,
                title="调减 ACC-SEA 低效投放预算，追加至 QPAY 聚合收单变现",
                status="proposed",
                recommendation_json={
                    "action_type": "transfer_budget",
                    "from_product_code": "ACC-SEA",
                    "to_product_code": "QPAY",
                    "amount": 35000.0,
                    "target_entity": "ACC-SEA"
                },
                evidence_json={
                    "metric": "CAC",
                    "threshold": 15.0,
                    "current_value": 25.0
                },
                impact_projection_json={
                    "projected_ltv_cac": 3.8
                },
                idempotency_key="reallocate-acc-to-qpay-v1"
            )
            db.add_all([risk_1, dec_1])
            await db.flush()
            prod_a = Product(
                id="accounting-sea",
                initiative_id=demo_init.id,
                name="记账本（东南亚版）",
                code="ACC-SEA",
                description="记账产品",
                strategic_role="acquisition",
                stage="growth",
                budget_allocated=220000.0,
                actual_spent=118000.0,
                revenue_contribution=85000.0,
                kpi_name="MAU",
                kpi_target=200000.0,
                kpi_actual=186000.0,
                kpi_unit="人"
            )
            prod_b = Product(
                id="quickpay",
                initiative_id=demo_init.id,
                name="QuickPay 聚合支付",
                code="QPAY",
                description="聚合支付产品",
                strategic_role="monetization",
                stage="building",
                budget_allocated=280000.0,
                actual_spent=97000.0,
                revenue_contribution=265000.0,
                kpi_name="月交易流水 (GMV)",
                kpi_target=5000000.0,
                kpi_actual=3820000.0,
                kpi_unit="元"
            )
            db.add_all([prod_a, prod_b])
            await db.commit()
            ensure_test_product_authorization("sea-2026", "ACC-SEA", budget=prod_a.budget_allocated or 5000.0)
            ensure_test_product_authorization("sea-2026", "QPAY", budget=prod_b.budget_allocated or 5000.0)
            await create_workflow_run_from_template(
                db=db,
                product_id=prod_a.id,
                template_id="fast-iteration",
                run_name="v1.0 东南亚首发迭代"
            )
            await create_workflow_run_from_template(
                db=db,
                product_id=prod_b.id,
                template_id="full-product-launch",
                run_name="探索期可行性论证"
            )
    yield

@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

@pytest.mark.asyncio
async def test_initiatives_and_runs():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Check initiatives
        res = await ac.get("/api/v1/initiatives")
        assert res.status_code == 200
        data = res.json()
        assert len(data) >= 1
        assert "东南亚" in data[0]["name"]

        # Check products
        res_prod = await ac.get("/api/v1/products")
        assert res_prod.status_code == 200
        products = res_prod.json()
        assert len(products) >= 2

        # Check runs
        res_runs = await ac.get(f"/api/v1/runs?product_id={products[0]['id']}")
        assert res_runs.status_code == 200
        runs = res_runs.json()
        assert len(runs) >= 1

        # Check run details with modules
        run_id = runs[0]["id"]
        res_run_detail = await ac.get(f"/api/v1/runs/{run_id}")
        assert res_run_detail.status_code == 200
        run_detail = res_run_detail.json()
        assert len(run_detail["modules"]) > 0

        # Test session interaction on first module
        first_mod = run_detail["modules"][0]
        res_sess = await ac.get(f"/api/v1/modules/{first_mod['id']}/session")
        assert res_sess.status_code == 200
        sess_data = res_sess.json()
        sess_id = sess_data["id"]

        # 1. Post instruction message (Human to Agent) -> generates v1
        post_msg = await ac.post(
            f"/api/v1/sessions/{sess_id}/messages?trigger_agent=true",
            json={
                "sender": "Alice",
                "sender_role": "product_manager",
                "message_type": "instruction",
                "content": "请输出东南亚记账 App 的 PRD 初稿，重点包含离线支持和印尼盾货币格式。"
            }
        )
        assert post_msg.status_code == 200
        messages = post_msg.json()
        assert len(messages) == 2
        assert messages[1]["message_type"] == "draft_artifact"
        art_id = messages[1]["artifact_ref_id"]
        assert art_id is not None

        # Check artifact
        res_art = await ac.get(f"/api/v1/artifacts/{art_id}")
        assert res_art.status_code == 200
        assert len(res_art.json()["content"]) > 20

        # 2. Post human feedback -> Agent revises to v2
        post_feedback = await ac.post(
            f"/api/v1/sessions/{sess_id}/messages?trigger_agent=true",
            json={
                "sender": "Alice",
                "sender_role": "product_manager",
                "message_type": "feedback",
                "content": "补充印尼本土电子钱包（OVO, GoPay）记账分类支持。"
            }
        )
        assert post_feedback.status_code == 200
        fb_msgs = post_feedback.json()
        assert len(fb_msgs) == 2
        assert fb_msgs[1]["message_type"] == "revised_artifact"
        v2_art_id = fb_msgs[1]["artifact_ref_id"]

        res_v2 = await ac.get(f"/api/v1/artifacts/{v2_art_id}")
        assert res_v2.json()["version"] == 2
        assert "OVO" in res_v2.json()["content"]

        # 3. Test Cross-module Issue Creation: Tester reports Bug targeting first_mod
        second_mod = run_detail["modules"][1] if len(run_detail["modules"]) > 1 else first_mod
        post_issue = await ac.post(
            "/api/v1/issues",
            json={
                "title": "登录闪退并导致本地缓存损坏",
                "source_module_id": second_mod["id"],
                "target_module_id": first_mod["id"],
                "reporter": "Bob",
                "reporter_role": "tester",
                "category": "bug",
                "severity": "critical",
                "priority": "P0",
                "description": {
                    "summary": "Android 11 设备首次启动闪退",
                    "steps": ["打开 App", "点击登录"],
                    "expected": "正常进入",
                    "actual": "闪退"
                }
            }
        )
        assert post_issue.status_code == 200
        issue_data = post_issue.json()
        assert issue_data["id"].startswith("ISSUE-")
        assert issue_data["severity"] == "critical"

        # 4. Attempt to baseline module while critical issue is open -> should fail with 400!
        res_baseline_fail = await ac.patch(
            f"/api/v1/modules/{first_mod['id']}/phase",
            json={"phase": "baselined"}
        )
        assert res_baseline_fail.status_code == 400
        assert "未解决的严重卡点问题" in res_baseline_fail.json()["detail"]

        # 5. Close the issue and then baseline should succeed!
        res_close = await ac.patch(
            f"/api/v1/issues/{issue_data['id']}",
            json={"status": "closed", "resolution": "fixed"}
        )
        assert res_close.status_code == 200
        assert res_close.json()["status"] == "closed"

        res_baseline_ok = await ac.patch(
            f"/api/v1/modules/{first_mod['id']}/phase",
            json={"phase": "baselined"}
        )
        assert res_baseline_ok.status_code == 200
        assert res_baseline_ok.json()["phase"] == "baselined"

@pytest.mark.asyncio
async def test_create_new_initiative_and_product():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Create new initiative
        res_init = await ac.post(
            "/api/v1/initiatives",
            json={
                "name": "北美跨境电商独立站矩阵战略",
                "description": "2026 年度北美出海品类战略",
                "owner": "CEO",
                "budget": 500000.0,
                "status": "active"
            }
        )
        assert res_init.status_code == 200
        init_data = res_init.json()
        assert init_data["name"] == "北美跨境电商独立站矩阵战略"
        init_id = init_data["id"]

        # Create new product under this initiative
        res_prod = await ac.post(
            "/api/v1/products",
            json={
                "name": "北美快时尚独立站 Web 端",
                "code": "NA-WEB",
                "description": "主站 Web 体验",
                "initiative_id": init_id
            }
        )
        assert res_prod.status_code == 200
        prod_data = res_prod.json()
        assert prod_data["code"] == "NA-WEB"
        assert prod_data["initiative_id"] == init_id

        # Verify listing filtered by this initiative
        res_list = await ac.get(f"/api/v1/products?initiative_id={init_id}")
        assert res_list.status_code == 200
        products = res_list.json()
        assert len(products) == 1
        assert products[0]["code"] == "NA-WEB"

        # Rename initiative
        res_rename = await ac.patch(
            f"/api/v1/initiatives/{init_id}",
            json={"name": "北美跨境出海超级矩阵战略"}
        )
        assert res_rename.status_code == 200
        assert res_rename.json()["name"] == "北美跨境出海超级矩阵战略"

        # Delete initiative
        res_del = await ac.delete(f"/api/v1/initiatives/{init_id}")
        assert res_del.status_code == 200
        assert res_del.json()["ok"] is True

        # Verify it's gone
        res_get_del = await ac.delete(f"/api/v1/initiatives/{init_id}")
        assert res_get_del.status_code == 404

@pytest.mark.asyncio
async def test_executive_cockpit_and_decision():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Fetch Executive Cockpit for sea-2026
        res = await ac.get("/api/v1/initiatives/sea-2026/cockpit?period=lifetime")
        assert res.status_code == 200
        cockpit = res.json()
        
        # Verify General Info
        assert cockpit["initiative_id"] == "sea-2026"
        assert "战略工程" in cockpit["initiative_name"]
        assert cockpit["status"] == "validating"
        assert cockpit["period"] == "lifetime"
        
        # Verify Financial Ledger (收付实现制现金流 vs 权责发生制)
        fin = cockpit["financials"]
        assert fin["budget_total"] == 500000.0
        assert fin["committed_unpaid"] == 80000.0
        assert fin["actual_paid"] == 215000.0
        # Available = 500000 - 80000 - 215000 = 205000
        assert fin["available_budget"] == 205000.0
        assert fin["cash_collected"] == 320000.0
        # Net Cash Flow = 320000 - 215000 = 105000
        assert fin["net_cash_flow"] == 105000.0
        assert fin["revenue_recognized"] == 350000.0
        assert fin["net_cash_flow"] > 0
        
        # Verify Focus Alerts
        alerts = cockpit["focus_alerts"]
        assert len(alerts) >= 1
        
        # Verify Portfolio
        portfolio = cockpit["portfolio"]
        assert len(portfolio) >= 2
        acc_sea = next(p for p in portfolio if p["code"] == "ACC-SEA")
        assert acc_sea["strategic_role"] == "acquisition"
        assert acc_sea["budget_allocated"] == 220000.0
        
        # Verify Marketing and Operations
        assert len(cockpit["marketing"]["categories"]) == 3
        cat_codes = [c["category_code"] for c in cockpit["marketing"]["categories"]]
        assert "paid_acquisition" in cat_codes
        assert "partnerships" in cat_codes
        assert "organic_referral" in cat_codes
        assert cockpit["operations"]["dau"] == 18500
        assert cockpit["operations"]["ltv_cac_ratio"] > 3.0
        
        # Verify Risks and Decisions
        assert len(cockpit["risks"]) >= 1
        assert len(cockpit["decisions"]) >= 1
        dec = cockpit["decisions"][0]
        assert dec["status"] == "proposed"
        
        # 2. Test CEO Decision Execution (Approve budget transfer)
        dec_id = dec["id"]
        res_action = await ac.post(
            f"/api/v1/initiatives/sea-2026/decisions/{dec_id}/action",
            json={
                "action": "approve",
                "operator": "CEO"
            }
        )
        assert res_action.status_code == 200
        approved_dec = res_action.json()
        assert approved_dec["status"] in ["approved", "executed"]
        assert approved_dec["approved_by"] == "CEO"
        
        # 3. Check cockpit again to verify budget transfer executed
        res_updated = await ac.get("/api/v1/initiatives/sea-2026/cockpit?period=lifetime")
        assert res_updated.status_code == 200
        updated_cockpit = res_updated.json()
        updated_portfolio = updated_cockpit["portfolio"]
        updated_acc_sea = next(p for p in updated_portfolio if p["code"] == "ACC-SEA")
        updated_qpay = next(p for p in updated_portfolio if p["code"] == "QPAY")
        
        # Budget was transferred from ACC-SEA to QPAY (35,000)
        assert updated_acc_sea["budget_allocated"] == 185000.0
        assert updated_qpay["budget_allocated"] == 315000.0

@pytest.mark.asyncio
async def test_single_active_iteration_lifecycle():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Product ACC-SEA already has an in_progress run from test fixture
        res_prod = await ac.get("/api/v1/products?initiative_id=sea-2026")
        acc_sea = next(p for p in res_prod.json() if p["code"] == "ACC-SEA")
        
        # 1. Attempting to create a second concurrent iteration must FAIL with 400
        res_fail = await ac.post(
            "/api/v1/runs",
            json={
                "product_id": acc_sea["id"],
                "template_id": "fast-iteration",
                "name": "v2.0 并行冲突测试"
            }
        )
        assert res_fail.status_code == 400
        assert "不允许并行" in res_fail.json()["detail"]
        
        # 2. Get the current active run
        res_runs = await ac.get(f"/api/v1/runs?product_id={acc_sea['id']}")
        runs = res_runs.json()
        assert len(runs) == 1
        active_run = runs[0]
        assert active_run["status"] == "in_progress"
        
        # 3. Rename and then Complete the active run
        res_rename = await ac.patch(
            f"/api/v1/runs/{active_run['id']}",
            json={"name": "v1.0 东南亚首发正式封版", "status": "completed"}
        )
        assert res_rename.status_code == 200
        assert res_rename.json()["name"] == "v1.0 东南亚首发正式封版"
        assert res_rename.json()["status"] == "completed"
        
        # 4. Now that previous run is completed, creating the NEXT iteration MUST SUCCEED!
        res_next = await ac.post(
            "/api/v1/runs",
            json={
                "product_id": acc_sea["id"],
                "template_id": "fast-iteration",
                "name": "v1.1 支付功能拓展迭代"
            }
        )
        assert res_next.status_code == 200
        next_run = res_next.json()
        assert next_run["status"] == "in_progress"
        assert next_run["name"] == "v1.1 支付功能拓展迭代"
        
        # 5. Verify total runs is now 2 (1 completed, 1 in_progress)
        res_all = await ac.get(f"/api/v1/runs?product_id={acc_sea['id']}")
        all_runs = res_all.json()
        assert len(all_runs) == 2
        statuses = [r["status"] for r in all_runs]
        assert "completed" in statuses
        assert "in_progress" in statuses

@pytest.mark.asyncio
async def test_workspace_physical_sync():
    """Test physical workspace disk sync and tree retrieval."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Trigger sync
        res_sync = await ac.post("/api/v1/initiatives/sea-2026/sync-workspace")
        assert res_sync.status_code == 200
        sync_data = res_sync.json()
        assert sync_data["success"] is True
        assert sync_data["initiative_id"] == "sea-2026"
        assert sync_data["products_count"] == 2

        # Inspect tree
        res_tree = await ac.get("/api/v1/initiatives/sea-2026/workspace-tree")
        assert res_tree.status_code == 200
        tree_data = res_tree.json()
        assert tree_data["exists"] is True
        assert tree_data["tree"]["name"] == "sea-2026"

@pytest.mark.asyncio
async def test_agent_roles_api():
    """Test listing agent roles and retrieving module-assigned roles."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. List all roles (Lead + 8 Stage Specialists)
        res_roles = await ac.get("/api/v1/roles")
        assert res_roles.status_code == 200
        roles = res_roles.json()
        assert len(roles) >= 8
        role_codes = [r["role_code"] for r in roles]
        assert "lead" in role_codes
        assert "mr" in role_codes
        assert "ba" in role_codes
        assert "pm" in role_codes
        assert "eng" in role_codes

        # 2. Get specific role
        res_pm = await ac.get("/api/v1/roles/pm")
        assert res_pm.status_code == 200
        pm_data = res_pm.json()
        assert pm_data["name"] == "产品经理 Agent"
        assert "PRD" in pm_data["responsibilities"] or "价值" in pm_data["responsibilities"]

        # 3. Get module details and verify roles are populated
        # Retrieve modules from run
        res_runs = await ac.get("/api/v1/runs?product_id=accounting-sea")
        assert res_runs.status_code == 200
        runs = res_runs.json()
        assert len(runs) > 0
        run_id = runs[0]["id"]
        res_run_detail = await ac.get(f"/api/v1/runs/{run_id}")
        assert res_run_detail.status_code == 200
        modules = res_run_detail.json()["modules"]
        # Check module 05 (方向确认与 MVP PRD)
        m05 = next(m for m in modules if m["module_code"] == "05")
        res_m05 = await ac.get(f"/api/v1/modules/{m05['id']}")
        assert res_m05.status_code == 200
        m05_data = res_m05.json()
        assert m05_data["primary_role"] is not None
        assert m05_data["primary_role"]["role_code"] == "pm"
        collab_codes = [c["role_code"] for c in m05_data["collaborator_roles"]]
        assert "ba" in collab_codes
        assert "eng" in collab_codes



