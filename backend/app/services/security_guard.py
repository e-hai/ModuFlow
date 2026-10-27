"""
ModuFlow Security Guard & Read-Only Protection Service
(backend/app/services/security_guard.py)

Enforces:
1. Physical OS-level read-only protection (`0o444`) on authorization.yaml and platform standards.
2. Application-level write interception: strictly blocks any Agent attempting to write or tamper with protected files.
3. Credential isolation & sanitization: strictly strips store credentials, live payment keys, and prod DB secrets from Agent environments.
4. Single source of pricing truth: only 'ba' (or human) can define or modify pricing. All others must route through CR.
5. Security violation audit logging in decisions/ and critical 🔴 ExecutiveRisk alerts.
"""

import os
import stat
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.config import settings
from backend.app.models.entities import ExecutiveRisk, Product


PROTECTED_FILE_NAMES = [
    "authorization.yaml",
    "authorization.json",
    "AGENTS.md",
    "agent_roles.py",
]

PROTECTED_DIR_PATTERNS = [
    "/platform/",
    "/decisions/",
    "/.agents/skills/",
]

FORBIDDEN_CREDENTIAL_PATTERNS = [
    "APPLE_ID",
    "APPLE_APP_SPECIFIC_PASSWORD",
    "FASTLANE_PASSWORD",
    "APP_STORE_CONNECT_API_KEY",
    "GOOGLE_PLAY_JSON_KEY",
    "PLAY_CONSOLE_PRIVATE_KEY",
    "STRIPE_SECRET_KEY",
    "STRIPE_LIVE_KEY",
    "PAYMENT_GATEWAY_LIVE_SECRET",
    "DATABASE_URL",
    "PROD_DB_PASSWORD",
    "DATABASE_PASSWORD",
    "MODUFLOW_PROD_SECRET"
]


def parse_actor_identity(actor_header: Optional[str]) -> Tuple[str, str, str]:
    """
    Parses 'X-ModuFlow-Actor' header.
    Returns:
        (actor_type, role_code, actor_name)
    Examples:
        'human:alice' -> ('human', 'human', 'human:alice')
        'agent:ba'    -> ('agent', 'ba', 'agent:ba')
        'agent:lead'  -> ('agent', 'lead', 'agent:lead')
        'agent:pm'    -> ('agent', 'pm', 'agent:pm')
        'lead'        -> ('agent', 'lead', 'agent:lead')
        'ba'          -> ('agent', 'ba', 'agent:ba')
        'human'       -> ('human', 'human', 'human:default')
    """
    if not actor_header:
        return "human", "human", "human:default"

    raw = actor_header.strip()
    if ":" in raw:
        prefix, rest = raw.split(":", 1)
        if prefix.lower() in ["human", "user"]:
            return "human", "human", raw
        elif prefix.lower() in ["agent", "bot", "ai"]:
            return "agent", rest.lower(), raw
        else:
            return "agent", prefix.lower(), raw
    else:
        low = raw.lower()
        if "human" in low:
            return "human", "human", f"human:{raw}"
        else:
            return "agent", low, f"agent:{raw}"


def apply_readonly_file_protection(file_path: Path):
    """Sets a file to read-only (0o444: r--r--r--)."""
    if file_path.exists():
        os.chmod(file_path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)


def apply_write_file_permission(file_path: Path):
    """Temporarily enables write permission for human modification (0o644: rw-r--r--)."""
    if file_path.exists():
        os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)


def is_protected_path(path: Path | str) -> bool:
    """Checks whether a target path is under system-protected read-only coverage."""
    p_str = str(path).replace("\\", "/")
    p_name = Path(p_str).name

    if p_name in PROTECTED_FILE_NAMES:
        return True

    for pattern in PROTECTED_DIR_PATTERNS:
        if pattern in p_str:
            return True

    return False


async def intercept_agent_write_attempt(
    file_path: Path | str,
    actor: str,
    actor_role: str,
    db: Optional[AsyncSession] = None,
    initiative_id: Optional[str] = None,
    product_code: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    Application-level write interceptor:
    If actor_role is not 'human' (or 'system') and attempts to write to a protected path,
    blocks immediately, logs to decisions/, and emits a critical 🔴 ExecutiveRisk.
    Returns:
        (is_blocked, error_message)
    """
    if actor_role in ["human", "system"]:
        return False, None

    if not is_protected_path(file_path):
        return False, None

    now = datetime.now(timezone.utc)
    target_str = str(file_path)
    err_msg = (
        f"❌ 权限拒绝: Agent '{actor}' (角色: {actor_role}) 企图写入或篡改受保护系统文件 '{target_str}'。\n"
        "依据系统硬约束，授权包、平台规范与决策留痕区对所有 Agent 只读。每次修改必须由人类账号操作并在 decisions/ 留痕。"
    )

    # 1. Log security violation audit to decisions/
    if initiative_id and product_code:
        decisions_dir = Path(settings.WORKSPACE_DIR) / initiative_id / "products" / product_code / "decisions"
        decisions_dir.mkdir(parents=True, exist_ok=True)
        ts_str = now.strftime("%Y%m%d_%H%M%S")
        log_file = decisions_dir / f"{ts_str}_security_violation_unauthorized_write.json"
        log_file.write_text(json.dumps({
            "event": "SECURITY_VIOLATION_UNAUTHORIZED_WRITE",
            "timestamp": now.isoformat(),
            "actor": actor,
            "actor_role": actor_role,
            "target_file": target_str,
            "action": "BLOCKED",
            "reason": err_msg
        }, indent=2, ensure_ascii=False), encoding="utf-8")

    # 2. Emit Critical ExecutiveRisk alert
    if db and initiative_id:
        risk = ExecutiveRisk(
            initiative_id=initiative_id,
            rule_code="SECURITY_VIOLATION_UNAUTHORIZED_WRITE",
            title=f"🚨 越权拦截: Agent '{actor}' 企图篡改受保护文件",
            severity="critical",
            description=f"Agent '{actor}' (角色: {actor_role}) 试图非法写入受保护文件 '{target_str}'，已被系统拦截。",
            product_code=product_code,
            action_suggestion="请核查该 Agent 任务指令，确保 Agent 严格遵守只读契约。",
            is_resolved=False
        )
        db.add(risk)
        try:
            await db.commit()
        except Exception:
            pass

    return True, err_msg


def sanitize_agent_environment(
    env: Dict[str, str],
    allowed_credentials: Optional[List[str]] = None
) -> Dict[str, str]:
    """
    Credential Isolation:
    Strips store accounts, live payment keys, and prod DB credentials from environment variables.
    Only credentials explicitly listed in allowed_credentials (from authorization.yaml) are preserved.
    """
    clean_env = dict(env)
    allowed_set = set(allowed_credentials or [])

    for k in list(clean_env.keys()):
        # Check against strictly forbidden patterns
        is_forbidden = any(pat in k.upper() for pat in FORBIDDEN_CREDENTIAL_PATTERNS)
        if is_forbidden and k not in allowed_set:
            clean_env.pop(k, None)

    return clean_env


def validate_pricing_authority(
    actor_role: str,
    action_description: str = "修改定价"
) -> Tuple[bool, Optional[str]]:
    """
    Enforces that 'ba' (Commercial Analysis) is the sole source of truth for pricing.
    Neither PM nor MKT can modify pricing without a formal CR.
    """
    if actor_role in ["ba", "human"]:
        return True, None

    return False, (
        f"❌ 权限拒绝: 角色 '{actor_role}' 企图执行【{action_description}】。\n"
        "系统硬约束规定：商业分析师 (ba) 是产品定价与单位经济的唯一来源。"
        "pm、mkt 及其他角色严禁直接修改 02 商业定价，必须通过需求变更单 (CR) 路由给 ba 重新精算。"
    )
