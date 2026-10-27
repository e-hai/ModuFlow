#!/usr/bin/env python3
"""
ModuFlow Authorization Package Validator (validate_authorization.py)
Validates an authorization.yaml / authorization.json file against:
1. JSON Schema 2020-12 (schemas/authorization-package.schema.json)
2. Mandatory lead_forbidden action list (Section 2 Hard Constraints)
3. Deterministic budget, time, and stop-loss logic rules.

Exit codes:
0: Valid authorization package
1: Validation failed (with structured diagnostics)
"""

import sys
import os
import json
import argparse
from pathlib import Path
from datetime import datetime
import yaml

try:
    import jsonschema
    from jsonschema.validators import validator_for
except ImportError:
    jsonschema = None

MANDATORY_LEAD_FORBIDDEN = [
    "approve_g1_g2_g4_g5",
    "modify_permissions",
    "modify_redlines",
    "modify_budget",
    "approve_payment_or_privacy_cr",
    "trigger_unauthorized_hotfix",
    "approve_budget_increase",
    "submit_store_review"
]

DEFAULT_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "authorization-package.schema.json"


def load_file_content(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Authorization file not found at: {path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in [".yaml", ".yml"]:
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"Authorization content must be a dictionary/mapping, got {type(data).__name__}")
    return data


def validate_schema(data: dict, schema_path: Path) -> list[str]:
    errors = []
    if not schema_path.exists():
        errors.append(f"Schema file not found at: {schema_path}")
        return errors

    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    if jsonschema is not None:
        validator_cls = validator_for(schema)
        validator = validator_cls(schema)
        for err in validator.iter_errors(data):
            path_str = ".".join(str(p) for p in err.path) or "root"
            errors.append(f"[{path_str}] {err.message}")
    else:
        # Fallback basic required key check if jsonschema is missing
        required_keys = schema.get("required", [])
        for k in required_keys:
            if k not in data:
                errors.append(f"Missing required field: '{k}'")
    return errors


def validate_business_rules(data: dict) -> list[str]:
    errors = []

    # 1. Mandatory lead_forbidden items check
    lead_forbidden = data.get("lead_forbidden", [])
    if not isinstance(lead_forbidden, list):
        errors.append("lead_forbidden must be a list of strings")
    else:
        existing_forbidden_set = set(lead_forbidden)
        missing_forbidden = [item for item in MANDATORY_LEAD_FORBIDDEN if item not in existing_forbidden_set]
        if missing_forbidden:
            errors.append(
                f"Missing mandatory lead_forbidden items: {', '.join(missing_forbidden)}. "
                "Per system redlines, lead agent cannot be granted these capabilities."
            )

    # 2. Budget limits check
    financial_budget = data.get("financial_budget", {})
    if isinstance(financial_budget, dict):
        total_limit = financial_budget.get("total_budget_limit", 0)
        hard_stop = financial_budget.get("hard_stop_limit", 0)
        if hard_stop < total_limit:
            errors.append(
                f"hard_stop_limit ({hard_stop}) cannot be lower than total_budget_limit ({total_limit})"
            )

    # 3. Time budget check
    time_budget = data.get("time_budget", {})
    if isinstance(time_budget, dict):
        start_str = time_budget.get("start_date")
        deadline_str = time_budget.get("deadline")
        if start_str and deadline_str:
            try:
                start_dt = datetime.fromisoformat(str(start_str).replace("Z", "+00:00"))
                deadline_dt = datetime.fromisoformat(str(deadline_str).replace("Z", "+00:00"))
                if deadline_dt < start_dt:
                    errors.append(f"deadline ({deadline_str}) cannot be before start_date ({start_str})")
            except ValueError:
                # Could be YYYY-MM-DD
                try:
                    s_dt = datetime.strptime(str(start_str), "%Y-%m-%d")
                    d_dt = datetime.strptime(str(deadline_str), "%Y-%m-%d")
                    if d_dt < s_dt:
                        errors.append(f"deadline ({deadline_str}) cannot be before start_date ({start_str})")
                except ValueError:
                    errors.append(f"Invalid date format in time_budget: start='{start_str}', deadline='{deadline_str}'")

    # 4. Kill criteria check
    kill_criteria = data.get("kill_criteria", [])
    if isinstance(kill_criteria, list):
        kc_ids = set()
        for idx, kc in enumerate(kill_criteria):
            if isinstance(kc, dict):
                k_id = kc.get("id")
                if k_id in kc_ids:
                    errors.append(f"Duplicate kill_criteria id: '{k_id}' at index {idx}")
                if k_id:
                    kc_ids.add(k_id)

    # 5. Credential scopes check
    cred_scopes = data.get("credential_scopes", {})
    if isinstance(cred_scopes, dict):
        forbidden_creds = set(cred_scopes.get("forbidden_agent_credentials", []))
        # Ensure mandatory human-only credentials are protected
        mandatory_forbidden_creds = [
            "apple_developer_account",
            "stripe_live_secret_key",
            "production_database_credentials"
        ]
        missing_creds = [c for c in mandatory_forbidden_creds if not any(c in f for f in forbidden_creds)]
        if missing_creds:
            errors.append(
                f"Missing protected credentials in forbidden_agent_credentials: {', '.join(missing_creds)}. "
                "Store accounts, live payment keys, and production DBs must be human-only."
            )

    return errors


def validate_authorization(file_path: Path, schema_path: Path = DEFAULT_SCHEMA_PATH) -> tuple[bool, list[str], dict | None]:
    try:
        data = load_file_content(file_path)
    except Exception as exc:
        return False, [f"Failed to load file: {exc}"], None

    schema_errors = validate_schema(data, schema_path)
    business_errors = validate_business_rules(data)
    all_errors = schema_errors + business_errors

    return len(all_errors) == 0, all_errors, data


def main():
    parser = argparse.ArgumentParser(description="Validate ModuFlow Authorization Package")
    parser.add_argument("file", type=Path, help="Path to authorization.yaml or authorization.json")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH, help="Path to JSON Schema file")
    parser.add_argument("--json-output", action="store_true", help="Output results in JSON format")

    args = parser.parse_args()

    is_valid, errors, data = validate_authorization(args.file, args.schema)

    result = {
        "valid": is_valid,
        "file": str(args.file),
        "errors": errors,
        "project_id": data.get("project_id") if data else None,
        "total_budget": data.get("financial_budget", {}).get("total_budget_limit") if data else None
    }

    if args.json_output:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if is_valid:
            print(f"✅ Authorization package is VALID: {args.file}")
            print(f"   Project: {result['project_id']}, Total Budget Limit: {result['total_budget']}")
        else:
            print(f"❌ Authorization package is INVALID: {args.file}")
            for err in errors:
                print(f"   - {err}")

    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
