"""
工序 06 设计交付包：确定性校验器。

交付包是一个可以直接在成果交付库里点开体验的设计稿文件夹：

    index.html            设计工作台（入口）：画板切换、平台切换、四态切换、点选标注、令牌与图标库
    tokens.json           设计令牌唯一真理源（color / typography / spacing / radius）
    screens/V-xx.html     每个 PRD 视图一张高保真视觉稿，页面之间可以点击跳转
    assets/icons/*.svg    图标资源

页面标注约定（校验器读的就是这些属性）：
    data-device="ios|android"   设备外框。data-safe-top / data-safe-bottom 是该外框的顶部、底部安全区（iOS pt，Android dp）
    data-hit="WxH"              可点击元素由 CSS 保证的最小热区（iOS pt，Android dp）
    data-state="default|loading|empty|error"   四态面板
    data-nav-target="V-xx"      点击后跳转的视图

校验器不跑浏览器，只做静态检查：属性是否齐全、数值是否达标、颜色是否来自 tokens.json、
链接和资源是否存在、是否零外部依赖。像素级实测留给后续阶段。
"""
import json
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

REQUIRED_STATES = ("default", "loading", "empty", "error")
VIEW_ID = re.compile(r"V-\d{2}")
HIT_RE = re.compile(r"^(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)$")
HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
CSS_URL_RE = re.compile(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)|@import\s+['\"]?([^'\";)]+)", re.I)
MIN_SCREEN_CHARS = 2000

IOS_MIN_TOP_PT = 71
IOS_MIN_BOTTOM_PT = 34
IOS_MIN_HIT = 44
ANDROID_MIN_TOP_DP = 24
ANDROID_MIN_HIT = 48

_VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
_SKIP_COLOR_ATTRS = {"href", "src", "id", "class", "data-nav-target", "data-hit"}


def _norm_hex(value: str) -> str:
    raw = value.lstrip("#").lower()
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    return "#" + raw


def _is_external(value: str) -> bool:
    text = (value or "").strip().lower()
    return text.startswith(("http://", "https://", "//"))


def _number(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def required_platforms(platform: str) -> List[str]:
    from backend.app.services.profile_guard import covers_android, covers_ios

    found: List[str] = []
    if covers_ios(platform):
        found.append("ios")
    if covers_android(platform):
        found.append("android")
    return found


class _ScreenScan(HTMLParser):
    """Collects the facts the design contract checks from one screen file."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.devices: List[Dict[str, Any]] = []
        self.interactive: List[Dict[str, Any]] = []
        self.states: set = set()
        self.nav_targets: List[str] = []
        self.href_pages: List[str] = []
        self.colors: set = set()
        self.local_refs: List[str] = []
        self.external: List[str] = []
        self.has_script = False
        self._stack: List[Tuple[str, Optional[str]]] = []
        self._in_style = False

    def _current_platform(self) -> Optional[str]:
        for _, platform in reversed(self._stack):
            if platform:
                return platform
        return None

    def _scan_css(self, css: str) -> None:
        for match in HEX_RE.finditer(css):
            self.colors.add(_norm_hex(match.group(0)))
        for match in CSS_URL_RE.finditer(css):
            target = (match.group(1) or match.group(2) or "").strip()
            if _is_external(target):
                self.external.append(target)

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        attr = {key: (value or "") for key, value in attrs}
        if tag == "script":
            self.has_script = True
            if _is_external(attr.get("src", "")):
                self.external.append(attr["src"])
        if tag == "style":
            self._in_style = True
        if tag == "link" and _is_external(attr.get("href", "")):
            self.external.append(attr["href"])

        device = attr.get("data-device", "").strip().lower() or None
        if device:
            self.devices.append({
                "platform": device,
                "safe_top": _number(attr.get("data-safe-top")),
                "safe_bottom": _number(attr.get("data-safe-bottom")),
            })
        state = attr.get("data-state", "").strip().lower()
        if state:
            self.states.add(state)
        nav = attr.get("data-nav-target", "").strip()
        if nav:
            self.nav_targets.append(nav)

        for key, value in attr.items():
            if key in ("href", "src", "action") and value:
                if _is_external(value):
                    self.external.append(value)
                elif not value.startswith(("#", "data:", "javascript:", "mailto:")):
                    if key == "href" and value.endswith(".html"):
                        self.href_pages.append(value)
                    elif key == "src":
                        self.local_refs.append(value)
            if key == "style":
                self._scan_css(value)
            elif key not in _SKIP_COLOR_ATTRS:
                for match in HEX_RE.finditer(value):
                    self.colors.add(_norm_hex(match.group(0)))

        platform_here = device or self._current_platform()
        is_interactive = (
            tag in ("button", "select", "textarea")
            or (tag == "input" and attr.get("type", "").lower() != "hidden")
            or (tag == "a" and "href" in attr)
            or attr.get("role", "").lower() == "button"
            or "onclick" in attr
            or bool(nav)
        )
        if is_interactive and platform_here:
            self.interactive.append({"tag": tag, "platform": platform_here, "hit": attr.get("data-hit", "").strip()})
        elif is_interactive:
            self.interactive.append({"tag": tag, "platform": None, "hit": attr.get("data-hit", "").strip()})

        if tag not in _VOID_TAGS:
            self._stack.append((tag, device))

    def handle_startendtag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in _VOID_TAGS and self._stack and self._stack[-1][0] == tag:
            self._stack.pop()

    def handle_endtag(self, tag: str) -> None:
        if tag == "style":
            self._in_style = False
        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index][0] == tag:
                del self._stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if self._in_style:
            self._scan_css(data)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _confined(root: Path, rel: str) -> Optional[Path]:
    text = (rel or "").strip()
    if not text or text.startswith(("/", "\\")) or ".." in Path(text).parts:
        return None
    base = root.resolve()
    target = (base / text).resolve()
    if target != base and base not in target.parents:
        return None
    return target


def _load_tokens(root: Path, tokens_path: str, reasons: List[str]) -> set:
    path = _confined(root, tokens_path) if tokens_path else None
    if path is None or not path.is_file():
        reasons.append(f"design.tokens_path：未找到令牌文件 {tokens_path or '(空)'}")
        return set()
    try:
        data = json.loads(_read(path))
    except json.JSONDecodeError:
        reasons.append("tokens.json：不是合法 JSON")
        return set()
    if not isinstance(data, dict):
        reasons.append("tokens.json：顶层必须是对象")
        return set()
    for group in ("color", "typography", "spacing", "radius"):
        if not isinstance(data.get(group), dict) or not data[group]:
            reasons.append(f"tokens.json：缺少 {group} 令牌组")
    colors: set = set()
    color_group = data.get("color")
    if isinstance(color_group, dict):
        for name, value in color_group.items():
            if isinstance(value, str) and HEX_RE.fullmatch(value.strip()):
                colors.add(_norm_hex(value.strip()))
            else:
                reasons.append(f"tokens.json：color.{name} 必须是十六进制色值")
    return colors


def _check_icons(root: Path, icons: Any, reasons: List[str]) -> None:
    if not isinstance(icons, list) or not icons:
        reasons.append("design.icons：至少列出 1 个 SVG 图标（在 slices/ 或 assets/icons/）")
        return
    for item in icons:
        path = _confined(root, str(item))
        if path is None or not path.is_file():
            reasons.append(f"design.icons：未找到图标 {item}")
            continue
        if path.suffix.lower() != ".svg":
            reasons.append(f"design.icons：{item} 不是 SVG")
            continue
        try:
            tag = ET.fromstring(_read(path)).tag
        except ET.ParseError:
            reasons.append(f"design.icons：{item} 不是合法 SVG")
            continue
        if not tag.endswith("svg"):
            reasons.append(f"design.icons：{item} 根节点不是 svg")


def _check_screen(
    root: Path,
    view_id: str,
    path: Path,
    platforms: List[str],
    token_colors: set,
    known_views: set,
    measured: Dict[str, Any],
) -> List[str]:
    reasons: List[str] = []
    text = _read(path)
    label = f"{view_id}"
    if len(text) < MIN_SCREEN_CHARS:
        reasons.append(f"{label}：页面内容过短（{len(text)} 字符），不是完整视觉稿")
    scan = _ScreenScan()
    try:
        scan.feed(text)
        scan.close()
    except Exception:
        reasons.append(f"{label}：HTML 无法解析")
        return reasons

    for target in dict.fromkeys(scan.external):
        reasons.append(f"{label}：引用了外部资源 {target}，设计稿必须零外部依赖")
    for ref in dict.fromkeys(scan.local_refs):
        resolved = _confined(path.parent, ref.split("#")[0].split("?")[0])
        if resolved is None or not resolved.is_file() or root.resolve() not in resolved.parents:
            reasons.append(f"{label}：引用的资源不存在 {ref}")
    for page in dict.fromkeys(scan.href_pages):
        resolved = _confined(path.parent, page.split("#")[0].split("?")[0])
        if resolved is None or not resolved.is_file():
            reasons.append(f"{label}：跳转链接指向不存在的页面 {page}")
    for target in dict.fromkeys(scan.nav_targets):
        if target not in known_views:
            reasons.append(f"{label}：data-nav-target 指向未交付的视图 {target}")

    if token_colors:
        stray = sorted(color for color in scan.colors if color not in token_colors)
        if stray:
            reasons.append(f"{label}：使用了未登记在 tokens.json 的颜色 {', '.join(stray[:6])}")

    missing_states = [state for state in REQUIRED_STATES if state not in scan.states]
    if missing_states:
        reasons.append(f"{label}：缺少四态面板 {', '.join(missing_states)}（data-state）")
    if not any(item["tag"] for item in scan.interactive):
        reasons.append(f"{label}：页面没有任何可点击元素，无法体验交互")
    if not scan.has_script:
        reasons.append(f"{label}：缺少交互脚本，页面不能切换状态或跳转")

    seen_platforms = {device["platform"] for device in scan.devices}
    for platform in platforms:
        if platform not in seen_platforms:
            reasons.append(f"{label}：缺少 {platform} 设备外框（data-device=\"{platform}\"）")
    for device in scan.devices:
        platform = device["platform"]
        top, bottom = device["safe_top"], device["safe_bottom"]
        if platform == "ios":
            if top is None or top < IOS_MIN_TOP_PT:
                reasons.append(f"{label}：iOS 顶部安全区 {top}pt 低于 {IOS_MIN_TOP_PT}pt")
            if bottom is None or bottom < IOS_MIN_BOTTOM_PT:
                reasons.append(f"{label}：iOS 底部安全区 {bottom}pt 低于 {IOS_MIN_BOTTOM_PT}pt")
            if top is not None:
                measured["ios_top"] = min(measured.get("ios_top", top), top)
            if bottom is not None:
                measured["ios_bottom"] = min(measured.get("ios_bottom", bottom), bottom)
        elif platform == "android":
            if top is None or top < ANDROID_MIN_TOP_DP:
                reasons.append(f"{label}：Android 状态栏避让 {top}dp 低于 {ANDROID_MIN_TOP_DP}dp")
            if top is not None:
                measured["android_top"] = min(measured.get("android_top", top), top)
        else:
            reasons.append(f"{label}：未知设备外框 {platform}")

    bad_hits = 0
    for item in scan.interactive:
        platform = item["platform"]
        if platform is None:
            continue
        match = HIT_RE.match(item["hit"])
        if not match:
            bad_hits += 1
            continue
        width, height = float(match.group(1)), float(match.group(2))
        floor = IOS_MIN_HIT if platform == "ios" else ANDROID_MIN_HIT
        key = "ios_touch" if platform == "ios" else "android_touch"
        measured[key] = min(measured.get(key, min(width, height)), min(width, height))
        if width < floor or height < floor:
            unit = "pt" if platform == "ios" else "dp"
            reasons.append(f"{label}：{platform} 触控热区 {item['hit']} 低于 {floor}×{floor}{unit}（<{item['tag']}>）")
            break
    if bad_hits:
        reasons.append(f"{label}：{bad_hits} 个可点击元素缺少 data-hit=\"宽x高\" 热区标注")
    return reasons


def inspect_design_bundle(
    root: Optional[Path],
    design: Any,
    platform: str,
    upstream_views: Optional[Iterable[str]] = None,
) -> Tuple[List[str], Dict[str, Any]]:
    """Returns (reasons, measured). Empty reasons mean the bundle is a usable, experienceable design."""
    reasons: List[str] = []
    measured: Dict[str, Any] = {}
    if not isinstance(design, dict):
        return ["design：缺少设计交付包清单（entry、tokens_path、screens、icons）"], measured
    if root is None:
        return ["design：找不到本工序目录，无法校验设计交付包"], measured

    needed = required_platforms(platform)
    declared_platform = str(design.get("platform") or "").lower()
    if declared_platform and declared_platform != str(platform or "").lower():
        reasons.append(f"design.platform：声明 {declared_platform} 与项目 Profile {platform} 不一致")

    token_colors = _load_tokens(root, str(design.get("tokens_path") or ""), reasons)
    _check_icons(root, design.get("slices") or design.get("icons"), reasons)

    screens = design.get("screens")
    known_views: set = set()
    entries: List[Tuple[str, Path, List[str]]] = []
    if not isinstance(screens, list) or not screens:
        reasons.append("design.screens：至少交付 1 张视图画板")
        screens = []
    for index, item in enumerate(screens):
        if not isinstance(item, dict):
            reasons.append(f"design.screens[{index}]：需要 view_id、path、platforms")
            continue
        view_id = str(item.get("view_id") or "").strip()
        rel = str(item.get("path") or "").strip()
        if not VIEW_ID.fullmatch(view_id):
            reasons.append(f"design.screens[{index}].view_id：{view_id or '(空)'} 不是 V-xx 编号")
            continue
        if not rel.startswith("screens/") or not rel.endswith(".html"):
            reasons.append(f"design.screens[{index}].path：{view_id} 的页面必须放在 screens/ 下的 .html")
            continue
        path = _confined(root, rel)
        if path is None or not path.is_file():
            reasons.append(f"design.screens[{index}].path：未找到 {rel}")
            continue
        declared = [str(p).lower() for p in (item.get("platforms") or [])]
        missing_declared = [p for p in needed if p not in declared]
        if missing_declared:
            reasons.append(f"{view_id}：清单没有声明 {', '.join(missing_declared)} 画板")
        known_views.add(view_id)
        entries.append((view_id, path, needed))

    if upstream_views:
        absent = sorted(set(upstream_views) - known_views)
        if absent:
            reasons.append(f"design.screens：工序 05 的视图 {', '.join(absent)} 没有对应的视觉稿")

    for view_id, path, platforms in entries:
        reasons.extend(_check_screen(root, view_id, path, platforms, token_colors, known_views, measured))

    if entries and not any("data-nav-target" in _read(path) or ".html" in _read(path) for _, path, _ in entries):
        reasons.append("design.screens：页面之间没有任何跳转，无法体验完整流程")

    entry = str(design.get("entry") or "index.html")
    entry_path = _confined(root, entry)
    if entry_path is None or not entry_path.is_file():
        reasons.append(f"design.entry：未找到设计工作台入口 {entry}")
    else:
        html = _read(entry_path)
        if "<script" not in html.lower():
            reasons.append("design.entry：设计工作台缺少交互脚本")
        for view_id, path, _ in entries:
            rel = path.relative_to(root.resolve()).as_posix()
            if rel not in html:
                reasons.append(f"design.entry：设计工作台没有收录画板 {rel}")
        scan = _ScreenScan()
        try:
            scan.feed(html)
            scan.close()
        except Exception:
            reasons.append("design.entry：工作台 HTML 无法解析")
        else:
            for target in dict.fromkeys(scan.external):
                reasons.append(f"design.entry：引用了外部资源 {target}，必须零外部依赖")
    return reasons, measured


def validate_design_bundle(
    root: Optional[Path],
    design: Any,
    platform: str,
    upstream_views: Optional[Iterable[str]] = None,
) -> List[str]:
    return inspect_design_bundle(root, design, platform, upstream_views)[0]


def upstream_prd_views(root: Optional[Path]) -> List[str]:
    """工序 05 清单里的视图编号。06 目录的兄弟目录 05_* 里找 delivery.manifest.json。"""
    if root is None:
        return []
    parent = root.resolve().parent
    for sibling in sorted(parent.glob("05_*")):
        manifest = sibling / "delivery.manifest.json"
        if not manifest.is_file():
            continue
        try:
            data = json.loads(_read(manifest))
        except json.JSONDecodeError:
            continue
        views = data.get("views") if isinstance(data, dict) else None
        if isinstance(views, list):
            return [str(v) for v in views if VIEW_ID.fullmatch(str(v))]
    return []
