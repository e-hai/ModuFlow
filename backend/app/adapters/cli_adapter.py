import os
import re
import json
import time
import shutil
import asyncio
from typing import AsyncIterator, Optional, Dict, Any, List
from pathlib import Path
from backend.app.adapters.base import BaseAgentAdapter, AgentStreamEvent, AgentEventType
from backend.app.core.config import settings
from backend.app.services.security_guard import sanitize_agent_environment
from backend.app.services.stage_memory import deliverable_filename
from backend.app.services.delivery_contract import manifest_instruction
from backend.app.services.workspace_sandbox import (
    os_sandbox_available,
    sandbox_layers,
    take_integrity_snapshot,
    verify_and_restore,
    wrap_command,
)

_live_processes: "Dict[int, asyncio.subprocess.Process]" = {}


async def terminate_live_cli_processes(grace_seconds: float = 3.0) -> int:
    """结束本进程启动的所有 Agent CLI。执行器退出时调用，别把子进程留成孤儿。"""
    procs = [p for p in _live_processes.values() if p.returncode is None]
    for proc in procs:
        try:
            proc.terminate()
        except ProcessLookupError:
            pass
    for proc in procs:
        try:
            await asyncio.wait_for(proc.wait(), timeout=grace_seconds)
        except (asyncio.TimeoutError, ProcessLookupError):
            try:
                proc.kill()
            except ProcessLookupError:
                pass
    _live_processes.clear()
    return len(procs)


def get_cli_search_path() -> str:
    """Construct a comprehensive PATH including common CLI install locations on macOS/Linux."""
    extra_paths = [
        str(Path.home() / ".local" / "bin"),
        "/opt/homebrew/bin",
        "/usr/local/bin",
    ]
    current_path = os.environ.get("PATH", "")
    return os.pathsep.join([p for p in extra_paths if p not in current_path] + [current_path])

async def apply_saved_cli_settings(db) -> None:
    """Copy the settings-page CLI and model onto this process. The runner is a separate process, so it has to read the same row."""
    from sqlalchemy import select
    from backend.app.models.entities import AgentSettingsModel

    row = (await db.execute(
        select(AgentSettingsModel).where(AgentSettingsModel.id == "default")
    )).scalar_one_or_none()
    if row is None:
        return
    settings.AGENT_ADAPTER_TYPE = row.adapter_type
    settings.AGENT_CLI_COMMAND = row.cli_command
    settings.AGENT_CLI_MODEL = row.cli_model or ""
    settings.AGENT_CLI_TIMEOUT = row.timeout


def find_cli_binary(command: str) -> Optional[str]:
    """Find the full executable path of a given CLI command."""
    if not command or command == "simulator":
        return None
    search_path = get_cli_search_path()
    return shutil.which(command, path=search_path)

_MODEL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+-]{0,119}$")
_CLAUDE_MODEL_RE = re.compile(r"\bclaude-(?:opus|sonnet|haiku|fable)-\d+(?:-\d+)?\b")
_MODEL_LIST_CACHE: Dict[str, tuple] = {}
_MODEL_LIST_TTL_SECONDS = 120


def continuation_preamble(has_draft: bool) -> str:
    """Tell the harness whether this stage already has a file to revise."""
    if has_draft:
        return (
            "本目录的 `.moduflow_agent_context.md` 已包含前序基线和本工序当前稿。"
            "直接依据它和下面的清单，在现有交付物上修改。\n"
        )
    return "本目录的 `.moduflow_agent_context.md` 已包含前序基线。直接依据它和下面的清单写交付物。\n"


def deliverable_write_rule(filename: str, has_draft: bool) -> str:
    """Write a new file on the first pass. Later passes revise that file in place."""
    if has_draft:
        return (
            f"3. 在现有文件 `{filename}` 上按未关闭事项修改，没被点名的段落保持原样，写完就结束。"
            "不要把全文再打印到 stdout，不要另起一份新稿。"
        )
    return (
        f"3. 把交付物一次写入当前工作区的 `{filename}`，写完就结束。"
        "不要把全文再打印到 stdout，不要为了核对而重读或改写这个文件。"
    )


def deliverable_length_guideline(mod_code: str) -> str:
    """Keep stage 05 a full PRD. Other stages stay inside their own checklist."""
    if mod_code in {"01", "02", "03", "04"}:
        return "全文控制在 2,000~3,500 字，用高密度表格写完即止。"
    if mod_code == "05":
        return (
            "这是完整 PRD：覆盖业务流程、逐页交互、五维模块卡、业务数据字典、权益状态机、埋点字典与验收标准，"
            "篇幅 6,000~12,000 字，不要缩成几行简表。"
        )
    return "只写本工序清单中的交付项，全文 1,800~3,500 字。不要扩写成 PRD，不要补写清单以外的章节。"


def usable_cli_model(model: Optional[str]) -> Optional[str]:
    """Return a model id safe to pass as a CLI argument, or None to keep the CLI default."""
    if model is None:
        return None
    text = model.strip()
    if not text or not _MODEL_ID_RE.match(text):
        return None
    return text


_QUOTA_RE = re.compile(
    r"quota|resource_exhausted|rate[_ ]limit|insufficient[_\s]quota",
    re.IGNORECASE,
)
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
PROBE_PROMPT = "Reply with the single word ok. Do not create or modify any files."
PROBE_TIMEOUT_SECONDS = 45


def classify_cli_probe(returncode: Optional[int], stdout: str, stderr: str) -> Dict[str, str]:
    """Tell a one-word model probe apart from a quota rejection and other CLI failures."""
    stdout = _ANSI_RE.sub("", stdout or "")
    stderr = _ANSI_RE.sub("", stderr or "")
    blob = "\n".join(part.strip() for part in (stderr, stdout) if part and part.strip())
    failed = returncode not in (0, None)
    quota_hit = bool(_QUOTA_RE.search(blob)) and (failed or "429" in blob or "error" in blob.lower())
    if quota_hit:
        return {"kind": "quota", "detail": _probe_detail(blob)}
    if failed:
        return {"kind": "error", "detail": _probe_detail(blob) or f"退出码 {returncode}"}
    if not stdout.strip() or "API Error:" in stdout:
        return {"kind": "error", "detail": _probe_detail(blob) or "模型没有返回内容"}
    return {"kind": "ok", "detail": stdout.strip()[:120]}


def _probe_detail(blob: str) -> str:
    lines = [ln.strip() for ln in blob.splitlines() if ln.strip()]
    picked = [ln for ln in lines if _QUOTA_RE.search(ln) or ln.lower().startswith("error")]
    return " ".join(picked or lines[:2])[:500]


async def probe_selected_model(
    cmd_path: str,
    model: Optional[str] = None,
    timeout: float = PROBE_TIMEOUT_SECONDS,
) -> Dict[str, str]:
    """Send one short prompt with the selected model so a quota rejection is visible."""
    import tempfile

    args = build_cli_arguments(cmd_path, PROBE_PROMPT, model)
    env = {
        **sanitize_agent_environment(dict(os.environ)),
        "PATH": get_cli_search_path(),
    }
    with tempfile.TemporaryDirectory(prefix="moduflow-probe-") as workspace:
        proc = await asyncio.create_subprocess_exec(
            *args,
            cwd=workspace,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            await proc.wait()
            return {"kind": "timeout", "detail": f"模型在 {int(timeout)} 秒内没有回应，无法确认额度"}
    return classify_cli_probe(
        proc.returncode,
        (stdout or b"").decode(errors="replace"),
        (stderr or b"").decode(errors="replace"),
    )


def build_cli_arguments(cmd_path: str, prompt: str, model: Optional[str] = None) -> List[str]:
    """
    Build non-interactive, permission-bypassing arguments for supported Agent CLIs.
    Supports Claude Code (claude), Google Antigravity (agy), Codex CLI (codex),
    and general custom CLI runners. A selected model is passed with the CLI's own --model flag.
    """
    cmd_name = Path(cmd_path).name.lower()
    chosen = usable_cli_model(model)
    model_flags = ["--model", chosen] if chosen else []
    if "claude" in cmd_name or "agy" in cmd_name:
        return [cmd_path, *model_flags, "-p", prompt, "--dangerously-skip-permissions"]
    elif "codex" in cmd_name:
        # Under sandbox-exec Codex cannot nest its own seatbelt, so it bypasses it; otherwise use its workspace-write sandbox.
        sandbox_flags = (
            ["--dangerously-bypass-approvals-and-sandbox"]
            if os_sandbox_available()
            else ["--sandbox", "workspace-write", "-c", "sandbox_workspace_write.network_access=true"]
        )
        return [
            cmd_path,
            *model_flags,
            "exec",
            "--ephemeral",
            "--skip-git-repo-check",
            *sandbox_flags,
            prompt
        ]
    else:
        return [cmd_path, *model_flags, "-p", prompt]


def parse_agy_model_listing(text: str) -> List[Dict[str, str]]:
    """Parse `agy models` stdout: one `id<TAB>label` row per model."""
    models: List[Dict[str, str]] = []
    seen = set()
    for raw in text.splitlines():
        line = raw.strip()
        if "\t" not in line:
            continue
        model_id, label = line.split("\t", 1)
        model_id = usable_cli_model(model_id)
        label = label.strip()
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        models.append({"id": model_id, "label": label or model_id})
    return models


def parse_codex_model_catalog(text: str) -> List[Dict[str, str]]:
    """Parse `codex debug models` JSON down to slug and display name."""
    start_obj = text.find("{")
    start_list = text.find("[")
    starts = [i for i in (start_obj, start_list) if i >= 0]
    if not starts:
        return []
    try:
        data = json.loads(text[min(starts):])
    except json.JSONDecodeError:
        return []
    rows = data.get("models", []) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return []
    models: List[Dict[str, str]] = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("visibility") not in (None, "list"):
            continue
        model_id = usable_cli_model(str(row.get("slug") or row.get("id") or ""))
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        label = str(row.get("display_name") or row.get("name") or model_id).strip() or model_id
        models.append({"id": model_id, "label": label})
    return models


def parse_claude_model_catalog(text: str) -> List[Dict[str, str]]:
    """Pull built-in Claude model ids out of CLI help or binary strings."""
    aliases = [
        {"id": "fable", "label": "Fable（该系列最新）"},
        {"id": "opus", "label": "Opus（该系列最新）"},
        {"id": "sonnet", "label": "Sonnet（该系列最新）"},
        {"id": "haiku", "label": "Haiku（该系列最新）"},
    ]
    family_rank = {"fable": 0, "opus": 1, "sonnet": 2, "haiku": 3}
    found = []
    seen = set()
    for model_id in _CLAUDE_MODEL_RE.findall(text):
        if model_id in seen:
            continue
        seen.add(model_id)
        family, *version = model_id.removeprefix("claude-").split("-")
        found.append({
            "id": model_id,
            "label": f"Claude {family.capitalize()} {'.'.join(version)}",
            "_rank": (family_rank.get(family, 9), tuple(-int(part) for part in version)),
        })
    found.sort(key=lambda item: item["_rank"])
    for item in found:
        item.pop("_rank", None)
    return aliases + found


async def _read_cli_stdout(args: List[str], timeout: float) -> str:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise TimeoutError(f"读取模型列表超时: {' '.join(args[:2])}")
    return (stdout or b"").decode(errors="replace")


async def list_cli_models(command: str, refresh: bool = False) -> Dict[str, Any]:
    """Ask the installed CLI for the models it can switch to."""
    command = (command or "").strip()
    if not command or any(ch in command for ch in "\n\r;&|`$"):
        return {"command": command, "models": [], "error": "无效的 CLI 命令"}
    cached = _MODEL_LIST_CACHE.get(command)
    if cached and not refresh and time.monotonic() - cached[0] < _MODEL_LIST_TTL_SECONDS:
        return cached[1]

    cmd_path = find_cli_binary(command)
    if not cmd_path:
        result = {"command": command, "models": [], "error": "未在 PATH 中找到该 CLI"}
        return result

    name = Path(cmd_path).name.lower()
    try:
        if "agy" in name:
            text = await _read_cli_stdout([cmd_path, "models"], 20)
            models = parse_agy_model_listing(text)
        elif "codex" in name:
            text = await _read_cli_stdout([cmd_path, "debug", "models"], 15)
            models = parse_codex_model_catalog(text)
        elif "claude" in name:
            help_text = await _read_cli_stdout([cmd_path, "--help"], 8)
            catalog_text = ""
            strings_bin = shutil.which("strings")
            if strings_bin:
                try:
                    catalog_text = await _read_cli_stdout([strings_bin, "-n", "12", cmd_path], 12)
                except Exception:
                    catalog_text = ""
            models = parse_claude_model_catalog(help_text + "\n" + catalog_text)
        else:
            text = await _read_cli_stdout([cmd_path, "models"], 12)
            models = parse_agy_model_listing(text)
    except Exception as exc:
        result = {"command": command, "models": [], "error": str(exc)}
        _MODEL_LIST_CACHE[command] = (time.monotonic(), result)
        return result

    if not models:
        result = {"command": command, "models": [], "error": "该 CLI 没有返回可切换的模型"}
    else:
        result = {"command": command, "models": models, "error": None}
    _MODEL_LIST_CACHE[command] = (time.monotonic(), result)
    return result


def sandbox_violation_event(snapshot, cli_command: str) -> Optional[AgentStreamEvent]:
    violations = verify_and_restore(snapshot)
    if not violations:
        return None
    listed = "\n".join(f"- `{v}`" for v in violations[:10])
    return AgentStreamEvent(
        event_type=AgentEventType.ERROR,
        content=(
            f"❌ 沙箱越权: Agent CLI (`{cli_command}`) 改动了受保护文件，已自动还原，本次交付物作废。\n\n{listed}\n\n"
            "授权包、决策留痕、已挂载 Skill 与 MCP 配置对 Agent 只读。"
        ),
        metadata={"sandbox_violations": violations, "command": cli_command},
    )

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
        output_filename = deliverable_filename(mod_code, mod_name)
        has_stage_draft = bool((metadata or {}).get("has_stage_draft"))

        # Initialize delivery.manifest.json if not present
        from backend.app.services.delivery_contract import CONTRACT_STAGES, MANIFEST_FILENAME, build_stage_manifest
        manifest_file = workspace_dir / MANIFEST_FILENAME
        if mod_code in CONTRACT_STAGES and not manifest_file.exists():
            seed_platform = str((metadata or {}).get("platform") or "cross_platform")
            seed_views = None
            if mod_code == "06":
                from backend.app.services.design_bundle import upstream_prd_views
                seed_views = upstream_prd_views(workspace_dir) or None
            manifest_content = build_stage_manifest(mod_code, output_filename, seed_platform, seed_views)
            if manifest_content:
                manifest_file.write_text(manifest_content, encoding="utf-8")

        # Resolve project profile (platform & client_zero_inference)
        from backend.app.services.profile_guard import is_dual_platform, resolve_project_profile
        init_id = (metadata or {}).get("initiative_id")
        prof = resolve_project_profile(
            initiative_id=init_id,
            product_code=prod_code,
            fallback_platform=(metadata or {}).get("platform", "ios"),
            fallback_zero_inference=(metadata or {}).get("client_zero_inference", True)
        )
        target_platform = prof["platform"]
        target_zero_inf = prof["client_zero_inference"]
        if is_dual_platform(target_platform):
            stage05_platform_guard = "iOS HIG（灵动岛顶部安全区 ≥71pt、触控热区 ≥44pt、Apple 4.3）与 Android Material 3（状态栏/挖孔 ≥24dp、触控热区 ≥48dp、Google Play 政策）都要写进验收"
        elif target_platform == "android":
            stage05_platform_guard = "Android Material 3 规范与 Google Play 政策合规业务护栏（触控热区 ≥48dp）"
        else:
            stage05_platform_guard = "iOS HIG 灵动岛安全区 ≥71pt 与 Apple 4.3 审核合规业务护栏"

        # Ensure exclusive role Skills and MCP config are mounted into workspace_dir
        from backend.app.services.skill_mcp_mounter import mount_role_skills_and_mcp
        from backend.app.services.agent_roles import STAGE_ROLE_CONFIGS
        stage_cfg = STAGE_ROLE_CONFIGS.get(mod_code, {})
        primary_rc = stage_cfg.get("primary", role_code)
        collab_rcs = stage_cfg.get("collaborators", [])
        arsenal_info = mount_role_skills_and_mcp(
            workspace_dir=workspace_dir,
            primary_role_code=primary_rc,
            collaborator_role_codes=collab_rcs,
            platform=target_platform,
            client_zero_inference=target_zero_inf
        )

        yield AgentStreamEvent(
            event_type=AgentEventType.LOG,
            content=f"[Arsenal] 已为角色 `{primary_rc}` 挂载独有 Skill ({', '.join(arsenal_info['mounted_skills'])}) 与专属 MCP ({', '.join(arsenal_info['mounted_mcp_servers'])})",
            metadata=arsenal_info
        )

        yield AgentStreamEvent(
            event_type=AgentEventType.LOG,
            content=f"[Sandbox] 文件系统防护：{sandbox_layers()}；仅允许写入 `{workspace_dir.name}`",
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
        if message_type in ("question", "review"):
            yield AgentStreamEvent(
                event_type=AgentEventType.THINKING,
                content=(
                    f"已读取工作区战略底稿，正在启动 `{self.cli_command}` 以 `{role_code}` 身份做协作评审..."
                    if message_type == "review" else
                    f"已读取工作区战略底稿，正在启动 `{self.cli_command}` 推演业务问题: '{user_instruction}'..."
                )
            )

            prompt_for_cli = (
                f"请先阅读工作区战略底稿与前序基线 `.moduflow_agent_context.md`。\n\n"
                f"{user_instruction}\n\n"
                f"直接在控制台标准输出 (stdout) 中输出评审意见与末尾的 json 结论，不要创建或修改任何文件。"
            ) if message_type == "review" else (
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

            args = build_cli_arguments(cmd_path, prompt_for_cli, settings.AGENT_CLI_MODEL)
            search_path = get_cli_search_path()
            sanitized_env = sanitize_agent_environment(dict(os.environ))
            env = {
                **sanitized_env,
                "MODUFLOW_WORKSPACE": str(workspace_dir),
                "PATH": search_path
            }

            stdout_lines: List[str] = []
            stderr_lines: List[str] = []
            args, _profile = wrap_command(args, workspace_dir)
            snapshot = take_integrity_snapshot(workspace_dir)

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
                _live_processes[proc.pid] = proc

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
                    violation = sandbox_violation_event(snapshot, self.cli_command)
                    if violation:
                        yield violation
                        return
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

                violation = sandbox_violation_event(snapshot, self.cli_command)
                if violation:
                    yield violation
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
                violation = sandbox_violation_event(snapshot, self.cli_command)
                if violation:
                    yield violation
                    return
                yield AgentStreamEvent(
                    event_type=AgentEventType.ERROR,
                    content=f"Agent CLI (`{self.cli_command}`) 子进程启动或执行异常: {str(e)}",
                    metadata={"error": str(e)}
                )
                return
            finally:
                stale = self._active_processes.pop(task_id, None)
                if stale is not None:
                    _live_processes.pop(stale.pid, None)

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
                f"- 【硬性禁区】：严禁通篇罗列全球几千亿 TAM 宏观报告空谈；严禁越界设计具体价格套餐；严禁越界编写产品 PRD 或线框图。\n"
            )
        elif mod_code == "02":
            extra_methodology = (
                f"\n【工序 02（商业模式分析）专项作业红线 —— 变现定价与单位经济精算】\n"
                f"- 1. 承接工序 01 市场输入，聚焦变现阶梯设计：设计免费引流层、24h 通行证、反周卡高质订阅与终身买断的价格锚点；\n"
                f"- 2. 单位经济模型 (UE) 精算：量化测算 LTV、Blended CAC 阈值、毛利防线与回本周期 (Payback Period)；\n"
                f"- 3. 商业护栏与防作弊规则：明确 0 开屏广告保 4.8+ 评分、广告超时免死放行等商业护栏；\n"
                f"- 【硬性禁区】：严禁脱离行业基准编造虚高转化率；严禁越界设计前端弹窗/按钮UI；严禁编写 StoreKit/Stripe 代码实现。\n"
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
                f"\n【工序 04（低成本市场验证）专项作业红线 —— 拒绝纸上谈兵，必须产出可交互 H5 假门网页与立项决策门禁】\n"
                f"- 1. 交付物文档（`{output_filename}`）必须精炼务实，拒绝动辄三万字的学院派空谈！聚焦输出：①承接工序 03 的四大假设验证映射；②2~3 条可直接开拍的 10 秒短视频分镜脚本或 Reddit/社区零成本截流帖文案；③小额测试预算分配（如 $100~$350 / 3~7天）与绿灯/红灯止损阈值。\n"
                f"- 2. 【强制真交付要求】：你必须在当前工作区目录下同步创建并写入一个单文件、零外部依赖、高颜值的移动端可交互 H5 假门测试着陆页 `index.html`！该网页必须包含：首屏核心功能交互模拟器、痛点对比、伪购买/下载抽屉，以及点击后的「早鸟内测坦白与留邮箱锁客弹窗 (Graceful Reveal)」，供业务负责人直接在右侧预览器交互体验或一键部署外测。\n"
                f"- 3. 【立项决策门禁 (Go/Pivot/Kill)】：在文档末尾明确设立立项评估门禁与放行标准。若尚未进行外部真实投放，一律输出待回填立项门禁框架（标明 `[待回填实测值 | 绿灯立项阈值: xxx]`），严禁虚构实测数据；只有当各项假设满足绿灯标准或业务负责人拍板确认后，方可向下游工序 05 移交立项成果。\n"
                f"- 【硬性禁区】：严禁伪造实测数据；假门页面必须是纯前端零依赖单页，严禁编写生产后端与数据库；严禁擅改业务规格。\n"
            )
        elif mod_code == "05":
            extra_methodology = (
                f"\n【工序 05（产品需求定义）专项作业红线 —— 黄金 7+1 章节结构化 + 纯正产品经理业务规格 (PRD) + 严禁工程师技术越界】\n"
                f"- 【工序核心定位】：工序 05 纯粹聚焦「产品需求规格定义与基线演进」，立项决策已在前序工序 04 闭环封版。严禁在工序 05 出现任何工序 04 的“假门测试待回填实测审计表”或“Go/Pivot/Kill 门禁”！\n"
                f"- 【严守 PM 业务本位，严禁工程师技术越界】：工序 05 必须且只能扮演「产品经理」角色，严禁出现任何技术实现代码、SQL 建表 DDL (`CREATE TABLE`)、数据库索引优化、代码级 JSON Schema / TypeScript interface、或底层 SDK/API 实现细节（如 StoreKit 2 监听器、Keychain 加密 API、SQLite 事务与 WAL 锁）！所有数据库表设计、技术选型与代码架构必须严格留给【工序 07 开发实现】。\n"
                f"- 【可读性第一法则（拒绝文字墙，拒绝机械填表）】：\n"
                f"  - 采用多视角渐进式阅读分层：业务负责人 30 秒看透拍板卡与范围矩阵；UI 设计师通过全站视图总表秒懂画板拓扑；开发工程师通过五维业务规格表与数据字典直接理解产品意图；QA 通过结构化 Gherkin 矩阵直接提测；\n"
                f"  - 保持图·文·表有机呼吸感：背景与心智意图采用精炼人话叙述（3~5行内）；页面路由与状态机采用清晰 Mermaid 图；组件清单、交互分支、异常降级与验收用例必须采用紧凑规整的标准表格，杜绝密集流水账！\n"
                f"- 【黄金 7+1 章节完整结构规范（必须严格按此章节编号与标题输出，严禁缩水）】：\n"
                f"  - 第 0 章：文档元信息与版本演进履历（版本号、更新时间、变更类型、变更项对照表、受影响模块）；\n"
                f"  - 第一章：版本定位与范围封版（业务背景、北极星指标、精简 User Stories、In-Scope P0/P1 vs Out-of-Scope Won't 范围封版矩阵表）；\n"
                f"  - 第二章：全局信息架构与全站视图索引（Mermaid 页面路由拓扑图、全站视图索引总表 View Index Table `V-01~V-05` 标明视图形态与安全区、主流程泳道图）；\n"
                f"  - 第三章：功能模块详细规格说明（M1~M6 核心功能全量展开，逐模块必须统一采用五维结构化规格卡：①模块定位与核心意图导言、②界面布局与组件清单表、③交互流转与计算规则表、④边界条件与异常降级表、⑤模块验收点索引）；\n"
                f"  - 第四章：商业化计费与权限业务规则（Mermaid StateDiagram 权益状态机、SKU 定价阶梯映射表、免费 vs 付费特权矩阵、付费门槛触发时机、网络超时或未支付时的用户端友好降级体验规则、防刷与风控业务规则）；\n"
                f"  - 第五章：核心业务数据字典与本地存储业务策略（纯业务视角，严禁代码/SQL/JSON Schema：①核心业务实体清单与业务关系说明、②逐实体业务数据字典表【字段名、业务含义、业务类型、是否必填、取值范围/枚举值、默认值、校验失败提示文案】、③用户数据存储与隐私分级业务策略【离线持久化诉求、敏感隐私保护诉求、缓存自动清理业务诉求与生命周期】）；\n"
                f"  - 第六章：全链路数据埋点规范（`E-01~E-12` 核心事件埋点总表、转化漏斗与留存计算公式）；\n"
                f"  - 第七章：端到端验收用例与体验质量需求（结构化 `AC-01~AC-08` Gherkin 验收矩阵表包含用例ID/场景/Given/When/Then、用户感知级性能要求【如冷启首屏、导出等待感知】、{stage05_platform_guard}）。\n"
            )
        elif mod_code == "06":
            if is_dual_platform(target_platform):
                platform_rules = (
                    "- 双端项目：每张画板同时画 iOS 与 Android 两个设备外框，缺一端不能放行。\n"
                    "- iOS：`data-device=\"ios\"`，`data-safe-top` ≥ 71（灵动岛）、`data-safe-bottom` ≥ 34，可点击元素 `data-hit` ≥ 44x44（pt）。\n"
                    "- Android：`data-device=\"android\"`，`data-safe-top` ≥ 24（状态栏/挖孔，dp），可点击元素 `data-hit` ≥ 48x48（dp）。\n"
                )
            elif target_platform == "android":
                platform_rules = (
                    "- Android 项目：每张画板只画 Android 设备外框 `data-device=\"android\"`，`data-safe-top` ≥ 24（dp），可点击元素 `data-hit` ≥ 48x48（dp）。无需任何 iOS 检查。\n"
                )
            else:
                platform_rules = (
                    "- iOS 项目：每张画板只画 iOS 设备外框 `data-device=\"ios\"`，`data-safe-top` ≥ 71、`data-safe-bottom` ≥ 34，可点击元素 `data-hit` ≥ 44x44（pt）。\n"
                )
            extra_methodology = (
                f"\n【工序 06（设计实现）专项作业红线 —— 交付的是可以直接点开体验的设计稿文件夹，不是文字规范】\n"
                f"- 1. 工作区必须落盘这套设计交付包（文件名固定）：\n"
                f"  - `index.html`：设计工作台（入口）。左侧列出全部画板，顶部切换平台与 Default/Loading/Empty/Error 状态，可开关标注层（高亮安全区与热区），点选画板里的任意元素在右侧查看尺寸、字号、圆角、颜色，并展示色板、字阶与图标库。必须内联收录每张画板的路径 `screens/V-xx.html`。\n"
                f"  - `tokens.json`：设计令牌唯一真理源，必须含 `color`（十六进制）、`typography`、`spacing`、`radius` 四组。\n"
                f"  - `screens/V-xx.html`：工序 05 视图索引里每个视图一张完整高保真视觉稿（真实文案、真实布局、品牌配色，不是线框、不是占位），页面之间可点击跳转（`data-nav-target=\"V-xx\"`），按钮有按下与状态反馈。\n"
                f"  - `assets/icons/*.svg`：图标资源，合法 SVG。\n"
                f"  - `{output_filename}`：设计说明，写拍板摘要卡、Design Tokens 摘要、逐视图四态说明。不要在里面自报安全区数值，校验器直接读画板标注。\n"
                f"- 2. 画板标注约定（校验器逐项读取）：\n"
                f"  - 设备外框元素带 `data-device`、`data-safe-top`、`data-safe-bottom`。\n"
                f"  - 每个可点击元素（button、a[href]、role=button、带 onclick 或 data-nav-target）都带 `data-hit=\"宽x高\"`，声明的是 CSS（min-width/min-height）保证的最小热区。\n"
                f"  - 四态各一个面板：`data-state=\"default|loading|empty|error\"`。\n"
                f"  - 页面里出现的所有颜色必须来自 `tokens.json`，建议在 `:root` 定义 CSS 变量后统一引用。\n"
                f"  - 零外部依赖：不得引用 http(s) 脚本、样式、字体或图片，所有资源本地相对路径。\n"
                f"{platform_rules}"
                f"- 3. `delivery.manifest.json` 的 `design` 块照实填写：platform、entry（index.html）、tokens_path、screens（view_id、path、platforms）、icons。清单和文件一起改。\n"
                f"- 4. 【需求合理性反馈】：发现工序 05 PRD 体验割裂、路径过深或与平台规范冲突，严禁私自绕过，向工序 05 提需求变更单 (CR)。\n"
                f"- 【硬性禁区】：严禁私自增删改业务流程；严禁写生产业务逻辑、网络请求与持久化代码（归属于 eng）；颜色、字阶不得写进工序 05 的 PRD。\n"
            )
        elif mod_code == "07":
            inference_redline = (
                "死守“客户端零推理成本”红线（AI 离线或云端预处理）"
                if target_zero_inf
                else "当前项目 Profile 允许端侧本地模型推理 (client_zero_inference=False)，请权衡端侧计算与能耗优化"
            )
            extra_methodology = (
                f"\n【工序 07（开发实现）专项作业红线 —— 轻量架构选型 + 代码交付与自测】\n"
                f"- 1. 承接工序 05（产品需求定义）与工序 06（设计实现），在开发启动前先用精简章节明确技术栈选型、核心模块划分与接口/存储方案（无需单独拆分长篇架构八股文），随后聚焦代码实现、核心逻辑交付与自测覆盖率报告。\n"
                f"- 2. 物理数据模型与持久化：输出具体表结构建表 DDL、索引规范、ORM 映射与安全存储加密封装；\n"
                f"- 3. 【技术可行性反馈】：如在开发中发现工序 05 PRD 定义的数据 Schema、三方 SDK 限制或性能瓶颈无法落地，严禁粗暴魔改，应通过向工序 05 提需求变更单 (CR) 驱动上游基线修订。\n"
                f"- 【硬性禁区】：严禁私自阉割功能；{inference_redline}；研发自测不等于测试通过，准入严格归属 qa。\n"
            )
        elif mod_code == "08":
            extra_methodology = (
                f"\n【工序 08（测试与 QA）专项作业红线 —— 端到端质量验证与阻断性缺陷门禁】\n"
                f"- 1. 承接工序 05 业务验收矩阵 (AC-01~AC-08 Gherkin) 与工序 07 交付代码，输出端到端用例执行报告；\n"
                f"- 2. 缺陷分级与阻断门禁：严格分级缺陷 (Critical/Major/Minor)，存在未解决的 P0/P1 缺陷系统强制阻断基线定稿；\n"
                f"- 3. 专项质量报告：输出弱网延迟、低端机掉帧、内存泄漏与合规边界测试结论；\n"
                f"- 【硬性禁区】：严禁带病放行（阻断门禁不可绕过）；严禁 QA 越界修改生产业务代码修复 Bug（必须建 Issue 分派 eng 修复）。\n"
            )
        elif mod_code == "09":
            extra_methodology = (
                f"\n【工序 09（发布与上线）专项作业红线 —— 商店提审合规与降级开关门禁】\n"
                f"- 1. 承接工序 08 测试绿灯决议，输出应用商店提审合规审查表（Apple 4.3 查重度、隐私合规声明、敏感权限合规）；\n"
                f"- 2. 提审降级保护预案：确保 Remote Config 降级兜底开关 100% 具备，制定审核期与上线后的灰度放量与回滚方案；\n"
                f"- 【硬性禁区】：未配置 Remote Config 降级开关与隐私协议，严禁提审放行；严禁裸奔发布。\n"
            )
        elif mod_code == "10":
            extra_methodology = (
                f"\n【工序 10（市场推广与获客）专项作业红线 —— 全球 ASO 与买量素材投放】\n"
                f"- 1. 承接工序 09 上线版本、工序 02 定价与工序 05 卖点，输出多语种 ASO 优化词表（英语/西语/日语/德语等）；\n"
                f"- 2. 获客素材与冷启动排期：输出买量短视频脚本分镜、社媒冷启动方案、KOL 推广合作矩阵；\n"
                f"- 3. 渠道获客成本熔断监控：设定各渠道 eCAC 预警线与熔断线，严格按预算投放，ROI 不达标立即熔断。\n"
            )
        elif mod_code == "11":
            extra_methodology = (
                f"\n【工序 11（运营分析与持续迭代）专项作业红线 —— 全生命周期复盘与 V1.1 Backlog】\n"
                f"- 1. 承接工序 05 埋点字典与线上真实运行数据，输出用户留存衰减漏斗（D1/D7/D30 留存曲线）；\n"
                f"- 2. 变现归因与用户反馈聚类：分析各 SKU 转化率与买量素材 ROI，深挖用户差评与吐槽聚类痛点；\n"
                f"- 3. 下一版本 (V1.1) 需求 Backlog 建议书：输出数据驱动的迭代立项书，正式移交给【工序 05 产品经理】发起增量 PRD 评审；\n"
                f"- 【硬性禁区】：严禁越界修改线上代码或基线；严禁把个别用户极端吐槽当作 P0 伪需求；严禁跳过工序 05 直接开工。\n"
            )

        length_guideline = deliverable_length_guideline(mod_code)
        contract_line = manifest_instruction(mod_code, output_filename)
        if contract_line:
            contract_line = f"4. {contract_line}\n"

        prompt_for_cli = (
            f"【当前战略工程与单品上下文】\n"
            f"- 所属战略工程：{init_name}\n"
            f"- 目标单品：{prod_name} ({prod_code})\n"
            f"- 目标市场：{target_mkt}\n"
            f"- 当前工序环节：{mod_name} (编号: {mod_code})\n"
            f"- 当前工作区已挂载独有 Skill：`{', '.join(arsenal_info['mounted_skills'])}` (位于 `.agents/skills/`)\n"
            f"- 当前工作区已挂载专属 MCP：`{', '.join(arsenal_info['mounted_mcp_servers'])}` (位于 `.agents/mcp_config.json`)\n\n"
            f"{continuation_preamble(has_stage_draft)}"
            f"不要阅读本工序目录以外的文件，忽略上级目录的 AGENTS.md。不要先搜索仓库，不要启动与清单无关的技能、MCP 或终端命令。\n\n"
            f"【本次工序任务要求】\n"
            f"{user_instruction}\n"
            f"{extra_methodology}\n"
            f"【双层分层与反冗余交付要求（强制执行）】\n"
            f"1. 第一层（置顶首屏给人类负责人拍板）：文档标题下方第一章必须固定为 `## 负责人 30 秒拍板摘要卡 (Executive Gate)`（控制在 300 字内，含：3条核心量化结论 + 需负责人拍板的 2~3 个开关/选项 + 下游传参锚点）。\n"
            f"2. 第二层（给下游 AI 传参的执行干货）：严禁重复抄写前序工序已定稿的用户画像、竞品常识或价格表（直接写“继承工序 XX 基线”），剔除废话；{length_guideline}\n"
            f"{deliverable_write_rule(output_filename, has_stage_draft)}\n"
            f"{contract_line}"
        )

        args = build_cli_arguments(cmd_path, prompt_for_cli, settings.AGENT_CLI_MODEL)
        search_path = get_cli_search_path()
        sanitized_env = sanitize_agent_environment(dict(os.environ))
        env = {
            **sanitized_env,
            "MODUFLOW_WORKSPACE": str(workspace_dir),
            "PATH": search_path
        }

        stdout_lines = []
        stderr_lines = []
        args, _profile = wrap_command(args, workspace_dir)
        snapshot = take_integrity_snapshot(workspace_dir)

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
            _live_processes[proc.pid] = proc

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
                violation = sandbox_violation_event(snapshot, self.cli_command)
                if violation:
                    yield violation
                    return

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
                        f"1. 交付物应按本工序清单一次写入文件；若仍在反复检索，通常是模型在跑多余的工具回合；\n"
                        f"2. 系统全局超时时限已默认调整为 300 秒（可在右上角设置中灵活配置）；\n"
                        f"3. 如需毫秒级即时测算与无缝演示，亦可在右上角设置中切换为「内置模拟器 (Simulator)」模式。"
                    ),
                    metadata={"command": self.cli_command, "timeout": self.timeout}
                )
                return

            violation = sandbox_violation_event(snapshot, self.cli_command)
            if violation:
                yield violation
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
            violation = sandbox_violation_event(snapshot, self.cli_command)
            if violation:
                yield violation
                return
            yield AgentStreamEvent(
                event_type=AgentEventType.ERROR,
                content=f"Agent CLI (`{self.cli_command}`) 子进程启动或通信异常: {str(e)}",
                metadata={"error": str(e)}
            )
            return
        finally:
            stale = self._active_processes.pop(task_id, None)
            if stale is not None:
                _live_processes.pop(stale.pid, None)

    async def cancel_task(self, task_id: str) -> bool:
        proc = self._active_processes.get(task_id)
        if proc:
            try:
                proc.terminate()
                await asyncio.sleep(0.1)
                if proc.returncode is None:
                    proc.kill()
                self._active_processes.pop(task_id, None)
                _live_processes.pop(proc.pid, None)
                return True
            except Exception:
                return False
        return False

def workspace_path_relative(path: Path) -> str:
    try:
        return str(path.relative_to(settings.WORKSPACE_DIR))
    except Exception:
        return str(path)
