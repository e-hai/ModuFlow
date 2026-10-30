#!/usr/bin/env python3
"""
Migrates workspace directory paths and database artifact storage paths from legacy
Chinese / redundant naming (e.g. 'FocusZen V1.0 首发全流程产研迭代/07_07_开发实现')
to clean ASCII-only slug paths (e.g. 'run_focuszen_v1.0/07_development').
Creates symlinks from legacy paths to new paths for backward compatibility.
"""

import os
import re
import shutil
import sqlite3
from pathlib import Path

WORKSPACE_ROOT = Path("data/workspaces").resolve()
DB_PATH = Path("data/moduflow.db").resolve()

STAGE_SLUGS = {
    "01": "market_research",
    "02": "business_model",
    "03": "product_direction",
    "04": "fake_door",
    "05": "product_requirement",
    "06": "design_implementation",
    "07": "development",
    "08": "testing_qa",
    "09": "release_deployment",
    "10": "growth_marketing",
    "11": "operations_iteration",
}

STAGE_NAMES = {
    "01": "市场研究",
    "02": "商业模式分析",
    "03": "产品方向决策",
    "04": "低成本市场验证",
    "05": "产品需求定义",
    "06": "设计实现",
    "07": "开发实现",
    "08": "测试与 QA",
    "09": "发布与上线",
    "10": "市场推广与获客",
    "11": "运营分析与持续迭代",
}


def slugify_ascii(text: str, fallback: str = "item") -> str:
    if not text:
        return fallback
    s = re.sub(r'[\s/\\:*"<>|]+', '_', text.strip())
    s = re.sub(r'[^a-zA-Z0-9_.-]', '', s)
    s = re.sub(r'_+', '_', s).strip('._-')
    return s.lower() if s else fallback


def get_stage_dir_name(order_index: int, module_code: str, name: str = "") -> str:
    slug = STAGE_SLUGS.get(module_code)
    if not slug:
        slug = slugify_ascii(name or module_code, fallback=f"stage_{module_code}")
    return f"{order_index:02d}_{slug}"


def get_run_dir_name(run_name: str, run_id: str = "") -> str:
    fallback = f"run_{run_id[:8]}" if run_id else "run_iteration"
    slug = slugify_ascii(run_name, fallback=fallback)
    if not slug.lower().startswith("run"):
        slug = f"run_{slug}"
    return slug


def migrate_workspaces():
    print("🚀 Starting workspace path migration to clean ASCII slugs...")

    if not WORKSPACE_ROOT.exists():
        print(f"❌ Workspace root {WORKSPACE_ROOT} does not exist.")
        return

    # Track old relative path -> new relative path mappings
    rel_path_mappings = {}

    # Find product directories
    for init_dir in WORKSPACE_ROOT.iterdir():
        if not init_dir.is_dir() or init_dir.name.startswith("."):
            continue

        products_dir = init_dir / "products"
        if not products_dir.is_dir():
            continue

        for prod_dir in products_dir.iterdir():
            if not prod_dir.is_dir() or prod_dir.name.startswith(".") or prod_dir.name == "decisions":
                continue

            # Iterate over run directories
            for run_dir in list(prod_dir.iterdir()):
                if not run_dir.is_dir() or run_dir.name.startswith(".") or run_dir.name in ("decisions", "README.md") or run_dir.is_symlink():
                    continue

                old_run_name = run_dir.name
                new_run_name = get_run_dir_name(old_run_name)

                # Migrate module directories inside run_dir first
                for mod_dir in list(run_dir.iterdir()):
                    if not mod_dir.is_dir() or mod_dir.name.startswith(".") or mod_dir.name in ("decisions", "README.md", ".agents", "versions") or mod_dir.is_symlink():
                        continue

                    old_mod_name = mod_dir.name
                    # Parse module order and code from old name like '07_07_开发实现'
                    match = re.match(r"^(\d{2})_(\d{2})_(.*)$", old_mod_name)
                    if match:
                        order_idx = int(match.group(1))
                        mod_code = match.group(2)
                        chinese_name = match.group(3)
                        new_mod_name = get_stage_dir_name(order_idx, mod_code, chinese_name)
                    else:
                        continue

                    if old_mod_name != new_mod_name:
                        target_mod_dir = run_dir / new_mod_name
                        print(f"  📁 Module: {old_mod_name} -> {new_mod_name}")
                        if not target_mod_dir.exists():
                            shutil.move(str(mod_dir), str(target_mod_dir))
                            # Create backward compatible symlink
                            os.symlink(new_mod_name, str(mod_dir))
                        else:
                            print(f"    Target {target_mod_dir} already exists, skipping move")

                        old_rel = f"{init_dir.name}/products/{prod_dir.name}/{old_run_name}/{old_mod_name}"
                        new_rel = f"{init_dir.name}/products/{prod_dir.name}/{new_run_name}/{new_mod_name}"
                        rel_path_mappings[old_rel] = new_rel

                # Now rename run_dir if needed
                if old_run_name != new_run_name:
                    target_run_dir = prod_dir / new_run_name
                    print(f"📦 Run: {old_run_name} -> {new_run_name}")
                    if not target_run_dir.exists():
                        shutil.move(str(run_dir), str(target_run_dir))
                        # Create backward compatible symlink
                        os.symlink(new_run_name, str(run_dir))
                    else:
                        print(f"  Target {target_run_dir} already exists, skipping move")

    # Update database artifacts
    if DB_PATH.exists() and rel_path_mappings:
        print(f"\n💾 Updating {len(rel_path_mappings)} path mappings in database {DB_PATH}...")
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        updated_count = 0

        for old_rel, new_rel in rel_path_mappings.items():
            cursor.execute(
                "UPDATE artifacts SET storage_rel_path = ? WHERE storage_rel_path = ?",
                (new_rel, old_rel)
            )
            updated_count += cursor.rowcount

        conn.commit()
        conn.close()
        print(f"✅ Successfully updated {updated_count} artifact records in database.")

    print("\n🎉 Workspace path migration completed!")


if __name__ == "__main__":
    migrate_workspaces()
