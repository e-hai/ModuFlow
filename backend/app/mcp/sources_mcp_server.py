#!/usr/bin/env python3
"""可靠来源查阅工具。只暴露 lookup_reliable_sources，不暴露 cite。"""

import argparse
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.app.services.reliable_sources import lookup_reliable_sources

TOOL = {
    "name": "lookup_reliable_sources",
    "description": "按问题查阅可靠来源，把打开后的正文写入当前工作区 sources/，并返回摘录。搜索摘要不是摘录。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "要查阅的问题，通常是人刚说的方向"},
        },
        "required": ["question"],
    },
}


def _respond(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    args = parser.parse_args()
    workspace = Path(args.workspace)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        method = request.get("method")
        req_id = request.get("id")
        if method == "initialize":
            _respond({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "moduflow-sources", "version": "1"},
                },
            })
        elif method == "tools/list":
            _respond({"jsonrpc": "2.0", "id": req_id, "result": {"tools": [TOOL]}})
        elif method == "tools/call":
            params = request.get("params") or {}
            name = params.get("name")
            if name != "lookup_reliable_sources":
                _respond({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "unknown tool"}})
                continue
            question = ((params.get("arguments") or {}).get("question")) or ""
            result = lookup_reliable_sources(question, workspace)
            _respond({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]},
            })
        elif req_id is not None:
            _respond({"jsonrpc": "2.0", "id": req_id, "result": {}})


if __name__ == "__main__":
    main()
