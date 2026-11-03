"""
DesignAdapter (设计资产适配层)

把 Sketch MeaXure 导出包和设计 Agent 已经写好的画板收成同一套设计交付包。
只保留来源里的画板文件，不用演示模板补页。

Canonical Design Bundle 目录结构：
    index.html              # MeaXure 经典三栏检视工作台
    manifest.json           # 项目与画板元数据总表 (MeaXure 标准)
    tokens.json             # W3C 标准设计令牌 (color, typography, spacing, radius)
    screens/{id}.html       # 高保真画板库 (每个工序 04 视图 id 一张可交互页面)
    slices/*.svg            # 矢量切片/图标资源库
    delivery.manifest.json  # ModuFlow 工序契约清单
"""
import json
import re
import shutil
import zipfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.app.services.design_bundle import VIEW_ID, required_platforms
from backend.app.services.design_bundle_sim import TOKENS


def _artboard_view_id(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    for key in ("slug", "id", "view_id"):
        value = str(item.get(key) or "").strip().lower()
        if VIEW_ID.fullmatch(value):
            return value
    return ""


def _discover_view_ids(root: Path, artboards: Any) -> List[str]:
    found: List[str] = []
    if isinstance(artboards, list):
        for item in artboards:
            view_id = _artboard_view_id(item)
            if view_id and view_id not in found:
                found.append(view_id)
    screens = root / "screens"
    if screens.is_dir():
        for path in sorted(screens.glob("*.html")):
            if VIEW_ID.fullmatch(path.stem) and path.stem not in found:
                found.append(path.stem)
    return found


def _find_artboard_html(root: Path, view_id: str) -> Optional[Path]:
    preferred = [
        root / "screens" / f"{view_id}.html",
        root / "artboards" / f"{view_id}.html",
        root / f"{view_id}.html",
    ]
    for path in preferred:
        if path.is_file():
            return path
    found = sorted(
        (path for path in root.rglob(f"{view_id}.html") if path.is_file()),
        key=lambda path: len(path.parts),
    )
    return found[0] if found else None


def _place_source_screens(source: Path, target: Path, view_ids: List[str]) -> Tuple[List[str], List[str]]:
    """Copy artboard HTML that already exists. Missing ids stay missing."""
    screens_dir = target / "screens"
    screens_dir.mkdir(parents=True, exist_ok=True)
    kept: List[str] = []
    missing: List[str] = []
    staged: List[Tuple[str, str]] = []
    for view_id in view_ids:
        src = _find_artboard_html(source, view_id)
        if src is None:
            missing.append(view_id)
            continue
        staged.append((view_id, src.read_text(encoding="utf-8")))
    for view_id, html in staged:
        (screens_dir / f"{view_id}.html").write_text(html, encoding="utf-8")
        kept.append(view_id)
    return kept, missing


def _ensure_workbench(source: Path, target: Path, name: str, views: List[str], platforms: List[str]) -> None:
    from backend.app.services.design_bundle_sim import _workbench_html

    dest = target / "index.html"
    src = source / "index.html"
    existing = src.read_text(encoding="utf-8", errors="replace") if src.is_file() else ""
    if not views:
        if existing and src.resolve() != dest.resolve():
            dest.write_text(existing, encoding="utf-8")
        return
    listed = all(f"screens/{view_id}.html" in existing for view_id in views)
    if existing and listed:
        if src.resolve() != dest.resolve():
            dest.write_text(existing, encoding="utf-8")
        return
    dest.write_text(_workbench_html(name, views, platforms), encoding="utf-8")


def _write_import_note(target: Path, kept: List[str], missing: List[str]) -> None:
    path = target / "交付物_05_设计实现.md"
    if path.is_file():
        return
    lines = ["# 设计导入", "", "画板来自上传的设计文件。"]
    lines.append("已收录：" + ("、".join(kept) if kept else "无"))
    if missing:
        lines.append("缺少：" + "、".join(missing))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class BaseDesignAdapter(ABC):
    """设计资产适配器基类"""

    @abstractmethod
    def can_adapt(self, source_path: Path) -> bool:
        """判断是否可以处理该源文件或目录"""
        pass

    @abstractmethod
    def adapt(
        self,
        source_path: Path,
        target_dir: Path,
        product_name: str = "当前产品",
        platform: str = "cross_platform",
        views: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """将源文件解析并输出为 Canonical Design Bundle，返回适配结果元数据"""
        pass


class SketchMeaXureAdapter(BaseDesignAdapter):
    """
    Sketch MeaXure 导出包适配器。
    支持解压并适配由 Sketch MeaXure / Sketch Measure 插件导出的 ZIP 包或解压目录。
    """

    def can_adapt(self, source_path: Path) -> bool:
        if not source_path.exists():
            return False
        if source_path.is_file() and source_path.suffix.lower() == ".zip":
            try:
                with zipfile.ZipFile(source_path, "r") as zf:
                    names = zf.namelist()
                    # MeaXure 标志性文件：manifest.json 或 index.html + slices/ 或 data/
                    has_manifest = any("manifest.json" in n for n in names)
                    has_slices = any("slices/" in n for n in names)
                    has_meaxure_index = any("index.html" in n for n in names)
                    return has_manifest or (has_slices and has_meaxure_index)
            except Exception:
                return False
        if source_path.is_dir():
            # 若已包含 ModuFlow 工序契约或 screens/ 目录，则属于 AI 原生设计工作区
            if (source_path / "delivery.manifest.json").is_file() or (source_path / "screens").is_dir():
                return False
            has_manifest = (source_path / "manifest.json").is_file()
            has_slices = (source_path / "slices").is_dir()
            has_index = (source_path / "index.html").is_file()
            return has_manifest or (has_slices and has_index)
        return False

    def adapt(
        self,
        source_path: Path,
        target_dir: Path,
        product_name: str = "当前产品",
        platform: str = "cross_platform",
        views: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        target_dir.mkdir(parents=True, exist_ok=True)
        platforms = required_platforms(platform) or ["ios"]

        extracted_dir: Optional[Path] = None
        temp_cleanup = False
        if source_path.is_file() and source_path.suffix.lower() == ".zip":
            import tempfile

            extracted_dir = Path(tempfile.mkdtemp(prefix="meaxure_extract_"))
            temp_cleanup = True
            with zipfile.ZipFile(source_path, "r") as zf:
                zf.extractall(extracted_dir)
        else:
            extracted_dir = source_path

        try:
            # 1. 解析 MeaXure manifest.json
            meaxure_manifest: Dict[str, Any] = {}
            candidate_manifests = list(extracted_dir.glob("**/manifest.json"))
            if candidate_manifests:
                try:
                    meaxure_manifest = json.loads(candidate_manifests[0].read_text(encoding="utf-8"))
                except Exception:
                    meaxure_manifest = {}

            # 2. 提取色彩与构建 tokens.json。只收录导出包里的颜色。
            extracted_colors: Dict[str, str] = {}
            if isinstance(meaxure_manifest.get("colors"), list):
                for idx, c in enumerate(meaxure_manifest["colors"]):
                    hex_val = c.get("hex") if isinstance(c, dict) else (c if isinstance(c, str) else None)
                    if hex_val and re.match(r"^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})$", hex_val):
                        name = (c.get("name") if isinstance(c, dict) else f"color_{idx + 1}") or f"color_{idx + 1}"
                        clean_name = re.sub(r"[^a-zA-Z0-9_]", "_", name).lower()
                        extracted_colors[clean_name] = hex_val.upper()

            tokens = {
                "color": extracted_colors,
                "typography": TOKENS["typography"],
                "spacing": TOKENS["spacing"],
                "radius": TOKENS["radius"],
            }
            (target_dir / "tokens.json").write_text(json.dumps(tokens, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            # 3. 复制与对齐 slices/ 切片
            slices_dir = target_dir / "slices"
            slices_dir.mkdir(parents=True, exist_ok=True)
            found_slices: List[str] = []

            # 搜寻解压目录里的 slices
            source_slices_dirs = list(extracted_dir.glob("**/slices"))
            if source_slices_dirs:
                src_sl = source_slices_dirs[0]
                for file_p in src_sl.glob("*.*"):
                    if file_p.is_file():
                        dest_file = slices_dir / file_p.name
                        if file_p.resolve() != dest_file.resolve():
                            shutil.copy2(file_p, dest_file)
                        found_slices.append(f"slices/{file_p.name}")

            # 4. 保留导出包里的画板。没有对应 HTML 的视图不另写演示页。
            artboards = meaxure_manifest.get("artboards", [])
            requested = [view_id for view_id in (views or []) if VIEW_ID.fullmatch(view_id)]
            if not requested:
                requested = _discover_view_ids(extracted_dir, artboards)
            kept, missing = _place_source_screens(extracted_dir, target_dir, requested)

            # 5. 工作台只收录已经留下的画板
            _ensure_workbench(extracted_dir, target_dir, product_name, kept, platforms)

            # 6. 生成标准 manifest.json (MeaXure 格式)
            meaxure_out_manifest = {
                "project": product_name,
                "scale": meaxure_manifest.get("scale", 3),
                "unit": meaxure_manifest.get("unit", "pt"),
                "colors": extracted_colors,
                "artboards": [
                    {"id": v, "name": f"{v} 画板", "width": 393, "height": 852} for v in kept
                ],
                "slices": [s.replace("slices/", "") for s in found_slices],
            }
            (target_dir / "manifest.json").write_text(json.dumps(meaxure_out_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            # 7. 生成 ModuFlow 工序契约清单 delivery.manifest.json
            from backend.app.services.delivery_contract import CONTRACT_VERSION, RISK_FLAG_KEYS

            delivery_manifest = {
                "contract_version": CONTRACT_VERSION,
                "stage": "05",
                "artifacts": [
                    {"role": "design_spec", "path": "交付物_05_设计实现.md"},
                    {"role": "design_workbench", "path": "index.html"},
                    {"role": "design_tokens", "path": "tokens.json"},
                    {"role": "meaxure_manifest", "path": "manifest.json"},
                ] + [{"role": "design_screen", "path": f"screens/{v}.html"} for v in kept],
                "risk_flags": {k: False for k in RISK_FLAG_KEYS},
                "design": {
                    "platform": platform,
                    "entry": "index.html",
                    "tokens_path": "tokens.json",
                    "screens": [{"view_id": v, "path": f"screens/{v}.html", "platforms": platforms} for v in kept],
                    "icons": [s for s in found_slices if s.endswith(".svg")],
                    "slices": found_slices,
                },
            }
            (target_dir / "delivery.manifest.json").write_text(json.dumps(delivery_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            _write_import_note(target_dir, kept, missing)

            return {
                "adapter": "SketchMeaXureAdapter",
                "product_name": product_name,
                "platform": platform,
                "views": kept,
                "missing_views": missing,
                "slices_count": len(found_slices),
                "target_dir": str(target_dir),
            }
        finally:
            if temp_cleanup and extracted_dir and extracted_dir.exists():
                shutil.rmtree(extracted_dir, ignore_errors=True)


class NativeAIAgentAdapter(BaseDesignAdapter):
    """
    AI Agent (ux) 原生生成设计产物适配器。
    用于规范化、自愈补充并编译 AI 在工作区直接落盘的 HTML/Tokens 资产。
    """

    def can_adapt(self, source_path: Path) -> bool:
        if not source_path.is_dir():
            return False
        # 如果包含 screens/ 目录，或者包含 tokens.json，或者包含 index.html
        return (
            (source_path / "screens").is_dir()
            or (source_path / "tokens.json").is_file()
            or (source_path / "index.html").is_file()
        )

    def adapt(
        self,
        source_path: Path,
        target_dir: Path,
        product_name: str = "当前产品",
        platform: str = "cross_platform",
        views: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        target_dir.mkdir(parents=True, exist_ok=True)
        platforms = required_platforms(platform) or ["ios"]
        requested = [view_id for view_id in (views or []) if VIEW_ID.fullmatch(view_id)]
        if not requested:
            requested = _discover_view_ids(source_path, [])

        tokens_file = target_dir / "tokens.json"
        src_tokens = source_path / "tokens.json"
        if src_tokens.is_file() and src_tokens.resolve() != tokens_file.resolve():
            shutil.copy2(src_tokens, tokens_file)

        slices_dir = target_dir / "slices"
        slices_dir.mkdir(parents=True, exist_ok=True)
        src_slices = source_path / "slices"
        if src_slices.is_dir() and src_slices.resolve() != slices_dir.resolve():
            for f in src_slices.glob("*.*"):
                if f.is_file():
                    shutil.copy2(f, slices_dir / f.name)

        src_icons = source_path / "assets" / "icons"
        if src_icons.is_dir():
            for f in src_icons.glob("*.svg"):
                dest = slices_dir / f.name
                if not dest.exists():
                    shutil.copy2(f, dest)

        kept, missing = _place_source_screens(source_path, target_dir, requested)
        _ensure_workbench(source_path, target_dir, product_name, kept, platforms)

        manifest_file = target_dir / "manifest.json"
        src_manifest = source_path / "manifest.json"
        if src_manifest.is_file() and src_manifest.resolve() != manifest_file.resolve():
            shutil.copy2(src_manifest, manifest_file)
        elif not manifest_file.exists() and kept:
            manifest_data = {
                "project": product_name,
                "scale": 3,
                "unit": "pt",
                "artboards": [{"id": v, "name": f"{v} 画板", "width": 393, "height": 852} for v in kept],
                "slices": [f.name for f in slices_dir.glob("*.svg")],
            }
            manifest_file.write_text(json.dumps(manifest_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        from backend.app.services.delivery_contract import CONTRACT_VERSION, RISK_FLAG_KEYS

        all_icons = [f"slices/{f.name}" for f in sorted(slices_dir.glob("*.svg"))]
        manifest_contract = {
            "contract_version": CONTRACT_VERSION,
            "stage": "05",
            "artifacts": [
                {"role": "design_spec", "path": "交付物_05_设计实现.md"},
                {"role": "design_workbench", "path": "index.html"},
                {"role": "design_tokens", "path": "tokens.json"},
                {"role": "meaxure_manifest", "path": "manifest.json"},
            ] + [{"role": "design_screen", "path": f"screens/{v}.html"} for v in kept],
            "risk_flags": {k: False for k in RISK_FLAG_KEYS},
            "design": {
                "platform": platform,
                "entry": "index.html",
                "tokens_path": "tokens.json",
                "screens": [{"view_id": v, "path": f"screens/{v}.html", "platforms": platforms} for v in kept],
                "icons": all_icons,
                "slices": all_icons,
            },
        }
        (target_dir / "delivery.manifest.json").write_text(
            json.dumps(manifest_contract, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        doc_file = target_dir / "交付物_05_设计实现.md"
        src_doc = source_path / "交付物_05_设计实现.md"
        if src_doc.is_file() and src_doc.resolve() != doc_file.resolve():
            shutil.copy2(src_doc, doc_file)
        else:
            _write_import_note(target_dir, kept, missing)

        return {
            "adapter": "NativeAIAgentAdapter",
            "product_name": product_name,
            "platform": platform,
            "views": kept,
            "missing_views": missing,
            "target_dir": str(target_dir),
        }


# 适配器注册与分发引擎
ADAPTERS: List[BaseDesignAdapter] = [
    SketchMeaXureAdapter(),
    NativeAIAgentAdapter(),
]


def resolve_design_adapter(source_path: Path) -> Optional[BaseDesignAdapter]:
    """根据源文件特征自动匹配最适宜的设计适配器"""
    for adapter in ADAPTERS:
        if adapter.can_adapt(source_path):
            return adapter
    return None


def adapt_to_canonical_bundle(
    source_path: Path,
    target_dir: Path,
    product_name: str = "当前产品",
    platform: str = "cross_platform",
    views: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """主分发函数：将任意源转换为 Canonical Design Bundle"""
    adapter = resolve_design_adapter(source_path)
    if not adapter:
        # 回退至 AI Agent 兜底适配
        adapter = NativeAIAgentAdapter()
    return adapter.adapt(
        source_path=source_path,
        target_dir=target_dir,
        product_name=product_name,
        platform=platform,
        views=views,
    )
