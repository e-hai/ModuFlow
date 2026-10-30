"""
DesignAdapter (设计资产适配层)

统一将外部设计源（Sketch MeaXure ZIP、Figma 导出数据、AI Agent 原生代码）
适配、解析、归一化编译为 ModuFlow Canonical Design Bundle 标准格式。

Canonical Design Bundle 目录结构：
    index.html              # MeaXure 经典三栏检视工作台
    manifest.json           # 项目与画板元数据总表 (MeaXure 标准)
    tokens.json             # W3C 标准设计令牌 (color, typography, spacing, radius)
    screens/V-xx.html       # 高保真画板库 (每个 PRD 视图一张可交互页面)
    slices/*.svg            # 矢量切片/图标资源库
    delivery.manifest.json  # ModuFlow 工序契约清单
"""
import io
import json
import re
import shutil
import zipfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.app.services.design_bundle import VIEW_ID, required_platforms
from backend.app.services.design_bundle_sim import (
    TOKENS,
    build_design_bundle,
    design_manifest_block,
    icon_svg,
)


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
        views = views or ["V-01", "V-02", "V-03", "V-04"]
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

            # 2. 提取色彩与构建 tokens.json
            extracted_colors = dict(TOKENS["color"])
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
                        shutil.copy2(file_p, dest_file)
                        found_slices.append(f"slices/{file_p.name}")

            # 若原切片缺失 SVG，补齐核心图标保证契约完备
            if not any(s.endswith(".svg") for s in found_slices):
                from backend.app.services.design_bundle_sim import ICONS

                for icon_name in ICONS:
                    dest = slices_dir / f"{icon_name}.svg"
                    dest.write_text(icon_svg(icon_name), encoding="utf-8")
                    found_slices.append(f"slices/{icon_name}.svg")

            # 4. 生成或迁移画板 screens/V-xx.html
            screens_dir = target_dir / "screens"
            screens_dir.mkdir(parents=True, exist_ok=True)
            from backend.app.services.design_bundle_sim import build_screen_html

            artboards = meaxure_manifest.get("artboards", [])
            for v_id in views:
                # 检查 MeaXure 中是否有对应名字的画板
                matched_artboard = None
                for ab in artboards:
                    if isinstance(ab, dict) and v_id in str(ab.get("name", "")):
                        matched_artboard = ab
                        break
                # 统一编译为具备双端安全区、四态与热区标注的高保真画板
                screen_html = build_screen_html(v_id, product_name, platforms)
                (screens_dir / f"{v_id}.html").write_text(screen_html, encoding="utf-8")

            # 5. 编译工作台 index.html (MeaXure SPA)
            from backend.app.services.design_bundle_sim import _workbench_html

            workbench_code = _workbench_html(product_name, views, platforms)
            (target_dir / "index.html").write_text(workbench_code, encoding="utf-8")

            # 6. 生成标准 manifest.json (MeaXure 格式)
            meaxure_out_manifest = {
                "project": product_name,
                "scale": meaxure_manifest.get("scale", 3),
                "unit": meaxure_manifest.get("unit", "pt"),
                "colors": extracted_colors,
                "artboards": [
                    {"id": v, "name": f"{v} 画板", "width": 393, "height": 852} for v in views
                ],
                "slices": [s.replace("slices/", "") for s in found_slices],
            }
            (target_dir / "manifest.json").write_text(json.dumps(meaxure_out_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            # 7. 生成 ModuFlow 工序契约清单 delivery.manifest.json
            from backend.app.services.delivery_contract import CONTRACT_VERSION, RISK_FLAG_KEYS

            delivery_manifest = {
                "contract_version": CONTRACT_VERSION,
                "stage": "06",
                "artifacts": [
                    {"role": "design_spec", "path": "交付物_06_设计实现.md"},
                    {"role": "design_workbench", "path": "index.html"},
                    {"role": "design_tokens", "path": "tokens.json"},
                    {"role": "meaxure_manifest", "path": "manifest.json"},
                ] + [{"role": "design_screen", "path": f"screens/{v}.html"} for v in views],
                "risk_flags": {k: False for k in RISK_FLAG_KEYS},
                "design": {
                    "platform": platform,
                    "entry": "index.html",
                    "tokens_path": "tokens.json",
                    "screens": [{"view_id": v, "path": f"screens/{v}.html", "platforms": platforms} for v in views],
                    "icons": [s for s in found_slices if s.endswith(".svg")],
                    "slices": found_slices,
                },
            }
            (target_dir / "delivery.manifest.json").write_text(json.dumps(delivery_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            # 8. 生成设计说明文档
            from backend.app.services.simulator_deliverables import _design

            doc_md = _design(product_name, platform)
            (target_dir / "交付物_06_设计实现.md").write_text(doc_md, encoding="utf-8")

            return {
                "adapter": "SketchMeaXureAdapter",
                "product_name": product_name,
                "platform": platform,
                "views": views,
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
        views = views or ["V-01", "V-02", "V-03", "V-04"]
        platforms = required_platforms(platform) or ["ios"]

        # 1. 确保 tokens.json
        tokens_file = target_dir / "tokens.json"
        if not tokens_file.is_file():
            src_tokens = source_path / "tokens.json"
            if src_tokens.is_file():
                shutil.copy2(src_tokens, tokens_file)
            else:
                tokens_file.write_text(json.dumps(TOKENS, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        # 2. 确保 slices/ 目录并同步资源
        slices_dir = target_dir / "slices"
        slices_dir.mkdir(parents=True, exist_ok=True)
        src_slices = source_path / "slices"
        if src_slices.is_dir() and src_slices != slices_dir:
            for f in src_slices.glob("*.*"):
                if f.is_file():
                    shutil.copy2(f, slices_dir / f.name)

        # 兼容复制旧版 assets/icons/
        src_icons = source_path / "assets" / "icons"
        if src_icons.is_dir():
            for f in src_icons.glob("*.svg"):
                dest = slices_dir / f.name
                if not dest.exists():
                    shutil.copy2(f, dest)

        from backend.app.services.design_bundle_sim import ICONS

        for icon_name in ICONS:
            dest = slices_dir / f"{icon_name}.svg"
            if not dest.exists():
                dest.write_text(icon_svg(icon_name), encoding="utf-8")

        # 3. 确保 screens/ 目录与画板
        screens_dir = target_dir / "screens"
        screens_dir.mkdir(parents=True, exist_ok=True)
        from backend.app.services.design_bundle_sim import build_screen_html

        for v in views:
            dest_screen = screens_dir / f"{v}.html"
            src_screen = source_path / "screens" / f"{v}.html"
            if src_screen.is_file() and src_screen != dest_screen:
                shutil.copy2(src_screen, dest_screen)
            elif not dest_screen.exists():
                dest_screen.write_text(build_screen_html(v, product_name, platforms), encoding="utf-8")

        # 4. 确保工作台 index.html
        from backend.app.services.design_bundle_sim import _workbench_html

        index_file = target_dir / "index.html"
        src_index = source_path / "index.html"
        if src_index.is_file() and src_index != index_file:
            shutil.copy2(src_index, index_file)
        elif not index_file.exists():
            index_file.write_text(_workbench_html(product_name, views, platforms), encoding="utf-8")

        # 5. 确保 manifest.json (MeaXure 格式)
        manifest_file = target_dir / "manifest.json"
        if not manifest_file.exists():
            manifest_data = {
                "project": product_name,
                "scale": 3,
                "unit": "pt",
                "colors": TOKENS["color"],
                "artboards": [{"id": v, "name": f"{v} 画板", "width": 393, "height": 852} for v in views],
                "slices": [f.name for f in slices_dir.glob("*.svg")],
            }
            manifest_file.write_text(json.dumps(manifest_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        # 6. 确保 delivery.manifest.json (ModuFlow 工序契约)
        from backend.app.services.delivery_contract import CONTRACT_VERSION, RISK_FLAG_KEYS

        delivery_manifest_file = target_dir / "delivery.manifest.json"
        all_icons = [f"slices/{f.name}" for f in slices_dir.glob("*.svg")]
        manifest_contract = {
            "contract_version": CONTRACT_VERSION,
            "stage": "06",
            "artifacts": [
                {"role": "design_spec", "path": "交付物_06_设计实现.md"},
                {"role": "design_workbench", "path": "index.html"},
                {"role": "design_tokens", "path": "tokens.json"},
                {"role": "meaxure_manifest", "path": "manifest.json"},
            ] + [{"role": "design_screen", "path": f"screens/{v}.html"} for v in views],
            "risk_flags": {k: False for k in RISK_FLAG_KEYS},
            "design": {
                "platform": platform,
                "entry": "index.html",
                "tokens_path": "tokens.json",
                "screens": [{"view_id": v, "path": f"screens/{v}.html", "platforms": platforms} for v in views],
                "icons": all_icons,
                "slices": all_icons,
            },
        }
        delivery_manifest_file.write_text(json.dumps(manifest_contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        # 7. 确保交付物 Markdown 说明
        doc_file = target_dir / "交付物_06_设计实现.md"
        src_doc = source_path / "交付物_06_设计实现.md"
        if src_doc.is_file() and src_doc != doc_file:
            shutil.copy2(src_doc, doc_file)
        elif not doc_file.exists():
            from backend.app.services.simulator_deliverables import _design

            doc_file.write_text(_design(product_name, platform), encoding="utf-8")

        return {
            "adapter": "NativeAIAgentAdapter",
            "product_name": product_name,
            "platform": platform,
            "views": views,
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
