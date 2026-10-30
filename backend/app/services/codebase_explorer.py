import os
import shutil
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.app.core.config import settings
from backend.app.models.entities import ModuleInstance, WorkflowRun, Product, StrategicInitiative
from backend.app.services.workspace_sync import (
    sanitize_dirname,
    get_stage_dir_name,
    get_run_dir_name,
)

# Ignored patterns when building the interactive codebase tree
IGNORED_DIRS = {
    ".git", ".gradle", "build", ".idea", ".agents",
    "__pycache__", ".pytest_cache", ".DS_Store", "versions"
}

IGNORED_FILES = {
    ".DS_Store", ".moduflow_agent_context.md", "delivery.manifest.json",
    "manifest.json", "tokens.json"
}

LANGUAGE_MAP = {
    ".kt": "kotlin",
    ".kts": "gradle",
    ".swift": "swift",
    ".json": "json",
    ".xml": "xml",
    ".md": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".properties": "properties",
    ".sh": "bash",
    ".bash": "bash",
    ".html": "html",
    ".css": "css",
    ".js": "javascript",
    ".ts": "typescript",
}


def detect_file_language(filename: str) -> str:
    lower = filename.lower()
    if lower == "gradlew" or lower.endswith(".sh"):
        return "bash"
    suffix = Path(filename).suffix.lower()
    return LANGUAGE_MAP.get(suffix, "plaintext")


async def resolve_module_codebase_dir(db: AsyncSession, module_id: str) -> Tuple[ModuleInstance, Path, Path]:
    """
    Resolve the physical workspace and codebase root directory for a module instance.
    Returns (module_instance, workspace_dir, codebase_dir).
    """
    stmt = (
        select(ModuleInstance)
        .options(
            selectinload(ModuleInstance.workflow_run)
            .selectinload(WorkflowRun.product)
            .selectinload(Product.initiative)
        )
        .where(ModuleInstance.id == module_id)
    )
    res = await db.execute(stmt)
    mod = res.scalar_one_or_none()
    if not mod:
        raise ValueError(f"Module {module_id} not found")

    run = mod.workflow_run
    prod = run.product if run else None
    init = prod.initiative if prod else None

    init_dir_name = sanitize_dirname(init.id if init else "standalone")
    prod_code_name = sanitize_dirname(prod.code if prod else "unknown")
    run_name = get_run_dir_name(run.name if run else "run", run.id if run else "")
    mod_dir_name = get_stage_dir_name(mod.order_index, mod.module_code, mod.name)

    workspace_dir = (settings.WORKSPACE_DIR / init_dir_name / "products" / prod_code_name / run_name / mod_dir_name).resolve()
    if not workspace_dir.exists():
        legacy_run_name = sanitize_dirname(run.name if run else "run")
        legacy_mod_name = f"{mod.order_index:02d}_{mod.module_code}_{sanitize_dirname(mod.name)}"
        legacy_workspace = (settings.WORKSPACE_DIR / init_dir_name / "products" / prod_code_name / legacy_run_name / legacy_mod_name).resolve()
        if legacy_workspace.exists():
            workspace_dir = legacy_workspace
    
    # Check if code is organized under a dedicated codebase/ subfolder or at workspace root
    candidate_sub = workspace_dir / "codebase"
    codebase_dir = candidate_sub if candidate_sub.is_dir() else workspace_dir

    return mod, workspace_dir, codebase_dir


def build_tree_node(path: Path, root: Path) -> Optional[Dict[str, Any]]:
    """Recursively build a tree node for a directory or file."""
    name = path.name
    if name in IGNORED_DIRS or name in IGNORED_FILES:
        return None
    if name.startswith(".") and name not in (".gitignore", ".editorconfig"):
        return None

    rel_path = str(path.relative_to(root))
    if path.is_dir():
        children: List[Dict[str, Any]] = []
        try:
            entries = sorted(list(path.iterdir()), key=lambda p: (not p.is_dir(), p.name.lower()))
            for entry in entries:
                child = build_tree_node(entry, root)
                if child:
                    children.append(child)
        except PermissionError:
            pass
        return {
            "name": name,
            "type": "directory",
            "path": rel_path,
            "children": children
        }
    else:
        size = path.stat().st_size
        lang = detect_file_language(name)
        return {
            "name": name,
            "type": "file",
            "path": rel_path,
            "language": lang,
            "size": size
        }


def get_codebase_summary_and_tree(codebase_dir: Path) -> Dict[str, Any]:
    """Scan the codebase directory and return summary stats + full file tree."""
    if not codebase_dir.exists():
        return {
            "root_name": codebase_dir.name,
            "codebase_path": str(codebase_dir),
            "exists": False,
            "total_files": 0,
            "total_lines": 0,
            "tree": []
        }

    tree: List[Dict[str, Any]] = []
    total_files = 0
    total_lines = 0

    entries = sorted(list(codebase_dir.iterdir()), key=lambda p: (not p.is_dir(), p.name.lower()))
    for entry in entries:
        node = build_tree_node(entry, codebase_dir)
        if node:
            tree.append(node)

    # Count files and lines across valid text files
    for f in codebase_dir.rglob("*"):
        if f.is_file() and not any(part in IGNORED_DIRS for part in f.parts):
            if f.name not in IGNORED_FILES and not f.name.startswith("."):
                total_files += 1
                try:
                    # quick estimate of lines
                    with open(f, "r", encoding="utf-8", errors="ignore") as fh:
                        total_lines += sum(1 for _ in fh)
                except Exception:
                    pass

    return {
        "root_name": codebase_dir.name,
        "codebase_path": str(codebase_dir),
        "exists": True,
        "total_files": total_files,
        "total_lines": total_lines,
        "tree": tree
    }


def read_codebase_file(codebase_dir: Path, rel_path: str) -> Dict[str, Any]:
    """Securely read a file from the codebase directory."""
    target = (codebase_dir / rel_path).resolve()
    # Guard against directory traversal
    if not str(target).startswith(str(codebase_dir.resolve())):
        raise PermissionError("Access denied: path traverses outside codebase directory")
    if not target.is_file():
        raise FileNotFoundError(f"File not found: {rel_path}")

    # Don't read files larger than 1MB into editor
    if target.stat().st_size > 1_048_576:
        return {
            "path": rel_path,
            "name": target.name,
            "size": target.stat().st_size,
            "language": detect_file_language(target.name),
            "content": f"// File size exceeds 1MB ({target.stat().st_size} bytes). View in local IDE."
        }

    content = target.read_text(encoding="utf-8", errors="replace")
    return {
        "path": rel_path,
        "name": target.name,
        "size": target.stat().st_size,
        "language": detect_file_language(target.name),
        "content": content
    }


async def open_codebase_in_local_ide(codebase_dir: Path, ide: str) -> Dict[str, Any]:
    """
    Launch native IDE on macOS to open the codebase.
    Supported: 'android_studio' | 'xcode'
    """
    if not codebase_dir.exists():
        return {
            "success": False,
            "message": f"工程目录不存在: {codebase_dir}",
            "codebase_path": str(codebase_dir)
        }

    target_path = codebase_dir
    app_name = "Android Studio"

    if ide == "xcode":
        app_name = "Xcode"
        # Look for .xcodeproj or .xcworkspace
        candidates = list(codebase_dir.glob("**/*.xcodeproj")) + list(codebase_dir.glob("**/*.xcworkspace"))
        if candidates:
            target_path = candidates[0]
        else:
            ios_dir = codebase_dir / "iosApp"
            if ios_dir.is_dir():
                target_path = ios_dir
    else:
        # Default to Android Studio for KMP/Gradle projects
        app_name = "Android Studio"
        target_path = codebase_dir

    cmd = ["open", "-a", app_name, str(target_path)]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            return {
                "success": True,
                "ide": ide,
                "app_name": app_name,
                "opened_path": str(target_path),
                "message": f"已成功调起本地 {app_name} 打开工程！"
            }
        else:
            err_msg = stderr.decode().strip() or stdout.decode().strip()
            return {
                "success": False,
                "ide": ide,
                "app_name": app_name,
                "opened_path": str(target_path),
                "message": f"未能调起 {app_name}: {err_msg}。请确认本地是否已安装该 IDE，或手动打开路径：{target_path}"
            }
    except Exception as exc:
        return {
            "success": False,
            "ide": ide,
            "app_name": app_name,
            "opened_path": str(target_path),
            "message": f"调用系统 open 指令异常: {str(exc)}。工程绝对路径为: {target_path}"
        }
