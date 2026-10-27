#!/usr/bin/env python3
"""
ModuFlow Legacy Project Authorization Migration Script
(scripts/migrate_legacy_project_auth.py)

Scans existing projects in the workspace and database.
If a legacy project lacks an authorization.yaml, this script generates
a fully compliant default authorization package draft based on product metadata,
ensuring seamless backward compatibility.
"""

import sys
import os
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta
import yaml

# Add workspace root to sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.validate_authorization import validate_authorization, MANDATORY_LEAD_FORBIDDEN


def generate_default_authorization_dict(
    product_code: str,
    product_name: str,
    budget_allocated: float = 5000.0,
    platform: str = "ios",
    client_zero_inference: bool = True
) -> dict:
    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")
    deadline_str = (now + timedelta(days=90)).strftime("%Y-%m-%d")
    total_budget = float(budget_allocated) if budget_allocated > 0 else 5000.0
    hard_stop = round(total_budget * 1.1, 2)

    return {
        "schema_version": "1.0",
        "project_id": product_code,
        "project_name": product_name,
        "owner": {
            "name": "System Administrator",
            "role": "human_sponsor",
            "email": "sponsor@moduflow.ai"
        },
        "authorized_at": now.isoformat(),
        "time_budget": {
            "start_date": today_str,
            "deadline": deadline_str,
            "max_duration_days": 90
        },
        "financial_budget": {
            "currency": "USD",
            "total_budget_limit": total_budget,
            "hard_stop_limit": hard_stop,
            "per_stage_limits": {
                "01": round(total_budget * 0.05, 2),
                "02": round(total_budget * 0.03, 2),
                "03": round(total_budget * 0.02, 2),
                "04": round(total_budget * 0.08, 2),
                "05": round(total_budget * 0.06, 2),
                "06": round(total_budget * 0.16, 2),
                "07": round(total_budget * 0.30, 2),
                "08": round(total_budget * 0.08, 2),
                "09": round(total_budget * 0.04, 2),
                "10": round(total_budget * 0.14, 2),
                "11": round(total_budget * 0.04, 2)
            }
        },
        "kill_criteria": [
            {
                "id": "KC-01",
                "metric": "ltv_cac_ratio",
                "operator": "<",
                "threshold": 3.0,
                "action": "pause_and_escalate",
                "description": "LTV/CAC ratio below 3.0 breaches unit economics baseline"
            },
            {
                "id": "KC-02",
                "metric": "cac",
                "operator": ">",
                "threshold": 2.5,
                "action": "pause_and_escalate",
                "description": "Blended CAC exceeding 2.5 USD breaches acquisition ceiling"
            },
            {
                "id": "KC-03",
                "metric": "d1_retention",
                "operator": "<",
                "threshold": 0.25,
                "action": "pause_and_escalate",
                "description": "Day-1 retention below 25% fails stickiness validation"
            },
            {
                "id": "KC-04",
                "metric": "actual_spent",
                "operator": ">=",
                "threshold": hard_stop,
                "action": "terminate_project",
                "description": "Total spend reaching hard stop ceiling triggers termination"
            }
        ],
        "lead_forbidden": list(MANDATORY_LEAD_FORBIDDEN),
        "credential_scopes": {
            "allowed_agent_credentials": [
                "market_intelligence_api_token",
                "sandbox_payment_test_key"
            ],
            "forbidden_agent_credentials": [
                "apple_developer_account",
                "google_play_console_service_account",
                "stripe_live_secret_key",
                "production_database_credentials"
            ]
        },
        "profile": {
            "platform": platform,
            "client_zero_inference": client_zero_inference
        }
    }


def migrate_workspace_products(workspaces_dir: Path, dry_run: bool = False) -> list[dict]:
    results = []
    if not workspaces_dir.exists():
        print(f"Workspaces dir does not exist: {workspaces_dir}")
        return results

    # Pattern: workspaces/{initiative_id}/products/{product_code}/
    for init_dir in workspaces_dir.iterdir():
        if not init_dir.is_dir():
            continue
        products_dir = init_dir / "products"
        if not products_dir.exists() or not products_dir.is_dir():
            continue

        for p_dir in products_dir.iterdir():
            if not p_dir.is_dir():
                continue
            product_code = p_dir.name
            auth_file = p_dir / "authorization.yaml"

            if auth_file.exists():
                is_valid, errors, _ = validate_authorization(auth_file)
                results.append({
                    "product_code": product_code,
                    "initiative_id": init_dir.name,
                    "status": "existing_valid" if is_valid else "existing_invalid",
                    "file": str(auth_file),
                    "errors": errors
                })
            else:
                data = generate_default_authorization_dict(
                    product_code=product_code,
                    product_name=product_code,
                    budget_allocated=5000.0,
                    platform="ios"
                )
                if not dry_run:
                    auth_file.write_text(yaml.dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
                    is_valid, errors, _ = validate_authorization(auth_file)
                    results.append({
                        "product_code": product_code,
                        "initiative_id": init_dir.name,
                        "status": "migrated_created",
                        "file": str(auth_file),
                        "errors": errors
                    })
                else:
                    results.append({
                        "product_code": product_code,
                        "initiative_id": init_dir.name,
                        "status": "needs_migration",
                        "file": str(auth_file),
                        "errors": []
                    })
    return results


def main():
    parser = argparse.ArgumentParser(description="Migrate legacy projects to have valid authorization packages")
    parser.add_argument("--workspaces-dir", type=Path, default=WORKSPACE_ROOT / "data" / "workspaces", help="Workspaces directory path")
    parser.add_argument("--dry-run", action="store_true", help="Report what would be migrated without writing files")

    args = parser.parse_args()
    results = migrate_workspace_products(args.workspaces_dir, args.dry_run)

    print("=== ModuFlow Project Authorization Scan/Migration Summary ===")
    for r in results:
        print(f"[{r['status'].upper()}] Initiative: {r['initiative_id']}, Product: {r['product_code']}")
        print(f"   Path: {r['file']}")
        if r['errors']:
            print(f"   Errors: {r['errors']}")
    print(f"Total processed: {len(results)}")


if __name__ == "__main__":
    main()
