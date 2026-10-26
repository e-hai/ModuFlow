from typing import Dict, List, Any, Optional, Tuple, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.models.entities import ModuleInstance, Artifact

# Downstream modules sensitive to upstream changes
UPSTREAM_IMPACT_MAP = {
    "05": ["06", "07", "08"],       # PRD changes impact Design, Dev, QA
    "06": ["07", "08"],             # Design changes impact Dev, QA
    "07": ["08", "09"],             # Dev changes impact QA, Release
    "08": ["09"],                   # QA changes impact Release
}

# Reverse map: what upstream specifications does a module care about?
DOWNSTREAM_UPSTREAM_MAP = {
    "06": ["05"],
    "07": ["05", "06"],
    "08": ["05", "06", "07"],
    "09": ["08"],
}

def get_relevant_upstream_codes(module_code: str, declared_dependencies: Optional[List[str]] = None) -> Set[str]:
    codes = set(declared_dependencies or [])
    if module_code in DOWNSTREAM_UPSTREAM_MAP:
        codes.update(DOWNSTREAM_UPSTREAM_MAP[module_code])
    return codes

async def calculate_module_stale_status(
    db: AsyncSession,
    module: ModuleInstance,
    all_run_modules: Optional[List[ModuleInstance]] = None,
    artifacts_map: Optional[Dict[str, Artifact]] = None
) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Determines if a module is running on outdated upstream specifications.
    Returns (is_stale, stale_details).
    """
    if not module.is_unlocked:
        return False, []

    relevant_upstreams = get_relevant_upstream_codes(module.module_code, module.dependencies)
    if not relevant_upstreams:
        return False, []

    if all_run_modules is None:
        stmt = select(ModuleInstance).where(ModuleInstance.run_id == module.run_id)
        res = await db.execute(stmt)
        all_run_modules = res.scalars().all()

    modules_by_code = {m.module_code: m for m in all_run_modules}
    synced_versions = module.synced_upstream_versions or {}

    # Need baseline artifacts for upstreams
    needed_art_ids = [
        modules_by_code[c].baseline_artifact_id
        for c in relevant_upstreams
        if c in modules_by_code and modules_by_code[c].baseline_artifact_id
    ]

    if artifacts_map is None:
        artifacts_map = {}
        if needed_art_ids:
            art_stmt = select(Artifact).where(Artifact.id.in_(needed_art_ids))
            art_res = await db.execute(art_stmt)
            for a in art_res.scalars().all():
                artifacts_map[a.id] = a

    stale_details: List[Dict[str, Any]] = []

    for up_code in relevant_upstreams:
        up_mod = modules_by_code.get(up_code)
        if not up_mod or not up_mod.baseline_artifact_id:
            continue

        baseline_art = artifacts_map.get(up_mod.baseline_artifact_id)
        if not baseline_art:
            continue

        latest_version = baseline_art.version
        synced_version = synced_versions.get(up_code, 0)

        if latest_version > synced_version:
            stale_details.append({
                "upstream_module_id": up_mod.id,
                "upstream_code": up_mod.module_code,
                "upstream_name": up_mod.name,
                "current_synced_version": synced_version,
                "latest_upstream_version": latest_version,
                "artifact_id": baseline_art.id,
                "artifact_type": baseline_art.artifact_type,
                "message": f"上游【{up_mod.name}】已演进至基线 v{latest_version}（当前工序依据 v{synced_version}），存在待对齐的最新改动"
            })

    return (len(stale_details) > 0), stale_details
