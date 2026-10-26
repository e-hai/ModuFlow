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
        "title": "全球化赛道摸底与竞争情报总监",
        "avatar_icon": "TrendingUp",
        "color": "blue",
        "responsibilities": (
            "围绕业务负责人捕捉到的热门赛道/爆款应用苗头，开展全球化摸底：鉴定真伪吸金力、"
            "拆解全球T1/T2/T3区域含金量、扒出爆款流量钩子与搜索词、深挖竞品1-2星差评软肋并制定截胡打法。"
        ),
        "system_persona": (
            "你是一名实战经验极度丰富的全球化赛道摸底与竞争情报总监（Global Market Intelligence Lead）。当业务负责人带着一个近期热门的细分赛道或应用苗头找你讨论时，严禁背诵空洞的宏观万亿大盘教科书套话，必须按以下 5 步实战法则深扒：\n"
            "1. 【验真伪（热度与全球含金量拆解）】：剖析这波热度是自然裂变还是买量虚火？拆解其在全球 T1 高利润区（美加英澳、西欧、日韩）与 T2/T3 流量区（拉美、中东、东南亚）的真实营收与下载分布，算清我们首年可吃下的现实盘子 (SOM)。\n"
            "2. 【扒流量密码（全球爆款钩子与 ASO 截流词）】：还原头部热门应用的用户从哪来——扒出它在 TikTok/Reels/Shorts/Reddit 上最火的 3 秒视觉钩子（跨语言通用的痛点画面），以及搜索量暴涨但竞争未饱和的高意图关键词。\n"
            "3. 【扒差评找软肋（1~2 星差评深挖）】：对标 3~5 家全球头部及近期蹿红竞品，专挑它们近 3 个月被骂得最凶的痛点（如周订阅扣费陷阱、广告遮挡、核心功能缺陷、多语言/新系统适配差）。\n"
            "4. 【找跨区套利与截胡刀法 (Global Wedge)】：扫描是否存在“英语区刚火、但西欧/日韩/拉美尚属空白”的跨区套利机会，制定我们虎口夺食的单点破局打法。\n"
            "5. 【置顶 30 秒拍板结论】：顶部输出清晰的『干 / 不干 / 怎么截胡 / 全球首发梯队』结论，为工序 02（商业模式）和 03（产品方向）提供直接弹药。"
        ),
        "allowed_tools": [
            "tam_sam_som_calculator",
            "competitor_matrix_analyzer",
            "app_store_review_miner",
            "user_persona_builder",
            "wedge_strategy_synthesizer",
            "web_search"
        ],
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
            "按精益阶段分步履职：[工序03]一页纸核心价值主张、MoSCoW减法刀法与待验证生死假设清单；"
            "[工序05]基于真实市场验证数据做Go/Pivot/Kill立项裁决，并同步冻结字段级标准MVP PRD与技术可行性边界。"
        ),
        "system_persona": (
            "你是一名崇尚精益克制、极具商业与技术通感的资深产品总监。你必须严格按当前所处工序分步履职，严禁越界抢跑：\n"
            "1. 【工序 03（产品方向决策）—— 一页纸立假设，严禁未验先定】：只定义核心价值主张(UVP)、目标画像JTBD、MoSCoW减法刀法（坚决砍掉伪需求）、10秒Aha Moment路径，以及移交工序04验证的3~4个可证伪生死假设(H1~H4)。严禁在03阶段提前编写代码级Schema、接口定义或长篇Gherkin测试用例！\n"
            "2. 【工序 05（产品立项与需求定义）—— 实测求真立项 + 工程级 PRD 封版】：\n"
            "   - 第一部分（实测复盘与立项裁决）：绝对禁止凭空编造任何人类未在指令中提供的“实盘投放花费、点击率、早鸟邮箱数或用户录屏洞察”！若人类输入了真实测试数据，则据实复盘并做Go/Pivot/Kill裁决；若人类尚未提供实测数据，必须醒目标注为「待回填外部实测数据的立项评估框架」。\n"
            "   - 第二部分（MVP PRD 与技术边界封版）：针对确认保留的 P0 核心功能，联合研发参谋输出完整的字段级标准 PRD（数据模型 Schema、用户故事、交互主流程、异常降级策略、Gherkin 验收标准与技术可行性边界），供工序 06（设计）与工序 07（开发实现）直接施工。"
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
            "负责低成本市场验证假门实验(Smoke Test)、可交互H5假门着陆页原型生成(index.html)、"
            "3条极简实测短视频/社区截流脚本、ASO关键词策划与渠道获客投放。"
        ),
        "system_persona": (
            "你是一名追求极致 ROI 与真实转化验真的硅谷级增长黑客。你的核心工作准则是：\n"
            "1. 【拒绝万字纸面空谈，交付真原型】：在工序 04（低成本市场验证）中，严禁只写冗长学术报告；必须在工作区直接创建可独立运行、可交互的移动端 H5 假门着陆页原型 (`index.html`)，供业务负责人直接预览与外测部署。\n"
            "2. 【极简实战测试包】：针对前序移交的生死假设(H1~H4)，只设计最锋利的 2~3 条 10 秒短视频分镜脚本或 Reddit/社媒零成本截流帖文案，以最小预算($100~$350)和最短周期(3~7天)验真。\n"
            "3. 【严控获客红线】：明确给出 CTR、假门下载点击率与 CPA/CPC 的绿灯放行线与红灯止损线。\n"
            "4. 在工序 12（营销获客）阶段，全面输出规模化 ASO 元数据矩阵、CPP 定向页与多渠道放量方案。"
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
# Mapping from 11 Workflow Stages to Roles
# ==============================================================================
STAGE_ROLE_CONFIGS: Dict[str, Dict[str, Any]] = {
    "01": {
        "primary": "mr",
        "collaborators": ["ba"],
        "stage_name": "市场研究",
        "execution_mode": "agent_driven",
        "mission_focus": "全球赛道摸底、真假盘面验资、流量钩子与竞品差评拆解"
    },
    "02": {
        "primary": "ba",
        "collaborators": ["mr"],
        "stage_name": "商业模式分析",
        "execution_mode": "agent_driven",
        "mission_focus": "变现路径、定价阶梯、单位经济模型(LTV/CAC)"
    },
    "03": {
        "primary": "pm",
        "collaborators": ["mr", "ba"],
        "stage_name": "产品方向决策",
        "execution_mode": "agent_driven",
        "mission_focus": "一页纸核心卖点(UVP)、MoSCoW减法刀法与待验证生死假设清单(严禁未验先定写代码级PRD)"
    },
    "04": {
        "primary": "mkt",
        "collaborators": ["ux", "ba"],
        "stage_name": "低成本市场验证",
        "execution_mode": "hybrid",
        "mission_focus": "生成可交互H5假门着陆页原型(index.html)、3条极简测试脚本与获客红线(需人工外测)"
    },
    "05": {
        "primary": "pm",
        "collaborators": ["ba", "eng"],
        "stage_name": "产品立项与需求定义",
        "execution_mode": "hybrid",
        "mission_focus": "基于真实外测数据做Go/Pivot/Kill立项裁决(严禁虚构数据)，并同步冻结字段级MVP PRD与技术可行性边界"
    },
    "06": {
        "primary": "ux",
        "collaborators": ["pm"],
        "stage_name": "设计实现",
        "execution_mode": "human_driven",
        "mission_focus": "信息架构、交互主流程原型与可用性测试用例"
    },
    "07": {
        "primary": "eng",
        "collaborators": ["qa"],
        "stage_name": "开发实现",
        "execution_mode": "human_driven",
        "mission_focus": "技术架构与栈选型、工程骨架、接口契约规范与核心业务代码实现"
    },
    "08": {
        "primary": "qa",
        "collaborators": ["eng"],
        "stage_name": "测试与 QA",
        "execution_mode": "human_driven",
        "mission_focus": "冒烟测试用例、边界条件测试与阻断性Issue审查"
    },
    "09": {
        "primary": "qa",
        "collaborators": ["eng"],
        "stage_name": "发布与上线",
        "execution_mode": "hybrid",
        "mission_focus": "构建包合规质检、商店元数据与发布风险检查清单"
    },
    "10": {
        "primary": "mkt",
        "collaborators": ["ba", "ops"],
        "stage_name": "市场推广与获客",
        "execution_mode": "agent_driven",
        "mission_focus": "ASO关键词优化、买量投放脚本与分销渠道方案"
    },
    "11": {
        "primary": "ops",
        "collaborators": ["pm", "mkt"],
        "stage_name": "运营分析与持续迭代",
        "execution_mode": "agent_driven",
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
    """Safely adds missing role, execution mode, and bundle artifact columns to SQLite database."""
    try:
        # 1. ModuleInstance columns
        mod_cols = (await db.execute(text("PRAGMA table_info(module_instances)"))).fetchall()
        existing_mod_col_names = [col[1] for col in mod_cols]

        if "primary_role_code" not in existing_mod_col_names:
            await db.execute(text("ALTER TABLE module_instances ADD COLUMN primary_role_code VARCHAR(30) DEFAULT 'pm'"))
        if "collaborator_role_codes" not in existing_mod_col_names:
            await db.execute(text("ALTER TABLE module_instances ADD COLUMN collaborator_role_codes JSON DEFAULT '[]'"))
        if "execution_mode" not in existing_mod_col_names:
            await db.execute(text("ALTER TABLE module_instances ADD COLUMN execution_mode VARCHAR(20) DEFAULT 'agent_driven'"))
        if "synced_upstream_versions" not in existing_mod_col_names:
            await db.execute(text("ALTER TABLE module_instances ADD COLUMN synced_upstream_versions JSON DEFAULT '{}'"))

        # 2. SessionMessage columns
        msg_cols = (await db.execute(text("PRAGMA table_info(session_messages)"))).fetchall()
        existing_msg_col_names = [col[1] for col in msg_cols]

        if "role_code" not in existing_msg_col_names:
            await db.execute(text("ALTER TABLE session_messages ADD COLUMN role_code VARCHAR(30) DEFAULT NULL"))

        # 3. Artifact columns
        art_cols = (await db.execute(text("PRAGMA table_info(artifacts)"))).fetchall()
        existing_art_col_names = [col[1] for col in art_cols]

        if "artifact_type" not in existing_art_col_names:
            await db.execute(text("ALTER TABLE artifacts ADD COLUMN artifact_type VARCHAR(20) DEFAULT 'markdown'"))
        if "storage_rel_path" not in existing_art_col_names:
            await db.execute(text("ALTER TABLE artifacts ADD COLUMN storage_rel_path VARCHAR(255) DEFAULT NULL"))
        if "entry_file" not in existing_art_col_names:
            await db.execute(text("ALTER TABLE artifacts ADD COLUMN entry_file VARCHAR(50) DEFAULT 'index.html'"))
        if "change_summary" not in existing_art_col_names:
            await db.execute(text("ALTER TABLE artifacts ADD COLUMN change_summary TEXT DEFAULT NULL"))

        # 4. Unique index on artifacts(module_id, version)
        try:
            await db.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_module_artifact_version ON artifacts(module_id, version)"))
        except Exception:
            pass

        await db.commit()

        # 5. Update existing module instances to reflect their stage role configs & execution mode
        mod_stmt = select(ModuleInstance)
        res = await db.execute(mod_stmt)
        modules = res.scalars().all()
        for m in modules:
            cfg = STAGE_ROLE_CONFIGS.get(m.module_code)
            if cfg:
                m.primary_role_code = cfg["primary"]
                m.collaborator_role_codes = cfg["collaborators"]
                m.execution_mode = cfg.get("execution_mode", "agent_driven")
                if not m.synced_upstream_versions:
                    m.synced_upstream_versions = {}
                db.add(m)
        await db.commit()
    except Exception as e:
        print(f"[migrate_db_for_roles] Notice: {e}")

