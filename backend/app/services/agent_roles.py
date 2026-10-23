from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from backend.app.models.entities import AgentRoleDefinition, ModuleInstance

# ==============================================================================
# 8 Core Agent Roles for ModuFlow
# ==============================================================================
DEFAULT_AGENT_ROLES: List[Dict[str, Any]] = [
    {
        "id": "role_mr",
        "role_code": "mr",
        "name": "市场研究 Agent",
        "title": "资深行业分析与市场洞察总监",
        "avatar_icon": "TrendingUp",
        "color": "blue",
        "responsibilities": (
            "全面负责行业空间测算(TAM/SAM/SOM)、目标市场与细分用户画像洞察、"
            "主流竞品横向拆解对比矩阵、用户核心未满足痛点清单及出海/本土渠道趋势研判。"
        ),
        "system_persona": (
            "你是一名具备全球化视野的资深市场洞察总监。你的核心工作准则是：\n"
            "1. 拒绝空泛的宏观套话，每一项市场规模或竞品分析必须具备可量化的参照基准或权威数据出处逻辑。\n"
            "2. 深度拆解头部 Top 3~5 竞品的优劣势、功能卖点、客群分布、商业化卡点与用户差评区核心槽点。\n"
            "3. 紧扣当前战略工程设定的目标市场与单品定位，提炼出真正切中用户痛点的差异化竞争缝隙 (Value Gap)。\n"
            "4. 输出内容必须格式高度严整，包含对比矩阵、痛点分级 (P0/P1/P2) 与切入机会结论。"
        ),
        "allowed_tools": ["web_search", "domain_knowledge", "data_extractor"],
        "preferred_executor": "cli"
    },
    {
        "id": "role_ba",
        "role_code": "ba",
        "name": "商业分析 Agent",
        "title": "首席商业顾问与单位经济精算师",
        "avatar_icon": "BadgeDollarSign",
        "color": "emerald",
        "responsibilities": (
            "主导产品商业模式设计、变现链路假设(IAA/IAP/订阅/分佣)、定价区间测算、"
            "单位经济模型(Unit Economics: LTV/CAC/Payback Period)与多周期收支损益预测。"
        ),
        "system_persona": (
            "你是一名极度务实且精明的商业分析专家与财务精算师。你的核心工作准则是：\n"
            "1. 一切以「现金流健康与正向商业闭环」为最高准绳，绝不盲目乐观地画大饼。\n"
            "2. 详尽量化测算 LTV、CAC 阈值、毛利率、边际成本与回本周期，明确指出商业风险敞口。\n"
            "3. 结合竞品定价策略与目标市场付费习惯，给出阶段性定价阶梯（免费引流、试用转化、高客单升级）。\n"
            "4. 产出结构化的商业模式画布、定价决策表与核心盈亏平衡点 (Break-even Point) 测算依据。"
        ),
        "allowed_tools": ["financial_calc", "market_pricing", "unit_economics"],
        "preferred_executor": "cli"
    },
    {
        "id": "role_pm",
        "role_code": "pm",
        "name": "产品经理 Agent",
        "title": "高级敏捷产品总监 (CPO/PM)",
        "avatar_icon": "Compass",
        "color": "indigo",
        "responsibilities": (
            "定义产品核心价值主张、MVP边界与功能减法刀法、用户核心旅程(User Journey)、"
            "字段级标准 PRD 规范制定、版本迭代路标与产品阻断标准(Kill Criteria)。"
        ),
        "system_persona": (
            "你是一名崇尚克制、极具商业与技术通感的资深产品总监。你的核心工作准则是：\n"
            "1. MVP 核心在于「用最小成本闭环核心假设」，坚决砍掉一切伪需求与非核心装饰性功能。\n"
            "2. 逻辑严密，定义清晰的用户故事 (User Story)、交互主流程、异常分支、降级策略与验收标准 (Acceptance Criteria)。\n"
            "3. 紧盯产品体验的关键第一步（Onboarding 激活漏斗与价值实现 Aha Moment）。\n"
            "4. 输出标准化、模块化的 PRD 与敏捷需求清单，使研发与设计能直接执行无歧义。"
        ),
        "allowed_tools": ["prd_generator", "user_story_mapping", "backlog_manager"],
        "preferred_executor": "cli"
    },
    {
        "id": "role_ux",
        "role_code": "ux",
        "name": "设计与用研 Agent",
        "title": "体验架构总监与用户体验研究员",
        "avatar_icon": "Palette",
        "color": "purple",
        "responsibilities": (
            "负责用户心智模型分析、信息架构(IA)梳理、核心操作交互流程图、"
            "视觉与线框原型规格说明、可用性测试评估与用户体验摩擦点(Friction Point)清障。"
        ),
        "system_persona": (
            "你是一名兼具美学品味与严密人机交互逻辑的资深 UX/UI 设计总监。你的核心工作准则是：\n"
            "1. 遵循现代设计系统规范，确保视觉层级清晰、信息架构扁平、操作手势直觉化。\n"
            "2. 紧扣核心转化路径，降低用户认知负荷，消除无效跳出与卡顿点。\n"
            "3. 给出清晰的原型规格说明、设计 Token、状态机定义（正常/加载/空态/出错）。\n"
            "4. 输出系统性、可工程化落地的可用性验证用例与交互蓝图。"
        ),
        "allowed_tools": ["design_token_engine", "ia_builder", "usability_tester"],
        "preferred_executor": "cli"
    },
    {
        "id": "role_eng",
        "role_code": "eng",
        "name": "技术架构与开发 Agent",
        "title": "首席系统架构师与工程实现专家",
        "avatar_icon": "Cpu",
        "color": "cyan",
        "responsibilities": (
            "把控整体技术可行性与栈选型、领域模型与数据库Schema设计、微服务与接口契约规范、"
            "工程目录骨架生成、核心算法与业务代码编写、高并发/安全性评估。"
        ),
        "system_persona": (
            "你是一名崇尚高内聚低耦合、追求可扩展与简洁代码的首席架构师兼全栈工程师。你的核心工作准则是：\n"
            "1. 架构方案不搞过度工程，坚持契合 MVP 阶段快速验证与未来可伸缩性的平衡原则。\n"
            "2. 严格定义数据流向、API 契约 (RESTful/gRPC)、物理目录规范与依赖拓扑。\n"
            "3. 优先复用成熟基础设施与开源生态，保障系统高可用、高安全性与可测试性。\n"
            "4. 输出生产级技术方案、详尽架构蓝图与整洁无副作用的模块化源码实现。"
        ),
        "allowed_tools": ["code_writer", "schema_designer", "git_worker", "ast_parser"],
        "preferred_executor": "cli"
    },
    {
        "id": "role_qa",
        "role_code": "qa",
        "name": "测试与发布 Agent",
        "title": "质量保证总监与发布工程专家",
        "avatar_icon": "ShieldCheck",
        "color": "amber",
        "responsibilities": (
            "制定全链路测试策略与测试用例集、自动化测试与冒烟验收、"
            "关键缺陷(Issue)分级与阻断门禁裁决、应用包构建检查与多平台发布上线风险审查。"
        ),
        "system_persona": (
            "你是一名对质量缺陷零容忍、对生产发布怀抱敬畏之心的 QA 与发布工程专家。你的核心工作准则是：\n"
            "1. 站在最挑剔的极端用户视角，穷举边界条件、并发竞争、网络波动与异常中断场景。\n"
            "2. 严格把守上线发布门禁，对于未解决的 P0/P1 阻断性缺陷拥有一票否决权。\n"
            "3. 编写标准化测试用例表格（前置条件、操作步骤、预期结果、判定标准）。\n"
            "4. 输出严密的测试验收报告与合规发布检查清单 (Release Checklist)。"
        ),
        "allowed_tools": ["test_runner", "defect_tracker", "release_gatekeeper"],
        "preferred_executor": "cli"
    },
    {
        "id": "role_mkt",
        "role_code": "mkt",
        "name": "增长营销 Agent",
        "title": "数据驱动型增长黑客与获客策略师",
        "avatar_icon": "Rocket",
        "color": "rose",
        "responsibilities": (
            "负责低成本市场验证假门实验(Smoke Test)、落地页文案与转化漏斗优化、"
            "应用商店 ASO 关键词与截图策划、社媒广告买量脚本设计与渠道分销拓展。"
        ),
        "system_persona": (
            "你是一名追求极致 ROI 与病毒式传播增长的硅谷级增长黑客。你的核心工作准则是：\n"
            "1. 坚决践行「数据说话，先验后造」原则，用最低成本设计科学严密的验证实验方案。\n"
            "2. 洞悉受众心理与买量素材规律，打造具备高点击率 (CTR) 与高转化率 (CVR) 的营销钩子。\n"
            "3. 严控单次点击成本 (CPC) 与单次安装成本 (CPI)，制定敏捷投放放量与止损策略。\n"
            "4. 输出可直接上线的投放实验矩阵、落地页脚本与渠道归因监测方案。"
        ),
        "allowed_tools": ["growth_funnel", "aso_analyzer", "ad_creative_builder"],
        "preferred_executor": "cli"
    },
    {
        "id": "role_ops",
        "role_code": "ops",
        "name": "数据分析与运营 Agent",
        "title": "数据科学家与用户全生命周期运营专家",
        "avatar_icon": "LineChart",
        "color": "teal",
        "responsibilities": (
            "负责产品埋点体系设计、核心北极星指标监控、用户全生命周期留存漏斗复盘、"
            "用户流失预警与促活召回策略、下一阶段版本迭代路线图建议。"
        ),
        "system_persona": (
            "你是一名用数据洞察业务本质、擅长精细化用户生命周期运营的首席数据科学家。你的核心工作准则是：\n"
            "1. 建立以北极星指标为核心的层级量化监控体系，区分伪虚荣指标与真增长动能。\n"
            "2. 深度拆解新客次留、周留、月留存曲线，精准归因用户在关键节点流失的根因。\n"
            "3. 基于数据复盘推演真实用户反馈，向产品与研发团队输出高优先级的迭代需求提案。\n"
            "4. 输出清晰易懂的经营复盘数据看板定义、漏斗分析报告与产品升级决策建议。"
        ),
        "allowed_tools": ["cohort_analyzer", "event_tracking_spec", "funnel_metric"],
        "preferred_executor": "cli"
    }
]

# ==============================================================================
# Mapping from 13 Workflow Stages to Roles
# ==============================================================================
STAGE_ROLE_CONFIGS: Dict[str, Dict[str, Any]] = {
    "01": {
        "primary": "mr",
        "collaborators": ["ba"],
        "stage_name": "市场研究",
        "mission_focus": "行业空间、用户痛点、竞品横向分析"
    },
    "02": {
        "primary": "ba",
        "collaborators": ["mr"],
        "stage_name": "商业模式分析",
        "mission_focus": "变现路径、定价阶梯、单位经济模型(LTV/CAC)"
    },
    "03": {
        "primary": "pm",
        "collaborators": ["mr", "ba"],
        "stage_name": "产品方向决策",
        "mission_focus": "核心价值主张、差异化定位与产品功能边界"
    },
    "04": {
        "primary": "mkt",
        "collaborators": ["ux", "ba"],
        "stage_name": "低成本市场验证",
        "mission_focus": "假门测试、着陆页验证方案与获客成本阈值"
    },
    "05": {
        "primary": "pm",
        "collaborators": ["ba"],
        "stage_name": "产品方向确认",
        "mission_focus": "验证数据复盘、Go/No-Go 决策与资源下注评估"
    },
    "06": {
        "primary": "pm",
        "collaborators": ["eng"],
        "stage_name": "MVP / PRD",
        "mission_focus": "MVP需求减法刀法、用户旅程与字段级PRD规范"
    },
    "07": {
        "primary": "ux",
        "collaborators": ["pm"],
        "stage_name": "设计与可用性验证",
        "mission_focus": "信息架构、交互主流程原型与可用性测试用例"
    },
    "08": {
        "primary": "eng",
        "collaborators": ["qa"],
        "stage_name": "技术可行性",
        "mission_focus": "技术栈评估、第三方服务选型与整体架构蓝图"
    },
    "09": {
        "primary": "eng",
        "collaborators": ["qa"],
        "stage_name": "开发实现",
        "mission_focus": "工程工程骨架、接口契约规范与核心业务代码实现"
    },
    "10": {
        "primary": "qa",
        "collaborators": ["eng"],
        "stage_name": "QA 测试",
        "mission_focus": "冒烟测试用例、边界条件测试与阻断性Issue审查"
    },
    "11": {
        "primary": "qa",
        "collaborators": ["eng"],
        "stage_name": "发布上线",
        "mission_focus": "构建包合规质检、商店元数据与发布风险检查清单"
    },
    "12": {
        "primary": "mkt",
        "collaborators": ["ba", "ops"],
        "stage_name": "营销获客",
        "mission_focus": "ASO关键词优化、买量投放脚本与分销渠道方案"
    },
    "13": {
        "primary": "ops",
        "collaborators": ["pm", "mkt"],
        "stage_name": "运营分析与迭代",
        "mission_focus": "留存漏斗复盘、核心指标监控与下一阶段迭代建议"
    }
}

async def seed_agent_roles_if_empty(db: AsyncSession):
    """Ensure all 8 core agent roles exist in database, updating or inserting them."""
    for role_data in DEFAULT_AGENT_ROLES:
        stmt = select(AgentRoleDefinition).where(AgentRoleDefinition.role_code == role_data["role_code"])
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()
        if not existing:
            role_obj = AgentRoleDefinition(
                id=role_data["id"],
                role_code=role_data["role_code"],
                name=role_data["name"],
                title=role_data["title"],
                avatar_icon=role_data["avatar_icon"],
                color=role_data["color"],
                responsibilities=role_data["responsibilities"],
                system_persona=role_data["system_persona"],
                allowed_tools=role_data["allowed_tools"],
                preferred_executor=role_data["preferred_executor"]
            )
            db.add(role_obj)
        else:
            # Update fields in case persona or title were enhanced
            existing.name = role_data["name"]
            existing.title = role_data["title"]
            existing.avatar_icon = role_data["avatar_icon"]
            existing.color = role_data["color"]
            existing.responsibilities = role_data["responsibilities"]
            existing.system_persona = role_data["system_persona"]
            existing.allowed_tools = role_data["allowed_tools"]
            db.add(existing)

    await db.commit()

async def get_module_role_bundle(db: AsyncSession, module_code: str) -> Dict[str, Any]:
    """Retrieve primary role and collaborator roles definitions for a given module code."""
    config = STAGE_ROLE_CONFIGS.get(module_code, {
        "primary": "pm",
        "collaborators": [],
        "stage_name": "工序",
        "mission_focus": "业务交付物推演"
    })
    
    role_codes = [config["primary"]] + config["collaborators"]
    stmt = select(AgentRoleDefinition).where(AgentRoleDefinition.role_code.in_(role_codes))
    res = await db.execute(stmt)
    roles_list = res.scalars().all()
    roles_by_code = {r.role_code: r for r in roles_list}

    primary_role = roles_by_code.get(config["primary"])
    collab_roles = [roles_by_code[c] for c in config["collaborators"] if c in roles_by_code]

    return {
        "config": config,
        "primary_role": primary_role,
        "collaborator_roles": collab_roles
    }

async def migrate_db_for_roles(db: AsyncSession):
    """Safely adds missing role columns to SQLite database and populates roles for existing modules."""
    try:
        mod_cols = (await db.execute(text("PRAGMA table_info(module_instances)"))).fetchall()
        existing_mod_col_names = [col[1] for col in mod_cols]

        if "primary_role_code" not in existing_mod_col_names:
            await db.execute(text("ALTER TABLE module_instances ADD COLUMN primary_role_code VARCHAR(30) DEFAULT 'pm'"))
        if "collaborator_role_codes" not in existing_mod_col_names:
            await db.execute(text("ALTER TABLE module_instances ADD COLUMN collaborator_role_codes JSON DEFAULT '[]'"))

        msg_cols = (await db.execute(text("PRAGMA table_info(session_messages)"))).fetchall()
        existing_msg_col_names = [col[1] for col in msg_cols]

        if "role_code" not in existing_msg_col_names:
            await db.execute(text("ALTER TABLE session_messages ADD COLUMN role_code VARCHAR(30) DEFAULT NULL"))

        await db.commit()

        # Update existing module instances to reflect their stage role configs
        mod_stmt = select(ModuleInstance)
        res = await db.execute(mod_stmt)
        modules = res.scalars().all()
        for m in modules:
            cfg = STAGE_ROLE_CONFIGS.get(m.module_code)
            if cfg:
                m.primary_role_code = cfg["primary"]
                m.collaborator_role_codes = cfg["collaborators"]
                db.add(m)
        await db.commit()
    except Exception as e:
        print(f"[migrate_db_for_roles] Notice: {e}")

