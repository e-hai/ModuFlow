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
        output_filename = f"交付物_{mod_code}_{mod_name}.md"

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
                    yield AgentStreamEvent(
                        event_type=AgentEventType.ERROR,
                        content=f"Agent CLI (`{self.cli_command}`) 问答推演超时 (超过设定时限 {self.timeout}秒)。底层子进程已终止。建议适当调大超时时间或检查底层模型网络连通性。",
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
                f"\n【市场研究 Agent 专业作业规范】\n"
                f"- 必须采用自下而上 (Bottom-Up) 模型量化测算 TAM/SAM/SOM，给出保守、基准、乐观三套情景；\n"
                f"- 必须包含 Top 5 核心标杆竞品 5 维对比矩阵（定位与规模、变现与定价、获客渠道、App Store 1-2星差评槽点挖掘、致命软肋与切入机会）；\n"
                f"- 必须输出 3 个典型 ICP 目标用户画像（设备、Jobs-To-Be-Done、现有替代方案痛点、付费意愿）；\n"
                f"- 必须提炼价值缝隙 (Value Gap) 与冷启动破局切入点 (Wedge Strategy)；\n"
                f"- 输出内容必须为工序 02（商业模式）与工序 03（产品方向）提供直接事实支撑。\n"
            )

        prompt_for_cli = (
            f"【当前战略工程与单品上下文】\n"
            f"- 所属战略工程：{init_name}\n"
            f"- 目标单品：{prod_name} ({prod_code})\n"
            f"- 目标市场：{target_mkt}\n"
            f"- 当前工序环节：{mod_name} (编号: {mod_code})\n\n"
            f"请仔细阅读当前工作区下的战略底稿与前序工序基线文件 `.moduflow_agent_context.md`。\n\n"
            f"【本次工序任务要求】\n"
            f"{user_instruction}\n"
            f"{extra_methodology}\n"
            f"【交付要求】\n"
            f"1. 请结合战略定性与微观闭环，严格按照工序规范生成「{prod_name}」完整的交付物内容。\n"
            f"2. 请将本次生成的交付物全文完整保存至当前工作区的 `{output_filename}` 文件中。\n"
            f"3. 并在控制台标准输出 (stdout) 中打印出交付物全文内容。"
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
                yield AgentStreamEvent(
                    event_type=AgentEventType.ERROR,
                    content=f"Agent CLI (`{self.cli_command}`) 执行超时 (超过设定时限 {self.timeout}秒)。交付物未能按时生成，子进程已安全终止。",
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
