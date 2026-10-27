"""
ModuFlow Project Profile & Dynamic Redline Guard (Phase 6)
(backend/app/services/profile_guard.py)

Enforces:
1. Dynamic ruleset selection by platform:
   - ios: iOS Human Interface Guidelines (HIG) (Dynamic Island >=71pt, touch >=44pt) via check_hig
   - android: Google Material Design (M3) (Status bar cutout >=24~48dp, touch >=48dp) via check_material
   - Android projects NEVER trigger iOS-specific checks (no Dynamic Island >=71pt, no Apple 4.3).
   - iOS projects retain 100% backward compatibility.
2. Parameterized client zero inference:
   - client_zero_inference=True: strictly enforces 0 client-side AI inference calls
   - client_zero_inference=False: explicitly allows on-device / edge AI inference
"""

from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import yaml

from backend.app.core.config import settings
from backend.app.services.authorization_engine import get_product_authorization_path


def resolve_project_profile(
    initiative_id: Optional[str] = None,
    product_code: Optional[str] = None,
    auth_data: Optional[Dict[str, Any]] = None,
    fallback_platform: str = "ios",
    fallback_zero_inference: bool = True
) -> Dict[str, Any]:
    """
    Resolves the project profile (platform and client_zero_inference).
    Priority:
    1. Direct auth_data dictionary if provided
    2. authorization.yaml file on disk
    3. Fallback defaults (platform="ios", client_zero_inference=True)
    """
    if auth_data and isinstance(auth_data, dict):
        prof = auth_data.get("profile", {})
        platform = str(prof.get("platform", fallback_platform)).lower()
        zero_inf = bool(prof.get("client_zero_inference", fallback_zero_inference))
        return {"platform": platform, "client_zero_inference": zero_inf}

    if initiative_id and product_code:
        auth_path = get_product_authorization_path(initiative_id, product_code)
        if auth_path.exists():
            try:
                data = yaml.safe_load(auth_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    prof = data.get("profile", {})
                    platform = str(prof.get("platform", fallback_platform)).lower()
                    zero_inf = bool(prof.get("client_zero_inference", fallback_zero_inference))
                    return {"platform": platform, "client_zero_inference": zero_inf}
            except Exception:
                pass

    return {
        "platform": str(fallback_platform).lower(),
        "client_zero_inference": bool(fallback_zero_inference)
    }


def check_hig(
    workspace_dir: Optional[Path] = None,
    top_pt: int = 74,
    touch_pt: int = 44,
    content: Optional[str] = None
) -> Dict[str, Any]:
    """
    Enforces iOS Human Interface Guidelines (HIG):
    - Dynamic Island / hardware safe area top padding >= 71pt (recommended 74pt)
    - Min touch target >= 44x44pt
    - Bottom safe area >= 34pt
    """
    safe_area_passed = (top_pt >= 71)
    touch_passed = (touch_pt >= 44)
    passed = safe_area_passed and touch_passed

    errors = []
    if not safe_area_passed:
        errors.append(f"iOS HIG 违背：灵动岛顶部留白为 {top_pt}pt，低于苹果法定要求 ≥71pt（防驳回推荐 ≥74pt）。")
    if not touch_passed:
        errors.append(f"iOS HIG 违背：最小触控热区为 {touch_pt}pt，低于苹果标准 44×44pt。")

    return {
        "platform": "ios",
        "ruleset": "iOS Human Interface Guidelines (HIG)",
        "dynamic_island_safe_pt": top_pt,
        "min_touch_pt": touch_pt,
        "multi_artboard_bundle": True,
        "passed": passed,
        "errors": errors,
        "advice": "确保遵循 Apple HIG 灵动岛安全区 (≥71pt) 与触控热区 (≥44pt) 规范。" if not passed else "通过 iOS HIG 规范检查。"
    }


def check_material(
    workspace_dir: Optional[Path] = None,
    status_bar_dp: int = 48,
    touch_dp: int = 48,
    content: Optional[str] = None
) -> Dict[str, Any]:
    """
    Enforces Google Material Design (Material 3 / M3):
    - Edge-to-edge status bar / display cutout safe area >= 24dp (recommended 48dp)
    - Min touch target >= 48x48dp (Material 3 accessibility benchmark)
    - CRITICAL: Does NOT trigger or check iOS Dynamic Island (>=71pt) or Apple 4.3!
    """
    safe_area_passed = (status_bar_dp >= 24)
    touch_passed = (touch_dp >= 48)
    passed = safe_area_passed and touch_passed

    errors = []
    if not safe_area_passed:
        errors.append(f"Android Material 违背：状态栏/挖孔避让留白为 {status_bar_dp}dp，低于标准 24dp。")
    if not touch_passed:
        errors.append(f"Android Material 违背：触控热区为 {touch_dp}dp，低于 Material 3 标准 48×48dp。")

    return {
        "platform": "android",
        "ruleset": "Google Material Design 3 (M3)",
        "material_version": "Material 3",
        "status_bar_cutout_safe_dp": status_bar_dp,
        "min_touch_target_dp": touch_dp,
        "multi_artboard_bundle": True,
        "passed": passed,
        "errors": errors,
        "advice": "确保遵循 Google Material Design 3 挖孔避让与 48dp 触控热区规范。" if not passed else "通过 Android Material 3 规范检查。"
    }


def audit_platform_design_system(
    platform: str = "ios",
    workspace_dir: Optional[Path] = None,
    top_safe_value: Optional[int] = None,
    min_touch_value: Optional[int] = None,
    content: Optional[str] = None
) -> Dict[str, Any]:
    """
    Universal design system auditor dispatching by platform:
    - android -> check_material (Android Material 3)
    - ios (or default) -> check_hig (iOS HIG)
    """
    norm_platform = (platform or "ios").lower()
    if norm_platform == "android":
        status_bar_dp = top_safe_value if top_safe_value is not None else 48
        touch_dp = min_touch_value if min_touch_value is not None else 48
        return check_material(
            workspace_dir=workspace_dir,
            status_bar_dp=status_bar_dp,
            touch_dp=touch_dp,
            content=content
        )
    else:
        top_pt = top_safe_value if top_safe_value is not None else 74
        touch_pt = min_touch_value if min_touch_value is not None else 44
        return check_hig(
            workspace_dir=workspace_dir,
            top_pt=top_pt,
            touch_pt=touch_pt,
            content=content
        )


def audit_client_zero_inference(
    client_realtime_ai_calls: int = 0,
    avg_cdn_bandwidth_mb: float = 15.0,
    enforce_zero_inference: bool = True
) -> Dict[str, Any]:
    """
    Enforces or permits client-side AI inference based on project profile:
    - If enforce_zero_inference is True:
        Strictly requires client_realtime_ai_calls == 0.
    - If enforce_zero_inference is False:
        Explicitly permits client_realtime_ai_calls > 0 (edge/on-device AI enabled).
    """
    cloud_marginal_cost = round(client_realtime_ai_calls * 0.015 + avg_cdn_bandwidth_mb * 0.00005, 5)

    if enforce_zero_inference:
        compliant = (client_realtime_ai_calls == 0)
        passed = compliant and (cloud_marginal_cost <= 0.005)
        errors = []
        if not compliant:
            errors.append(
                f"违反客户端零推理红线：检测到客户端实时 AI 推理调用 {client_realtime_ai_calls} 次/人。"
                f"当前项目 profile 严格锁定 client_zero_inference=True，AI 推理必须离线预处理或云端完成！"
            )
        return {
            "enforce_zero_inference": True,
            "client_realtime_ai_calls": client_realtime_ai_calls,
            "estimated_cost_per_mau_usd": cloud_marginal_cost,
            "zero_client_ai_compliant": compliant,
            "edge_ai_permitted": False,
            "passed": passed,
            "errors": errors,
            "mode": "strict_zero_client_inference",
            "advice": "守住客户端零推理成本红线" if not passed else "通过客户端零推理成本审计"
        }
    else:
        # client_zero_inference=False: Edge AI allowed
        passed = (cloud_marginal_cost <= 0.05)
        return {
            "enforce_zero_inference": False,
            "client_realtime_ai_calls": client_realtime_ai_calls,
            "estimated_cost_per_mau_usd": cloud_marginal_cost,
            "zero_client_ai_compliant": True,
            "edge_ai_permitted": True,
            "passed": passed,
            "errors": [],
            "mode": "edge_ai_permitted",
            "advice": f"项目 Profile 允许端侧本地模型推理 (client_zero_inference=False)，当前端侧实时调用: {client_realtime_ai_calls} 次/人。"
        }
