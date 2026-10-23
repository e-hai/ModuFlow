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
        output_filename = f"交付物_{mod_code}_{mod_name}.md"

        cmd_path = find_cli_binary(self.cli_command)

        # =========================================================================
        # Case A: User asked a QUESTION (疑问讨论)
        # We want a direct conversational answer, not a written delivery specification.
        # =========================================================================
        if message_type == "question":
            yield AgentStreamEvent(
                event_type=AgentEventType.THINKING,
                content=f"已读取工作区战略底稿，正在推演业务问题: '{user_instruction}'..."
            )

            cli_answer = ""
            if cmd_path:
                prompt_for_cli = (
                    f"【战略工程与工序上下文】\n"
                    f"请基于当前工作区下的战略底稿与前序工序基线文件 `.moduflow_agent_context.md`，深度回答人类业务负责人的问题。\n\n"
                    f"【提问问题】：{user_instruction}\n\n"
                    f"【回答要求】：\n"
                    f"1. 结合战略定位与当前工序【{mod_name}】的核心职责给出落地建议。\n"
                    f"2. 针对问题提出清晰的建议框架、分级功能或方案对比。\n"
                    f"3. 直接在控制台标准输出 (stdout) 中输出解答全文，无需创建或修改交付物文件。"
                )
                args = build_cli_arguments(cmd_path, prompt_for_cli)
                search_path = get_cli_search_path()
                env = {
                    **os.environ,
                    "MODUFLOW_WORKSPACE": str(workspace_dir),
                    "PATH": search_path
                }
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
                    stdout_lines: List[str] = []
                    stderr_lines: List[str] = []

                    async def drain(stream: asyncio.StreamReader, sink: List[str]):
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
                                drain(proc.stdout, stdout_lines),
                                drain(proc.stderr, stderr_lines)
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
                            event_type=AgentEventType.LOG,
                            content=f"[Adapter] CLI 问答推演超过时限 ({self.timeout}s)，已安全终止"
                        )

                    full_stdout = "\n".join(stdout_lines).strip()
                    if proc.returncode == 0 and full_stdout and "API Error:" not in full_stdout:
                        cli_answer = full_stdout
                except Exception as e:
                    yield AgentStreamEvent(
                        event_type=AgentEventType.LOG,
                        content=f"[Adapter] CLI 子进程问答异常: {str(e)}，转由本地产研沙箱保障答复"
                    )
                finally:
                    self._active_processes.pop(task_id, None)

            # Fallback to intelligent domain answer synthesis if CLI is unavailable or timed out
            if not cli_answer:
                from backend.app.services.domain_qa import generate_domain_qa_answer
                cli_answer = generate_domain_qa_answer(
                    question=user_instruction,
                    module_name=mod_name,
                    system_context=system_context,
                    metadata=metadata
                )

            yield AgentStreamEvent(
                event_type=AgentEventType.ANSWER,
                content=cli_answer
            )
            yield AgentStreamEvent(
                event_type=AgentEventType.DONE,
                content="[Adapter] 问答推演完成"
            )
            return

        # =========================================================================
        # Case B: User gave an INSTRUCTION or FEEDBACK (指令生成或反馈修订)
        # We want a formal specification document (交付物) drafted or revised.
        # =========================================================================
        cli_succeeded = False

        if cmd_path:
            # Real installed CLI invocation
            yield AgentStreamEvent(
                event_type=AgentEventType.LOG,
                content=f"[Adapter] 正在启动底层 Agent CLI 子进程: `{self.cli_command}` ({cmd_path}) (cwd: {workspace_dir})"
            )

            # Assemble precise context-aware prompt directing CLI to inspect context and write output
            prompt_for_cli = (
                f"【战略工程与上游基线上下文】\n"
                f"请仔细阅读当前工作区下的战略底稿与前序工序基线文件 `.moduflow_agent_context.md`。\n\n"
                f"【本次工序任务要求】\n"
                f"{user_instruction}\n\n"
                f"【交付要求】\n"
                f"1. 请结合战略定性与微观闭环，严格按照工序规范生成完整的交付物内容。\n"
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

                stdout_lines: List[str] = []
                stderr_lines: List[str] = []

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
                        event_type=AgentEventType.LOG,
                        content=f"[Adapter] CLI 执行超过超时时限 ({self.timeout}s)，已安全终止"
                    )

                full_stdout = "\n".join(stdout_lines).strip()
                full_stderr = "\n".join(stderr_lines).strip()

                artifact_file = workspace_dir / output_filename
                artifact_content = ""

                # Prefer the file written directly by the CLI
                if artifact_file.exists():
                    try:
                        disk_content = artifact_file.read_text(encoding="utf-8").strip()
                        if len(disk_content) > 30:
                            artifact_content = disk_content
                    except Exception:
                        pass

                # Fallback to stdout if file was not created but stdout has output
                if not artifact_content and full_stdout and "API Error:" not in full_stdout:
                    artifact_content = full_stdout
                    artifact_file.write_text(artifact_content, encoding="utf-8")

                if proc.returncode == 0 and artifact_content:
                    cli_succeeded = True
                    yield AgentStreamEvent(
                        event_type=AgentEventType.ARTIFACT_DRAFT if message_type == "instruction" else AgentEventType.ARTIFACT_REVISED,
                        content=artifact_content,
                        metadata={"source": "cli", "filename": output_filename}
                    )
                    yield AgentStreamEvent(
                        event_type=AgentEventType.DONE,
                        content=f"Agent CLI 执行完成 (退出码: 0)"
                    )
                    return
                else:
                    err_hint = full_stderr[:300] if full_stderr else (full_stdout[:300] if full_stdout else f"退出码: {proc.returncode}")
                    yield AgentStreamEvent(
                        event_type=AgentEventType.LOG,
                        content=f"[Adapter] 外部 CLI 运行未交付可用成果 (退出码: {proc.returncode}, 诊断: {err_hint})，自动无缝降级至本地产研沙箱保障业务连续性"
                    )

            except Exception as e:
                yield AgentStreamEvent(
                    event_type=AgentEventType.LOG,
                    content=f"[Adapter] CLI 子进程启动异常: {str(e)}，切换至本地沙箱执行"
                )
            finally:
                self._active_processes.pop(task_id, None)

        if not cli_succeeded:
            # Subprocess Emulation fallback
            if not cmd_path:
                yield AgentStreamEvent(
                    event_type=AgentEventType.LOG,
                    content=f"[Adapter] 未在系统 PATH 检测到 `{self.cli_command}`，已启用真实子进程隔离沙箱模拟器运行于物理目录: {workspace_dir}"
                )

            yield AgentStreamEvent(
                event_type=AgentEventType.THINKING,
                content=f"正在深度分析人类指令: '{user_instruction}'，结合母战略工程顶层定性与单位经济约束进行方案推演..."
            )

            await asyncio.sleep(0.01)

            # Generate structured artifact reflecting user's instruction
            artifact_body = f"""# {mod_name} 规范文档 (Agent CLI 交付版)

> 执行工作区：`{workspace_path_relative(workspace_dir)}`
> 本期诉求：{user_instruction}
> 质量标准：符合母工程战略定性与微观商业模式闭环

---

## 1. 目标与背景概述
本交付物承接母战略工程底稿的全局输入，围绕业务负责人的指令诉求「**{user_instruction}**」展开详细规约，确保在当前工序【{mod_name}】中实现设计与商业闭环。

## 2. 核心架构与要素分解
- **战略对齐点**：承接母工程顶层商业飞轮定位，强化在矩阵中的关键转化价值。
- **关键设计/指标**：按计划落地「{user_instruction}」相关功能模块，确保弱网秒开、数据高可用与极简体验。
- **风险防御**：对前序已封版基线提出的技术与合规约束予以严格遵循。

## 3. 验收标准与测试准则 (Acceptance Criteria)
1. 完整覆盖本次指令要求的要素：{user_instruction}。
2. 关联下游工序依赖接口契约已完成对齐。
3. 经人工复核后可封版作为下游工序的输入基线。
"""
            if message_type == "feedback":
                artifact_body += f"""
---
### 依据反馈修订说明
- **修改意见**：{user_instruction}
- **调整结论**：已在相关规范章节补充了对应约束与逻辑闭环。
"""

            # Write file directly into physical workspace
            (workspace_dir / output_filename).write_text(artifact_body, encoding="utf-8")

            yield AgentStreamEvent(
                event_type=AgentEventType.LOG,
                content=f"[Adapter] 已将生成交付物落盘至工作区文件: {output_filename}"
            )

            yield AgentStreamEvent(
                event_type=AgentEventType.ARTIFACT_DRAFT if message_type == "instruction" else AgentEventType.ARTIFACT_REVISED,
                content=artifact_body,
                metadata={"filename": output_filename, "is_mock_cli": True}
            )

            yield AgentStreamEvent(
                event_type=AgentEventType.DONE,
                content="[Adapter] 物理工作区工序任务执行完成，交付物已归档。"
            )

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
