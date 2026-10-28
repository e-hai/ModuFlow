#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def _audit():
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "backend" / "app" / "services" / "deliverable_audit.py").exists():
            sys.path.insert(0, str(parent))
            break
    from backend.app.services.deliverable_audit import audit_som_workspace
    return audit_som_workspace(Path.cwd())


def main():
    try:
        result = _audit()
    except Exception as exc:
        result = {"passed": False, "error": f"checker unavailable: {exc}"}
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result.get("passed") else 1)


if __name__ == "__main__":
    main()
