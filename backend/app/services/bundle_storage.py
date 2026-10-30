import io
import zipfile
import shutil
import hashlib
from pathlib import Path
from typing import Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.app.core.config import settings
from backend.app.models.entities import (
    ModuleInstance,
    WorkflowRun,
    Product,
    StrategicInitiative,
    Artifact,
    ChangeReview
)
from backend.app.services.workspace_sync import (
    sanitize_dirname,
    get_stage_dir_name,
    get_run_dir_name,
)
from backend.app.services.diff_engine import analyze_changes_and_impact
from backend.app.services.workflow_engine import calculate_sha256

def calculate_bytes_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

async def process_and_save_bundle_artifact(
    db: AsyncSession,
    module_id: str,
    filename: str,
    file_bytes: bytes,
    change_summary: Optional[str] = None
) -> Tuple[Artifact, ChangeReview]:
    """
    Saves an uploaded artifact (single markdown, HTML bundle, or ZIP prototype archive).
    - Extracts zip archives containing index.html, assets, preview.
    - Preserves immutable versioning under physical workspace: versions/v{N}/.
    - Generates ChangeReview with diff analysis in 'pending_approval' state.
    """
    stmt = (
        select(ModuleInstance)
        .options(
            selectinload(ModuleInstance.workflow_run)
            .selectinload(WorkflowRun.product)
            .selectinload(Product.initiative),
            selectinload(ModuleInstance.artifacts)
        )
        .where(ModuleInstance.id == module_id)
    )
    res = await db.execute(stmt)
    mod = res.scalar_one_or_none()
    if not mod:
        raise ValueError(f"Module {module_id} not found")

    run = mod.workflow_run
    prod = run.product
    init = prod.initiative

    # Compute next version number
    existing_versions = [a.version for a in mod.artifacts] if mod.artifacts else []
    next_ver = (max(existing_versions) + 1) if existing_versions else 1
    prev_artifact = next((a for a in mod.artifacts if a.version == (next_ver - 1)), None)
    if not prev_artifact and mod.artifacts:
        prev_artifact = mod.artifacts[0]

    # Workspace directory setup
    init_dir = sanitize_dirname(init.id if init else "standalone")
    prod_dir = sanitize_dirname(prod.code)
    run_dir = get_run_dir_name(run.name, run.id)
    mod_dir = get_stage_dir_name(mod.order_index, mod.module_code, mod.name)
    
    version_dir = settings.WORKSPACE_DIR / init_dir / "products" / prod_dir / run_dir / mod_dir / "versions" / f"v{next_ver}"
    version_dir.mkdir(parents=True, exist_ok=True)

    is_zip = filename.lower().endswith(".zip")
    is_html = filename.lower().endswith(".html") or filename.lower().endswith(".htm")

    artifact_type = "markdown"
    entry_file = "index.html"
    content_text = ""
    storage_rel_path = None

    if is_zip:
        artifact_type = "html_bundle"
        # Extract zip contents
        with zipfile.ZipFile(io.BytesIO(file_bytes), 'r') as zf:
            zf.extractall(version_dir)

        # Look for entry index.html
        if (version_dir / "index.html").exists():
            entry_file = "index.html"
            content_text = (version_dir / "index.html").read_text(encoding="utf-8", errors="replace")[:20000]
        else:
            # Check subdirectories for index.html
            candidates = list(version_dir.glob("**/index.html"))
            if candidates:
                rel = candidates[0].relative_to(version_dir)
                entry_file = str(rel)
                content_text = candidates[0].read_text(encoding="utf-8", errors="replace")[:20000]
            else:
                entry_file = "index.html"
                content_text = f"# 交付包 v{next_ver}\n包含资产文件 {len(list(version_dir.iterdir()))} 项。"

        storage_rel_path = str(version_dir.relative_to(settings.WORKSPACE_DIR))
    elif is_html:
        artifact_type = "html_bundle"
        dest_file = version_dir / filename
        dest_file.write_bytes(file_bytes)
        entry_file = filename
        content_text = file_bytes.decode("utf-8", errors="replace")
        storage_rel_path = str(version_dir.relative_to(settings.WORKSPACE_DIR))
    else:
        # Standard markdown or text document
        artifact_type = "markdown"
        dest_file = version_dir / filename
        dest_file.write_bytes(file_bytes)
        content_text = file_bytes.decode("utf-8", errors="replace")
        storage_rel_path = str(version_dir.relative_to(settings.WORKSPACE_DIR))

    content_hash = calculate_bytes_sha256(file_bytes)

    # Create Artifact record
    artifact = Artifact(
        module_id=mod.id,
        title=f"{mod.name} 交付物 v{next_ver}",
        version=next_ver,
        artifact_type=artifact_type,
        content=content_text,
        storage_rel_path=storage_rel_path,
        entry_file=entry_file,
        change_summary=change_summary,
        content_hash=content_hash,
        is_baseline=False # Not active baseline until approved by lead!
    )
    db.add(artifact)
    await db.flush()

    # Generate Diff & ChangeReview
    prev_content = prev_artifact.content if prev_artifact else None
    diff_summary, impact_list = analyze_changes_and_impact(
        module_code=mod.module_code,
        prev_content=prev_content,
        new_content=content_text,
        human_change_summary=change_summary
    )

    change_review = ChangeReview(
        module_id=mod.id,
        artifact_id=artifact.id,
        from_version=(prev_artifact.version if prev_artifact else 0),
        to_version=next_ver,
        title=f"【{mod.name}】v{next_ver} 变更审批单",
        diff_summary=diff_summary,
        impact_analysis=impact_list,
        status="pending_approval" # 统一审批流：等待我统一审批
    )
    db.add(change_review)
    await db.commit()
    await db.refresh(artifact)
    await db.refresh(change_review)

    return artifact, change_review
