import os
import shutil
import asyncio
from typing import AsyncIterator, Optional, Dict, Any, List
from pathlib import Path
from backend.app.adapters.base import BaseAgentAdapter, AgentStreamEvent, AgentEventType
from backend.app.core.config import settings

def get_cli_search_path() -> str:
    """Construct a comprehensive PATH including common CLI install locations on macOS/Linux."""
    extra_paths = [
        str(Path.home() / ".local" / "bin"),
        "/opt/homebrew/bin",
        "/usr/local/bin",
    ]
    current_path = os.environ.get("PATH", "")
    return os.pathsep.join([p for p in extra_paths if p not in current_path] + [current_path])

def find_cli_binary(command: str) -> Optional[str]:
    """Find the full executable path of a given CLI command."""
    if not command or command == "simulator":
        return None
    search_path = get_cli_search_path()
    return shutil.which(command, path=search_path)

def build_cli_arguments(cmd_path: str, prompt: str) -> List[str]:
    """
    Build non-interactive, permission-bypassing arguments for supported Agent CLIs.
    Supports Claude Code (claude), Google Antigravity (agy), Codex CLI (codex),
    and general custom CLI runners.
    """
    cmd_name = Path(cmd_path).name.lower()
    if "claude" in cmd_name:
        return [cmd_path, "-p", prompt, "--dangerously-skip-permissions"]
    elif "agy" in cmd_name:
        return [cmd_path, "-p", prompt, "--dangerously-skip-permissions"]
    elif "codex" in cmd_name:
        return [
            cmd_path,
            "exec",
            "--ephemeral",
            "--skip-git-repo-check",
            "--dangerously-bypass-approvals-and-sandbox",
            prompt
        ]
    else:
        return [cmd_path, "-p", prompt]

class CliSubprocessAdapter(BaseAgentAdapter):
    """
    Subprocess-based Agent CLI Adapter.
    Executes an autonomous Agent CLI (e.g. Claude Code, Antigravity agy, Codex CLI, or custom binary)
    in the isolated physical workspace directory of the specific product module.
    When errors occur, explicitly reports failure without fabricating fake answers.
    """

    def __init__(self, cli_command: Optional[str] = None, timeout: Optional[int] = None):
        self.cli_command = cli_command or settings.AGENT_CLI_COMMAND
        self.timeout = timeout or settings.AGENT_CLI_TIMEOUT
        self._active_processes: Dict[str, asyncio.subprocess.Process] = {}

    async def execute_task(
        self,
        task_id: str,
        workspace_dir: Path,
        system_context: str,
        user_instruction: str,
        message_type: str = "instruction",
        metadata: Optional[Dict[str, Any]] = None
    ) -> AsyncIterator[AgentStreamEvent]:
        workspace_dir.mkdir(parents=True, exist_ok=True)

        # 1. Write the assembled strategic context into the workspace
        context_file = workspace_dir / ".moduflow_agent_context.md"
        context_file.write_text(system_context, encoding="utf-8")

        yield AgentStreamEvent(
            event_type=AgentEventType.LOG,
            content=f"[Adapter] 已注入母工程战略底稿与前序基线至物理工作区: {context_file.name}",
            metadata={"workspace": str(workspace_dir)}
        )

        mod_code = (metadata or {}).get("module_code", "01")
        mod_name = (metadata or {}).get("module_name", "工序交付物")
        init_name = (metadata or {}).get("initiative_name") or "当前战略工程"
        prod_name = (metadata or {}).get("product_name") or "当前产品"
        prod_code = (metadata or {}).get("product_code") or ""
        target_mkt = (metadata or {}).get("target_market") or "目标市场"
        strat_intent = (metadata or {}).get("strategic_intent") or ""
        role_code = (metadata or {}).get("role_code") or "pm"
        output_filename = f"交付物_{mod_code}_{mod_name}.md"

        # Ensure exclusive role Skills and MCP config are mounted into workspace_dir
        from backend.app.services.skill_mcp_mounter import mount_role_skills_and_mcp
        from backend.app.services.agent_roles import STAGE_ROLE_CONFIGS
        stage_cfg = STAGE_ROLE_CONFIGS.get(mod_code, {})
        primary_rc = stage_cfg.get("primary", role_code)
        collab_rcs = stage_cfg.get("collaborators", [])
        arsenal_info = mount_role_skills_and_mcp(
            workspace_dir=workspace_dir,
            primary_role_code=primary_rc,
            collaborator_role_codes=collab_rcs
        )

        yield AgentStreamEvent(
            event_type=AgentEventType.LOG,
            content=f"[Arsenal] 已为角色 `{primary_rc}` 挂载独有 Skill ({', '.join(arsenal_info['mounted_skills'])}) 与专属 MCP ({', '.join(arsenal_info['mounted_mcp_servers'])})",
            metadata=arsenal_info
        )

        cmd_path = find_cli_binary(self.cli_command)
        if not cmd_path:
            yield AgentStreamEvent(
                event_type=AgentEventType.ERROR,
                content=f"系统 PATH 中未找到命令行工具 `{self.cli_command}`。请确认已正确安装该 CLI 并配置在 PATH 中，或在右上角设置中切换为已安装的 Agent。",
                metadata={"command": self.cli_command}
            )
            return

        # =========================================================================
        # Case A: User asked a QUESTION (疑问讨论)
        # =========================================================================
        if message_type == "question":
            yield AgentStreamEvent(
                event_type=AgentEventType.THINKING,
                content=f"已读取工作区战略底稿，正在启动 `{self.cli_command}` 推演业务问题: '{user_instruction}'..."
            )

            prompt_for_cli = (
                f"【当前战略工程与单品上下文】\n"
                f"- 所属战略工程：{init_name}\n"
                f"- 目标单品：{prod_name} ({prod_code})\n"
                f"- 目标市场：{target_mkt}\n"
                f"- 战略定位：{strat_intent}\n"
                f"- 当前工序环节：{mod_name} (编号: {mod_code})\n\n"
                f"请结合工作区战略底稿 `.moduflow_agent_context.md`，深度回答人类业务负责人的问题。\n\n"
                f"【提问问题】：{user_instruction}\n\n"
                f"【回答要求】：\n"
                f"1. 严格紧扣「{prod_name}」在「{target_mkt}」的定位与工序【{mod_name}】的核心目标，给出极其专业、详尽、务实且结构化的解答（如竞品横向对比分析矩阵、核心功能分级清单、定价策略建议等）。\n"
                f"2. 直接在控制台标准输出 (stdout) 中输出解答全文，无需创建或修改交付物文件。"
            )

            args = build_cli_arguments(cmd_path, prompt_for_cli)
            search_path = get_cli_search_path()
            env = {
                **os.environ,
                "MODUFLOW_WORKSPACE": str(workspace_dir),
                "PATH": search_path
            }

            stdout_lines: List[str] = []
            stderr_lines: List[str] = []

            try:
                proc = await asyncio.create_subprocess_exec(
                    *args,
                    cwd=str(workspace_dir),
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env
                )
                self._active_processes[task_id] = proc

                async def drain_stream(stream: asyncio.StreamReader, sink: List[str]):
                    while True:
                        line = await stream.readline()
                        if not line:
                            break
                        decoded = line.decode("utf-8", errors="replace").rstrip()
                        if decoded:
                            sink.append(decoded)

                try:
                    await asyncio.wait_for(
                        asyncio.gather(
                            drain_stream(proc.stdout, stdout_lines),
                            drain_stream(proc.stderr, stderr_lines)
                        ),
                        timeout=self.timeout
                    )
                    await proc.wait()
                except asyncio.TimeoutError:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    # Check if there is already partial stdout before timeout
                    partial_stdout = "\n".join(stdout_lines).strip()
                    if partial_stdout and len(partial_stdout) > 50 and "API Error:" not in partial_stdout:
                        yield AgentStreamEvent(
                            event_type=AgentEventType.ANSWER,
                            content=partial_stdout
                        )
                        yield AgentStreamEvent(
                            event_type=AgentEventType.DONE,
                            content="[Adapter] 问答推演完成 (超时截断前已输出内容)"
                        )
                        return

                    yield AgentStreamEvent(
                        event_type=AgentEventType.ERROR,
                        content=(
                            f"Agent CLI (`{self.cli_command}`) 问答推演超时 (已耗时 {self.timeout}秒)。底层子进程已终止。\n\n"
                            f"【优化排查建议】：\n"
                            f"1. 真实 Agent CLI (如 agy / claude) 在执行自下而上空间测算或竞品 5 维解剖时，需要充分的多步推理与检索时间 (通常为 120~240秒)；\n"
                            f"2. 系统全局超时时限已默认调整为 300 秒（可在右上角设置中灵活配置）；\n"
                            f"3. 如需毫秒级即时测算与无缝演示，亦可在右上角设置中切换为「内置模拟器 (Simulator)」模式。"
                        ),
                        metadata={"command": self.cli_command, "timeout": self.timeout}
                    )
                    return

                full_stdout = "\n".join(stdout_lines).strip()
                full_stderr = "\n".join(stderr_lines).strip()

                if proc.returncode != 0:
                    err_msg = full_stderr or full_stdout or f"进程异常退出 (退出码: {proc.returncode})"
                    yield AgentStreamEvent(
                        event_type=AgentEventType.ERROR,
                        content=f"Agent CLI (`{self.cli_command}`) 执行出错 (退出码: {proc.returncode})：\n\n```\n{err_msg[:1200]}\n```",
                        metadata={"command": self.cli_command, "exit_code": proc.returncode}
                    )
                    return

                if not full_stdout or "API Error:" in full_stdout:
                    yield AgentStreamEvent(
                        event_type=AgentEventType.ERROR,
                        content=f"Agent CLI (`{self.cli_command}`) 退出码为 0，但未在控制台输出有效解答内容。",
                        metadata={"command": self.cli_command}
                    )
                    return

                yield AgentStreamEvent(
                    event_type=AgentEventType.ANSWER,
                    content=full_stdout
                )
                yield AgentStreamEvent(
                    event_type=AgentEventType.DONE,
                    content="[Adapter] 问答推演完成"
                )
                return

            except Exception as e:
                yield AgentStreamEvent(
                    event_type=AgentEventType.ERROR,
                    content=f"Agent CLI (`{self.cli_command}`) 子进程启动或执行异常: {str(e)}",
                    metadata={"error": str(e)}
                )
                return
            finally:
                self._active_processes.pop(task_id, None)

        # =========================================================================
        # Case B: User gave an INSTRUCTION or FEEDBACK (指令生成或反馈修订)
        # =========================================================================
        yield AgentStreamEvent(
            event_type=AgentEventType.LOG,
            content=f"[Adapter] 正在启动底层 Agent CLI 子进程: `{self.cli_command}` ({cmd_path}) (cwd: {workspace_dir})"
        )

        extra_methodology = ""
        if mod_code == "01":
            extra_methodology = (
                f"\n【工序 01（市场研究）专项作业红线 —— 全球赛道摸底与截胡实战】\n"
                f"- 1. 验真伪与全球含金量拆解：剖析该赛道/热门应用是自然裂变真风口还是买量虚火，拆解全球 T1 高利润区（美加英澳、西欧、日韩）与 T2/T3 流量区的真实营收潜能，采用自下而上模型算清首年可拿下的现实盘子 (SOM)；\n"
                f"- 2. 扒全球流量密码：拆解头部爆款在 TikTok/Reels/Shorts/Reddit 上最吸量的 3 秒跨文化视觉钩子 (Visual Hook) 与高意图低竞争 ASO 搜索词；\n"
                f"- 3. 扒 1-2 星差评找软肋：对标 3~5 家全球头部或近期蹿红竞品，深挖其被骂得最凶的痛点（如周卡扣费陷阱、核心功能缺陷、本地化缺失）；\n"
                f"- 4. 全球跨区套利与截胡打法 (Global Wedge)：给出『干/不干/怎么改单点去截胡/全球首发与扩量区域梯队』的明确建议，支撑工序 02 与 03。\n"
            )
        elif mod_code == "03":
            extra_methodology = (
                f"\n【工序 03（产品方向决策）专项作业红线 —— 严禁未验先定】\n"
                f"- 本工序定位为「一页纸精益方向决策与假设提炼」，绝不是工程级详细 PRD！\n"
                f"- 必须聚焦输出：①产品核心价值主张 (UVP) 与一句话定位；②目标画像痛点与价值映射；③MoSCoW 功能减法矩阵（明确 P0 必做与坚决砍除的伪需求 Non-Goals）；④10秒 Aha Moment 激活路径；⑤向工序 04（低成本市场验证）正式移交的 3~4 个可被真实流量证伪的生死假设清单（H1~H4，含通过阈值与熔断线）。\n"
                f"- 【硬性禁令】：严禁在本工序提前编写代码级数据结构 (Schema)、TypeScript/JSON 接口字段、伪代码或长篇 Gherkin (Given/When/Then) 验收用例（这些工程细节必须留到工序 05 经过市场验证后再写）！\n"
                f"- 【工序编号对齐】：向下游穿透指令必须严格指向真实的「工序 04：低成本市场验证 (Smoke Test)」，严禁错标为 UI 或架构设计。\n"
            )
        elif mod_code == "04":
            extra_methodology = (
                f"\n【工序 04（低成本市场验证）专项作业红线 —— 拒绝纸上谈兵，必须产出可交互 H5 假门网页】\n"
                f"- 1. 交付物文档（`{output_filename}`）必须精炼务实，拒绝动辄三万字的学院派空谈！聚焦输出：①承接工序 03 的四大假设验证映射；②2~3 条可直接开拍的 10 秒短视频分镜脚本或 Reddit/社区零成本截流帖文案；③小额测试预算分配（如 $100~$350 / 3~7天）与绿灯/红灯止损阈值。\n"
                f"- 2. 【强制真交付要求】：你必须在当前工作区目录下同步创建并写入一个单文件、零外部依赖、高颜值的移动端可交互 H5 假门测试着陆页 `index.html`！该网页必须包含：首屏核心功能交互模拟器、痛点对比、伪购买/下载抽屉，以及点击后的「早鸟内测坦白与留邮箱锁客弹窗 (Graceful Reveal)」，供业务负责人直接在右侧预览器交互体验或一键部署外测。\n"
            )
        elif mod_code == "05":
            extra_methodology = (
                f"\n【工序 05（产品立项与需求定义）专项作业红线 —— 严禁虚构实测数据 + 输出完整工程级 PRD 需求规格说明书】\n"
                f"- 【反幻觉最高铁律】：绝对禁止凭空捏造任何未在人类【本次工序任务要求】中明确提供的“实盘投放花费、访客数(UV)、点击率(CTR)、收集到的早鸟邮箱数量、卡方检验 p 值或 PostHog 录屏分析结论”！\n"
                f"- 1. 产品立项确认（实测复盘，占篇幅 10%）：\n"
                f"  - 若人类在指令中明确粘贴了真实的外部测试数据：严格依据真实数据对 H1~H4 假设逐一复盘，做出客观的 Go（立项）/ Pivot（微调转型）/ Kill（熔断终止）决议。\n"
                f"  - 若人类未提供具体实测数据：必须在报告正文的显著开头输出「外部实测数据未录入声明：当前尚未收到工序 04 的真实外测投放数据，以下为待回填立项评估框架与完整 MVP PRD 基线」，所有实测数据列必须填写为 `[待回填实测值 | 目标基准: xxx]`，绝不伪造“已测完”的假象！\n"
                f"- 2. 完整工程级 PRD 需求规格说明书（占篇幅 90%，严禁缩水为简表！必须供工序 06 UI 设计与工序 07 研发直接照单施工）：\n"
                f"  - 章节一：立项评估与 MVP 范围封版（In-Scope P0/P1 模块清单 vs Out-of-Scope 明确不做边界）；\n"
                f"  - 章节二：全局信息架构 (IA) 与核心状态流转图（含 Mermaid 页面路由拓扑图与核心用户转化/变现状态机）；\n"
                f"  - 章节三：逐模块、逐页面详细功能需求规格（M1~M6 全量展开：包含页面布局区域、UI 元素说明、手势与参数阈值公式、主流程交互、空状态/加载态/报错降级态）；\n"
                f"  - 章节四：完整数据字典与云端/本地接口契约（完整 JSON Schema、SQLite 本地存储表结构、Keychain 持久化字段、CDN 路径规范与 Remote Config 下发契约）；\n"
                f"  - 章节五：商业化计费与权限状态机（免费额度扣减、`24h Ad-Pass` 激励视频进度与跨天过期逻辑、StoreKit 2 订阅/买断/恢复购买 Restore 与早鸟码兑换状态机）；\n"
                f"  - 章节六：全链路数据埋点字典（Tracking Plan：核心事件名、触发时机、必传属性字段与北极星漏斗归因公式，支撑工序 07 埋点与工序 11 运营分析）；\n"
                f"  - 章节七：非功能性需求与全量 Gherkin 验收标准（AC-01 ~ AC-08+ Given/When/Then 完整用例、性能指标、灵动岛安全区 ≥ 71pt 规范、离线弱网与 Apple 4.3 审核合规红线）。\n"
            )
        elif mod_code == "07":
            extra_methodology = (
                f"\n【工序 07（开发实现）专项作业红线 —— 轻量架构选型 + 代码交付与自测】\n"
                f"- 承接工序 05（产品立项与需求定义）与工序 06（设计实现），在开发启动前先用精简章节明确技术栈选型、核心模块划分与接口/存储方案（无需单独拆分长篇架构八股文），随后聚焦代码实现、核心逻辑交付与自测覆盖率报告。\n"
            )

        length_guideline = (
            "工序 01~04（立项前精益探索期）全文总篇幅控制在 2,000~3,500 字高密度表格内。"
            if mod_code in ("01", "02", "03", "04")
            else "工序 05（完整工程级 PRD）及后续工程工序必须完整输出全部技术规格、逐页面交互细节、Schema、状态机、埋点字典与全量验收标准，严禁将功能模块缩水为几行简表（完整 PRD 篇幅通常为 6,000~12,000 字）。"
        )

        prompt_for_cli = (
            f"【当前战略工程与单品上下文】\n"
            f"- 所属战略工程：{init_name}\n"
            f"- 目标单品：{prod_name} ({prod_code})\n"
            f"- 目标市场：{target_mkt}\n"
            f"- 当前工序环节：{mod_name} (编号: {mod_code})\n"
            f"- 当前工作区已挂载独有 Skill：`{', '.join(arsenal_info['mounted_skills'])}` (位于 `.agents/skills/`)\n"
            f"- 当前工作区已挂载专属 MCP：`{', '.join(arsenal_info['mounted_mcp_servers'])}` (位于 `.agents/mcp_config.json`)\n\n"
            f"请仔细阅读当前工作区下的战略底稿与前序工序基线文件 `.moduflow_agent_context.md`，并优先激活工作区 `.agents/skills/` 下的专属技能与 MCP 工具辅助推演。\n\n"
            f"【本次工序任务要求】\n"
            f"{user_instruction}\n"
            f"{extra_methodology}\n"
            f"【双层分层与反冗余交付要求（强制执行）】\n"
            f"1. 第一层（置顶首屏给人类负责人拍板）：文档标题下方第一章必须固定为 `## 负责人 30 秒拍板摘要卡 (Executive Gate)`（控制在 300 字内，含：3条核心量化结论 + 需负责人拍板的 2~3 个开关/选项 + 下游传参锚点）。\n"
            f"2. 第二层（给下游 AI 传参的执行干货）：严禁重复抄写前序工序已定稿的用户画像、竞品常识或价格表（直接写“继承工序 XX 基线”），剔除废话；{length_guideline}\n"
            f"3. 请将本次生成的交付物全文完整保存至当前工作区的 `{output_filename}` 文件中，并在控制台标准输出 (stdout) 中打印出交付物全文内容。"
        )

        args = build_cli_arguments(cmd_path, prompt_for_cli)
        search_path = get_cli_search_path()
        env = {
            **os.environ,
            "MODUFLOW_WORKSPACE": str(workspace_dir),
            "PATH": search_path
        }

        stdout_lines = []
        stderr_lines = []

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                cwd=str(workspace_dir),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            self._active_processes[task_id] = proc

            async def drain_stream(stream: asyncio.StreamReader, sink: List[str]):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    decoded = line.decode("utf-8", errors="replace").rstrip()
                    if decoded:
                        sink.append(decoded)

            try:
                await asyncio.wait_for(
                    asyncio.gather(
                        drain_stream(proc.stdout, stdout_lines),
                        drain_stream(proc.stderr, stderr_lines)
                    ),
                    timeout=self.timeout
                )
                await proc.wait()
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except Exception:
                    pass

                # Graceful recovery: Check if artifact file was already written to disk before timeout
                artifact_file = workspace_dir / output_filename
                if artifact_file.exists():
                    try:
                        disk_content = artifact_file.read_text(encoding="utf-8").strip()
                        if len(disk_content) > 50:
                            yield AgentStreamEvent(
                                event_type=AgentEventType.ARTIFACT_DRAFT if message_type == "instruction" else AgentEventType.ARTIFACT_REVISED,
                                content=disk_content,
                                metadata={"source": "cli", "filename": output_filename, "recovered_from_workspace": True}
                            )
                            yield AgentStreamEvent(
                                event_type=AgentEventType.DONE,
                                content="[Adapter] 工序交付物已在物理工作区成功落盘保存"
                            )
                            return
                    except Exception:
                        pass

                yield AgentStreamEvent(
                    event_type=AgentEventType.ERROR,
                    content=(
                        f"Agent CLI (`{self.cli_command}`) 执行超时 (已耗时 {self.timeout}秒)。交付物未能按时生成，子进程已安全终止。\n\n"
                        f"【优化排查建议】：\n"
                        f"1. 交付物全量生成涉及多工序约束与万字级文档编排，通常需要 150~240 秒思考与检索；\n"
                        f"2. 系统全局超时时限已默认调整为 300 秒（可在右上角设置中灵活配置）；\n"
                        f"3. 如需毫秒级即时测算与无缝演示，亦可在右上角设置中切换为「内置模拟器 (Simulator)」模式。"
                    ),
                    metadata={"command": self.cli_command, "timeout": self.timeout}
                )
                return

            full_stdout = "\n".join(stdout_lines).strip()
            full_stderr = "\n".join(stderr_lines).strip()

            if proc.returncode != 0:
                err_hint = full_stderr or full_stdout or f"进程异常退出 (退出码: {proc.returncode})"
                yield AgentStreamEvent(
                    event_type=AgentEventType.ERROR,
                    content=f"Agent CLI (`{self.cli_command}`) 执行出错 (退出码: {proc.returncode})，交付物未能生成：\n\n```\n{err_hint[:1200]}\n```",
                    metadata={"command": self.cli_command, "exit_code": proc.returncode}
                )
                return

            artifact_file = workspace_dir / output_filename
            artifact_content = ""

            # 1. Prefer file created on disk
            if artifact_file.exists():
                try:
                    disk_content = artifact_file.read_text(encoding="utf-8").strip()
                    if len(disk_content) > 30:
                        artifact_content = disk_content
                except Exception:
                    pass

            # 2. Fallback to stdout
            if not artifact_content and full_stdout and "API Error:" not in full_stdout:
                artifact_content = full_stdout
                artifact_file.write_text(artifact_content, encoding="utf-8")

            if not artifact_content:
                yield AgentStreamEvent(
                    event_type=AgentEventType.ERROR,
                    content=f"Agent CLI (`{self.cli_command}`) 退出码为 0，但未生成目标规范文件 `{output_filename}` 且无有效内容输出。",
                    metadata={"command": self.cli_command}
                )
                return

            yield AgentStreamEvent(
                event_type=AgentEventType.ARTIFACT_DRAFT if message_type == "instruction" else AgentEventType.ARTIFACT_REVISED,
                content=artifact_content,
                metadata={"source": "cli", "filename": output_filename}
            )
            yield AgentStreamEvent(
                event_type=AgentEventType.DONE,
                content="[Adapter] 工序交付物已成功落盘生成"
            )
            return

        except Exception as e:
            yield AgentStreamEvent(
                event_type=AgentEventType.ERROR,
                content=f"Agent CLI (`{self.cli_command}`) 子进程启动或通信异常: {str(e)}",
                metadata={"error": str(e)}
            )
            return
        finally:
            self._active_processes.pop(task_id, None)

    async def cancel_task(self, task_id: str) -> bool:
        proc = self._active_processes.get(task_id)
        if proc:
            try:
                proc.terminate()
                await asyncio.sleep(0.1)
                if proc.returncode is None:
                    proc.kill()
                self._active_processes.pop(task_id, None)
                return True
            except Exception:
                return False
        return False

def workspace_path_relative(path: Path) -> str:
    try:
        return str(path.relative_to(settings.WORKSPACE_DIR))
    except Exception:
        return str(path)
