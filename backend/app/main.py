from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from backend.app.core.config import settings
from backend.app.core.database import engine, Base, AsyncSessionLocal
from backend.app.api.endpoints import api_router
from backend.app.services.workflow_engine import seed_templates_if_empty, create_workflow_run_from_template
from backend.app.services.workspace_sync import sync_strategic_initiative_workspace
from backend.app.models.entities import StrategicInitiative, Product

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Seed templates & demo initiative
    async with AsyncSessionLocal() as db:
        await seed_templates_if_empty(db)
        
        # Check if demo initiative exists
        stmt = select(StrategicInitiative).where(StrategicInitiative.id == "sea-2026")
        res = await db.execute(stmt)
        demo_init = res.scalar_one_or_none()
        if not demo_init:
            demo_init = StrategicInitiative(
                id="sea-2026",
                name="进军东南亚市场战略工程",
                description="2026 年度核心战略：拓展印尼、越南等东南亚市场的轻量金融记账与支付矩阵。",
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
                marketing_summary={},
                operations_summary={}
            )
            db.add(demo_init)
            await db.flush()

            # Product A: 记账本东南亚版 (快速迭代模板 - 流量获客)
            prod_a = Product(
                id="accounting-sea",
                initiative_id=demo_init.id,
                name="记账本（东南亚版）",
                code="ACC-SEA",
                description="基于现有产品改造的本地化轻量记账工具，重点支持印尼盾、弱网秒开与离线存储。",
                strategic_role="acquisition",
                stage="growth",
                budget_allocated=220000.0,
                actual_spent=118000.0,
                revenue_contribution=85000.0,
                kpi_name="MAU",
                kpi_target=200000.0,
                kpi_actual=186000.0,
                kpi_unit="人",
                key_risk="Meta 渠道 CAC 超标 72%，次月留存需加速向支付闭环转化",
                recommendation="控制高成本广告投放，加码本地达人合作与自然裂变"
            )
            # Product B: QuickPay 东南亚支付 (完整 13 模块模板 - 商业变现)
            prod_b = Product(
                id="quickpay",
                initiative_id=demo_init.id,
                name="QuickPay 聚合支付",
                code="QPAY",
                description="全新探索的东南亚本地商户聚合支付工具，需从商业模式与技术可行性完整验证。",
                strategic_role="monetization",
                stage="building",
                budget_allocated=280000.0,
                actual_spent=97000.0,
                revenue_contribution=265000.0,
                kpi_name="月交易流水 (GMV)",
                kpi_target=5000000.0,
                kpi_actual=3820000.0,
                kpi_unit="元",
                key_risk="印尼 QRIS 聚合支付资质合规审核中，需储备银行备用方案",
                recommendation="追加商户费率补贴，加速清算联调与商户签约"
            )
            db.add_all([prod_a, prod_b])
            await db.commit()

            # Create default run for Product A
            await create_workflow_run_from_template(
                db=db,
                product_id=prod_a.id,
                template_id="fast-iteration",
                run_name="v1.0 东南亚首发迭代"
            )
            # Create default run for Product B
            await create_workflow_run_from_template(
                db=db,
                product_id=prod_b.id,
                template_id="full-product-launch",
                run_name="探索期可行性论证"
            )

        # 始终同步一次工作空间至本地磁盘 data/workspaces
        await sync_strategic_initiative_workspace(db, "sea-2026")
    yield
    # Shutdown
    await engine.dispose()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/health")
async def health_check():
    return {"status": "ok", "app": settings.PROJECT_NAME}
