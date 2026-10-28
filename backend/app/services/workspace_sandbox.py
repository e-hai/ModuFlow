"""
Filesystem sandbox for Agent CLI runs.

Two layers:
1. OS write restriction (macOS ``sandbox-exec``): the CLI may only write its own stage
   directory, temp dirs and the CLI's own state dirs under $HOME. Mounted Skills and MCP
   configs inside the stage directory stay read-only.
2. Integrity check (all platforms): files that no backend code rewrites during a run
   (authorization package, existing decision logs, mounted Skills, MCP configs) are
   snapshotted before the run and restored afterwards if the Agent changed them.
"""
import hashlib
import os
import platform as py_platform
import shutil
import subprocess
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from backend.app.core.config import settings

AUTHORIZATION_FILES = ("authorization.yaml", "authorization.json")
MCP_CONFIG_FILES = (".mcp.json", ".agents/mcp_config.json")

# CLI state dirs under $HOME that agy / claude / codex / cursor-agent write at startup.
HOME_WRITABLE_SUBPATHS = (
    ".claude",
    ".codex",
    ".gemini",
    ".antigravity",
    ".cursor",
    ".config",
    ".cache",
    ".npm",
    ".local/state",
    ".local/share",
    "Library/Caches",
    "Library/Application Support",
    "Library/Logs",
    "Library/Preferences",
)
HOME_WRITABLE_FILE_PREFIXES = (".claude.json",)


@dataclass
class IntegritySnapshot:
    files: Dict[Path, Tuple[bytes, int]] = field(default_factory=dict)
    append_only_dirs: List[Path] = field(default_factory=list)
    frozen_dirs: List[Path] = field(default_factory=list)


def product_dir_for(workspace_dir: Path) -> Path:
    """data/workspaces/{initiative}/products/{product}/{run}/{stage} -> .../products/{product}"""
    return workspace_dir.resolve().parent.parent


def _iter_files(root: Path) -> List[Path]:
    if not root.exists():
        return []
    return [p for p in root.rglob("*") if p.is_file() and not p.is_symlink()]


def take_integrity_snapshot(workspace_dir: Path) -> IntegritySnapshot:
    workspace_dir = workspace_dir.resolve()
    product_dir = product_dir_for(workspace_dir)
    snap = IntegritySnapshot()

    tracked: List[Path] = [product_dir / name for name in AUTHORIZATION_FILES]
    tracked += [workspace_dir / name for name in MCP_CONFIG_FILES]

    decisions_dir = product_dir / "decisions"
    snap.append_only_dirs.append(decisions_dir)
    tracked += _iter_files(decisions_dir)

    skills_dir = workspace_dir / ".agents" / "skills"
    snap.frozen_dirs.append(skills_dir)
    tracked += _iter_files(skills_dir)

    for path in tracked:
        if path.is_file():
            snap.files[path] = (path.read_bytes(), path.stat().st_mode & 0o777)
    return snap


def _restore(path: Path, data: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        os.chmod(path, 0o644)
    path.write_bytes(data)
    os.chmod(path, mode)


def verify_and_restore(snap: IntegritySnapshot) -> List[str]:
    """Returns violated paths; modified or deleted files are restored, files added to frozen dirs removed."""
    violations: List[str] = []
    for path, (data, mode) in snap.files.items():
        if not path.exists() or path.read_bytes() != data:
            violations.append(str(path))
            _restore(path, data, mode)

    for frozen in snap.frozen_dirs:
        for path in _iter_files(frozen):
            if path not in snap.files:
                violations.append(str(path))
                path.unlink()
    return violations


@lru_cache(maxsize=1)
def _sandbox_exec_works() -> bool:
    """sandbox-exec cannot nest: it fails when the backend itself already runs inside a sandbox."""
    if py_platform.system() != "Darwin" or shutil.which("sandbox-exec") is None:
        return False
    try:
        probe = subprocess.run(
            ["sandbox-exec", "-p", "(version 1)(allow default)", "/usr/bin/true"],
            capture_output=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return probe.returncode == 0


def os_sandbox_available() -> bool:
    if (settings.AGENT_FS_SANDBOX or "auto").lower() == "off":
        return False
    return _sandbox_exec_works()


def sandbox_layers() -> str:
    return "sandbox-exec 写入限制 + 完整性校验" if os_sandbox_available() else "完整性校验（OS 沙箱不可用）"


def _sb_quote(path: Path | str) -> str:
    return '"' + str(path).replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_sandbox_profile(workspace_dir: Path, home: Optional[Path] = None) -> str:
    workspace_dir = workspace_dir.resolve()
    home = (home or Path.home()).resolve()
    allow = [
        f"(subpath {_sb_quote(workspace_dir)})",
        '(subpath "/private/tmp")',
        '(subpath "/private/var/folders")',
        '(subpath "/dev")',
    ]
    allow += [f"(subpath {_sb_quote(home / sub)})" for sub in HOME_WRITABLE_SUBPATHS]
    allow += [f"(prefix {_sb_quote(home / name)})" for name in HOME_WRITABLE_FILE_PREFIXES]
    deny_inside = [
        f"(subpath {_sb_quote(workspace_dir / '.agents' / 'skills')})",
    ] + [f"(literal {_sb_quote(workspace_dir / name)})" for name in MCP_CONFIG_FILES]
    return "\n".join([
        "(version 1)",
        "(allow default)",
        "(deny file-write*)",
        "(allow file-write*\n  " + "\n  ".join(allow) + ")",
        "(deny file-write*\n  " + "\n  ".join(deny_inside) + ")",
        "",
    ])


def wrap_command(args: List[str], workspace_dir: Path) -> Tuple[List[str], Optional[Path]]:
    """Prefix the CLI command with sandbox-exec when available; returns (args, profile_path)."""
    if not os_sandbox_available():
        return args, None
    profile_dir = Path(settings.DATA_DIR) / "sandbox_profiles"
    profile_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(str(workspace_dir.resolve()).encode("utf-8")).hexdigest()[:16]
    profile_path = profile_dir / f"{digest}.sb"
    profile_path.write_text(build_sandbox_profile(workspace_dir), encoding="utf-8")
    return ["sandbox-exec", "-f", str(profile_path)] + list(args), profile_path
