from typing import Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.models.entities import (
    ModuleInstance,
    CollaborationSession,
    SessionMessage,
    Artifact
)
from backend.app.services.workflow_engine import calculate_sha256

MODULE_TEMPLATES_CONTENT = {
    "01": (
        "# 市场研究与竞品分析报告\n\n"
        "## 一、目标市场总览\n"
        "- **市场定位**：东南亚（印尼、越南、泰国）个人财务管理与小微商户记账市场。\n"
        "- **痛点分析**：本土主流应用界面繁杂、对低端 Android 机型卡顿严重、缺少多币种与离线记账支持。\n\n"
        "## 二、竞品对比矩阵\n"
        "| 竞品名称 | 优势 | 劣势 | 机会切入点 |\n"
        "|---|---|---|---|\n"
        "| MoneyForward | 银行直连丰富 | 东南亚本地化差、订阅价格昂贵 | 极简免费离线体验 |\n"
        "| BukuKas | 知名度高 | 侧重 B 端商户，个人记账体验弱 | 兼顾小微与个人的混合账本 |\n\n"
        "## 三、初步结论与建议\n"
        "优先以轻量化、支持弱网秒开、多货币自动转换切入市场。"
    ),
    "06": (
        "# MVP 产品需求文档 (PRD)\n\n"
        "## 1. 业务目标\n"
        "在 3 个月内构建面向东南亚首发版本的轻量记账 App，支持双币种和快速拍照记账。\n\n"
        "## 2. 核心用户故事\n"
        "- **US-01 闪电记账**：打开 App 在 3 秒内完成一笔支出录入。\n"
        "- **US-02 汇率自动转换**：支持印尼盾 (IDR) 与美元 (USD) 实时/离线汇率转换。\n"
        "- **US-03 预算超额预警**：月度分类预算达到 80% 和 100% 时主动推送轻量通知。\n\n"
        "## 3. 非功能性需求与规范\n"
        "- 弱网（3G/边缘网络）下全部核心记账数据本地 SQLite 存储，网络恢复后增量同步。\n"
        "- 数字货币格式：印尼盾金额采用点号作为千分位分隔符 (例如 Rp 1.500.000)。"
    ),
    "07": (
        "# UI/UX 设计与设计规范基线\n\n"
        "## 1. 设计风格与色彩系统\n"
        "- 主品牌色：深翠绿 `#0E8A5A`（契合东南亚金融信任感与生机）。\n"
        "- 背景底色：清爽灰白 `#F8FAFC`，暗黑模式适配良好。\n\n"
        "## 2. 核心交互流程设计\n"
        "- 底部悬浮快捷记账按钮（FAB），支持单手大拇指快速呼出数字键盘。\n"
        "- 报表看板采用扁平色块圆环图，避免繁重 3D 动画以保证低端设备流畅性。"
    ),
    "08": (
        "# 技术架构可行性评估报告\n\n"
        "## 1. 技术栈选型\n"
        "- 客户端：Flutter 3.x 或原生 Kotlin / Swift（优先考虑 Android 原生以最大化低端机性能）。\n"
        "- 后端：FastAPI + PostgreSQL + Redis 缓存。\n"
        "- 本地存储：SQLite (Room / SQLDelight) + 加密安全凭据存储。\n\n"
        "## 2. 风险与规避方案\n"
        "- **风险**：低端机内存溢出 (OOM)。\n"
        "- **规避**：严格限制列表图片解码尺寸，离线图片压缩至 300KB 以下。"
    ),
    "09": (
        "# 开发实现任务清单与代码交付说明\n\n"
        "## 1. 交付模块说明\n"
        "- `auth-service`：支持手机号与 Google 登录认证。\n"
        "- `transaction-core`：核心记账本地 SQLite 读写与离线同步队列。\n"
        "- `currency-engine`：双币种与汇率换算引擎。\n\n"
        "## 2. 代码审查通过指标\n"
        "- 单元测试覆盖率：82%\n"
        "- 静态代码检查 Lint 0 Errors, 0 Warnings。"
    ),
    "10": (
        "# 测试报告与 QA 质量评估\n\n"
        "## 1. 测试用例执行汇总\n"
        "- 执行用例总数：128\n"
        "- 通过用例：125\n"
        "- 失败/异常用例：3（已提交结构化 Bug Issue）\n\n"
        "## 2. 性能与兼容性测试\n"
        "- 测试机型覆盖：Pixel 4a (Android 11), Redmi Note 8, Samsung A12\n"
        "- 弱网测试（300Kbps）：记账成功率 100%，同步延迟 < 1.2s。"
    )
}

async def generate_agent_response(
    db: AsyncSession,
    session: CollaborationSession,
    user_message: SessionMessage
) -> Optional[SessionMessage]:
    """Simulates an intelligent Agent participating in the module session."""
    module_stmt = select(ModuleInstance).where(ModuleInstance.id == session.module_id)
    mod_res = await db.execute(module_stmt)
    module = mod_res.scalar_one_or_none()
    if not module:
        return None

    msg_type = user_message.message_type
    content = user_message.content

    # 1. Human gave an instruction -> Generate draft artifact
    if msg_type == "instruction":
        if module.module_code == "01":
            from backend.app.services.market_research_engine import generate_comprehensive_market_report
            from backend.app.models.entities import WorkflowRun, Product, StrategicInitiative
            run_res = await db.execute(select(WorkflowRun).where(WorkflowRun.id == module.run_id))
            run = run_res.scalar_one_or_none()
            prod_name = "当前产品"
            prod_code = "PRD"
            target_mkt = "目标细分市场"
            strat_intent = ""
            strat_role = "acquisition"
            if run:
                p_res = await db.execute(select(Product).where(Product.id == run.product_id))
                prod = p_res.scalar_one_or_none()
                if prod:
                    prod_name = prod.name
                    prod_code = prod.code
                    strat_role = prod.strategic_role or "acquisition"
                    if prod.initiative_id:
                        i_res = await db.execute(select(StrategicInitiative).where(StrategicInitiative.id == prod.initiative_id))
                        init = i_res.scalar_one_or_none()
                        if init:
                            target_mkt = init.target_market or target_mkt
                            strat_intent = init.strategic_intent or strat_intent

            default_art = generate_comprehensive_market_report(
                product_name=prod_name,
                product_code=prod_code,
                target_market=target_mkt,
                strategic_intent=strat_intent,
                strategic_role=strat_role,
                user_instruction=content
            )
        else:
            default_art = MODULE_TEMPLATES_CONTENT.get(
                module.module_code,
                f"# {module.name} 交付物初稿\n\n基于指令生成：{content}\n\n已完成基础框架搭建与核心要素梳理。"
            )
        
        # Check current max version
        art_stmt = select(Artifact).where(Artifact.module_id == module.id).order_by(Artifact.version.desc())
        art_res = await db.execute(art_stmt)
        existing_artifacts = art_res.scalars().all()
        next_ver = (existing_artifacts[0].version + 1) if existing_artifacts else 1

        artifact = Artifact(
            module_id=module.id,
            title=f"{module.name} 规范文档 v{next_ver}",
            version=next_ver,
            content=default_art,
            content_hash=calculate_sha256(default_art),
            is_baseline=False
        )
        db.add(artifact)
        await db.flush()

        agent_msg = SessionMessage(
            session_id=session.id,
            sender="AI Agent",
            sender_role="agent",
            message_type="draft_artifact",
            content=f"已根据指令完成分析，产出了交付物初稿【{artifact.title}】。请查阅右侧交付物看板，如有调整建议请随时提出。",
            artifact_ref_id=artifact.id
        )
        db.add(agent_msg)
        
        # Advance phase to discussing if draft
        if module.phase == "draft":
            module.phase = "discussing"
            db.add(module)

        await db.commit()
        await db.refresh(agent_msg)

        # 触发物理文件同步
        try:
            from backend.app.services.workspace_sync import sync_run_workspace
            await sync_run_workspace(db, module.run_id)
        except Exception:
            pass

        return agent_msg

    # 2. Human gave feedback -> Revise artifact
    elif msg_type == "feedback":
        # Get latest artifact
        art_stmt = select(Artifact).where(Artifact.module_id == module.id).order_by(Artifact.version.desc()).limit(1)
        art_res = await db.execute(art_stmt)
        latest_art = art_res.scalars().first()
        
        base_content = latest_art.content if latest_art else "# 文档草稿"
        next_ver = (latest_art.version + 1) if latest_art else 1
        
        revised_content = (
            f"{base_content}\n\n"
            f"--- \n"
            f"### 依据反馈修订记录 (v{next_ver})\n"
            f"- **反馈要点**：{content}\n"
            f"- **调整说明**：已对相关段落进行定向补充与结构优化，确保符合上下文业务要求。"
        )

        new_artifact = Artifact(
            module_id=module.id,
            title=f"{module.name} 规范文档 v{next_ver}",
            version=next_ver,
            content=revised_content,
            content_hash=calculate_sha256(revised_content),
            is_baseline=False
        )
        db.add(new_artifact)
        await db.flush()

        agent_msg = SessionMessage(
            session_id=session.id,
            sender="AI Agent",
            sender_role="agent",
            message_type="revised_artifact",
            content=f"收到反馈，已完成修订并生成新版本【{new_artifact.title}】。已同步更新至交付物库，请审阅。",
            artifact_ref_id=new_artifact.id
        )
        db.add(agent_msg)
        await db.commit()
        await db.refresh(agent_msg)

        # 触发物理文件同步
        try:
            from backend.app.services.workspace_sync import sync_run_workspace
            await sync_run_workspace(db, module.run_id)
        except Exception:
            pass

        return agent_msg

    # 3. Human asked a question
    elif msg_type == "question":
        agent_msg = SessionMessage(
            session_id=session.id,
            sender="AI Agent",
            sender_role="agent",
            message_type="question",
            content=f"针对您提出的问题「{content}」：\n\n从当前【{module.name}】的视角来看，建议在不破坏既有架构边界的前提下，通过增加轻量适配层或在下一迭代周期解决。您也可以通过创建 Issue 将该疑问指派给技术或需求评审人员进一步评估。"
        )
        db.add(agent_msg)
        await db.commit()
        await db.refresh(agent_msg)
        return agent_msg

    # 4. Human approved
    elif msg_type == "approve":
        agent_msg = SessionMessage(
            session_id=session.id,
            sender="AI Agent",
            sender_role="agent",
            message_type="approve",
            content="收到审批通过确认。只要当前模块不存在阻断性（Critical/Major）未关闭 Issue，即可执行基线锁定操作以解锁后续下游模块。"
        )
        db.add(agent_msg)
        await db.commit()
        await db.refresh(agent_msg)
        return agent_msg

    return None
