"""
ModuFlow Deterministic Authorization & Circuit Breaker Engine
(backend/app/services/authorization_engine.py)

Enforces:
1. Authorization package validation against JSON Schema 2020-12 & Mandatory Lead Forbidden rules
2. Deterministic, zero-LLM budget limit check (total, hard-stop, per-stage)
3. Deterministic time limit & deadline check
4. Deterministic stop-loss check against kill_criteria
5. Lead forbidden action block
6. Automatic circuit breaker execution (paused state, decisions/ log, critical 🔴 alert)
"""

import os
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Tuple, List, Optional
import yaml

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.core.config import settings
from backend.app.models.entities import Product, ExecutiveRisk
from scripts.validate_authorization import (
    validate_schema,
    validate_business_rules,
    DEFAULT_SCHEMA_PATH,
    MANDATORY_LEAD_FORBIDDEN
)


def get_workspace_root() -> Path:
    return Path(settings.WORKSPACE_DIR)


def get_product_dir(initiative_id: str, product_code: str) -> Path:
    return get_workspace_root() / initiative_id / "products" / product_code


def get_product_authorization_path(initiative_id: str, product_code: str) -> Path:
    return get_product_dir(initiative_id, product_code) / "authorization.yaml"


def validate_authorization_dict(data: dict, schema_path: Path = DEFAULT_SCHEMA_PATH) -> Tuple[bool, List[str]]:
    schema_errors = validate_schema(data, schema_path)
    biz_errors = validate_business_rules(data)
    all_errors = schema_errors + biz_errors
    return len(all_errors) == 0, all_errors


def validate_authorization_file(file_path: Path, schema_path: Path = DEFAULT_SCHEMA_PATH) -> Tuple[bool, List[str], Optional[dict]]:
    if not file_path.exists():
        return False, [f"Authorization file not found at: {file_path}"], None
    try:
        text = file_path.read_text(encoding="utf-8")
        if file_path.suffix.lower() in [".yaml", ".yml"]:
            data = yaml.safe_load(text)
        else:
            data = json.loads(text)
        if not isinstance(data, dict):
            return False, ["Authorization file content must be a mapping/dict"], None
    except Exception as exc:
        return False, [f"Failed to read/parse authorization file: {exc}"], None

    is_valid, errors = validate_authorization_dict(data, schema_path)
    return is_valid, errors, data


def load_product_authorization(initiative_id: str, product_code: str) -> Tuple[str, Optional[dict], List[str]]:
    """
    Loads and validates the authorization package for a product.
    Returns:
        status: 'authorized' | 'needs_authorization' | 'invalid_authorization'
        data: dict or None
        errors: list of error strings
    """
    auth_path = get_product_authorization_path(initiative_id, product_code)
    if not auth_path.exists():
        return "needs_authorization", None, [f"Missing authorization.yaml at {auth_path}"]

    is_valid, errors, data = validate_authorization_file(auth_path)
    if not is_valid:
        return "invalid_authorization", None, errors

    return "authorized", data, []


def check_budget_limits(
    auth_data: dict,
    actual_spent: float,
    stage_code: Optional[str] = None,
    stage_spent: Optional[float] = None
) -> Tuple[bool, Optional[str], bool]:
    """
    Deterministic budget check.
    Returns:
        (is_breached, reason_message, is_hard_stop)
    """
    fin = auth_data.get("financial_budget", {})
    total_limit = float(fin.get("total_budget_limit", 0))
    hard_stop = float(fin.get("hard_stop_limit", total_limit))

    if actual_spent >= hard_stop:
        return True, f"Actual spent ({actual_spent:.2f}) reached or exceeded hard stop limit ({hard_stop:.2f})", True

    if actual_spent > total_limit:
        return True, f"Actual spent ({actual_spent:.2f}) exceeded total budget limit ({total_limit:.2f})", False

    if stage_code and stage_spent is not None:
        stage_limits = fin.get("per_stage_limits", {})
        if stage_code in stage_limits:
            stg_limit = float(stage_limits[stage_code])
            if stage_spent > stg_limit:
                return True, f"Stage {stage_code} spent ({stage_spent:.2f}) exceeded stage limit ({stg_limit:.2f})", False

    return False, None, False


def check_time_limits(
    auth_data: dict,
    current_time: Optional[datetime] = None
) -> Tuple[bool, Optional[str]]:
    """
    Deterministic deadline and duration check.
    Returns:
        (is_expired, reason_message)
    """
    tb = auth_data.get("time_budget", {})
    now = current_time or datetime.now(timezone.utc)

    # Check deadline
    deadline_str = tb.get("deadline")
    if deadline_str:
        try:
            deadline_dt = datetime.fromisoformat(str(deadline_str).replace("Z", "+00:00"))
            if deadline_dt.tzinfo is None:
                deadline_dt = deadline_dt.replace(tzinfo=timezone.utc)
            if now > deadline_dt:
                return True, f"Project deadline ({deadline_str}) has expired. Current time: {now.isoformat()}"
        except ValueError:
            try:
                deadline_d = datetime.strptime(str(deadline_str), "%Y-%m-%d").date()
                if now.date() > deadline_d:
                    return True, f"Project deadline ({deadline_str}) has expired."
            except ValueError:
                pass

    # Check max duration days
    start_str = tb.get("start_date")
    max_days = tb.get("max_duration_days")
    if start_str and max_days:
        try:
            start_d = datetime.strptime(str(start_str)[:10], "%Y-%m-%d").date()
            elapsed_days = (now.date() - start_d).days
            if elapsed_days > max_days:
                return True, f"Project duration ({elapsed_days} days) exceeded max allowed duration ({max_days} days)"
        except ValueError:
            pass

    return False, None


def check_kill_criteria(
    auth_data: dict,
    metrics: Dict[str, float]
) -> List[Dict[str, Any]]:
    """
    Deterministic stop-loss condition evaluator.
    Compares current metrics against thresholds without LLM.
    Returns list of triggered kill criteria objects.
    """
    triggered = []
    kill_criteria = auth_data.get("kill_criteria", [])

    for kc in kill_criteria:
        m_name = kc.get("metric")
        if m_name not in metrics:
            continue

        curr_val = float(metrics[m_name])
        threshold = float(kc.get("threshold", 0))
        op = kc.get("operator")

        is_hit = False
        if op == ">" and curr_val > threshold:
            is_hit = True
        elif op == "<" and curr_val < threshold:
            is_hit = True
        elif op == ">=" and curr_val >= threshold:
            is_hit = True
        elif op == "<=" and curr_val <= threshold:
            is_hit = True
        elif op == "==" and abs(curr_val - threshold) < 1e-6:
            is_hit = True
        elif op == "!=" and abs(curr_val - threshold) >= 1e-6:
            is_hit = True

        if is_hit:
            triggered.append({
                "id": kc.get("id"),
                "metric": m_name,
                "current_value": curr_val,
                "threshold": threshold,
                "operator": op,
                "action": kc.get("action", "pause_and_escalate"),
                "description": kc.get("description", "")
            })

    return triggered


def check_lead_forbidden_action(
    auth_data: dict,
    action_name: str
) -> Tuple[bool, Optional[str]]:
    """
    Checks if a requested action is strictly forbidden for the lead agent.
    Returns:
        (is_forbidden, reason_message)
    """
    forbidden_list = auth_data.get("lead_forbidden", [])
    if action_name in forbidden_list:
        return True, (
            f"Action '{action_name}' is strictly forbidden for lead agent per authorization package and system redlines. "
            "Must be escalated to human sponsor."
        )
    return False, None


async def execute_circuit_breaker(
    initiative_id: str,
    product_code: str,
    trigger_type: str,
    details: Dict[str, Any],
    db: AsyncSession
) -> Dict[str, Any]:
    """
    Deterministic Circuit Breaker:
    1. Sets product status to 'paused' in database
    2. Writes decisions/{timestamp}_{trigger_type}.json audit log on disk
    3. Creates a Critical (🔴) ExecutiveRisk record
    """
    now = datetime.now(timezone.utc)
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")
    event_id = f"cb_{uuid.uuid4().hex[:8]}"

    # 1. Update Product status in DB
    result = await db.execute(select(Product).where(Product.code == product_code))
    product = result.scalar_one_or_none()
    if product:
        product.stage = "paused"
        product.key_risk = f"🔴 熔断触发: {trigger_type} - {details.get('reason', '')}"
        product.recommendation = "暂停派活，等待人类负责人审批或止损"

    # 2. Write decisions/ file on disk
    decisions_dir = get_product_dir(initiative_id, product_code) / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    decision_file = decisions_dir / f"{timestamp_str}_{trigger_type}.json"

    event_payload = {
        "event_id": event_id,
        "timestamp": now.isoformat(),
        "initiative_id": initiative_id,
        "product_code": product_code,
        "trigger_type": trigger_type,
        "action_taken": "paused",
        "escalation_level": "red",
        "actor": "deterministic_authorization_engine",
        "details": details
    }
    decision_file.write_text(json.dumps(event_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # 3. Create Critical ExecutiveRisk record
    risk = ExecutiveRisk(
        initiative_id=initiative_id,
        rule_code=f"CIRCUIT_BREAKER_{trigger_type.upper()}",
        title=f"🔴 确定性熔断: {trigger_type}",
        severity="critical",
        description=f"项目 {product_code} 触发确定性红线熔断: {details.get('reason', '')}。系统已自动置为 paused，阻断所有派活。",
        product_code=product_code,
        action_suggestion="请人类负责人检查项目授权包、追加预算或执行项目止损决策。",
        is_resolved=False
    )
    db.add(risk)
    await db.commit()

    return event_payload
