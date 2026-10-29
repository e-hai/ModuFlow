"""
离线模拟器用的设计交付包生成器：输出一套能在成果交付库里点开体验的完整视觉稿。

每个视图一张画板（iOS、Android 各一个设备外框），含 Default / Loading / Empty / Error 四态，
页面之间可点击跳转；index.html 是设计工作台，可切换画板、平台、状态，打开标注层，
点选任意元素查看尺寸、字号、圆角和颜色。
"""
import json
from html import escape
from typing import Any, Dict, List, Optional

from backend.app.services.design_bundle import required_platforms

TOKENS: Dict[str, Any] = {
    "color": {
        "primary": "#0E8A5A",
        "primary_dark": "#0A6B46",
        "primary_soft": "#E3F4EC",
        "background": "#F8FAFC",
        "surface": "#FFFFFF",
        "text": "#0F172A",
        "text_muted": "#64748B",
        "border": "#E2E8F0",
        "danger": "#DC2626",
        "danger_soft": "#FEE2E2",
        "stage": "#1E293B",
    },
    "typography": {
        "title": {"size": 24, "weight": 700, "line": 30},
        "headline": {"size": 17, "weight": 600, "line": 24},
        "body": {"size": 15, "weight": 400, "line": 22},
        "caption": {"size": 12, "weight": 400, "line": 16},
    },
    "spacing": {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24},
    "radius": {"card": 12, "button": 12, "chip": 999},
}

_STROKE = 'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"'
ICONS: Dict[str, str] = {
    "grid": '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    "history": '<path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/><path d="M12 7v5l3 2"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    "share": '<path d="M12 3v12"/><path d="m7 8 5-5 5 5"/><path d="M5 14v5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5"/>',
    "download": '<path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 20h14"/>',
    "retry": '<path d="M21 12a9 9 0 1 1-3-6.7"/><path d="M21 4v5h-5"/>',
    "check": '<path d="m5 12 5 5 9-10"/>',
    "back": '<path d="m15 18-6-6 6-6"/>',
}


def icon_svg(name: str) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" {_STROKE}>{ICONS[name]}</svg>\n'


def _inline_icon(name: str) -> str:
    return f'<svg class="ico" aria-hidden="true" {_STROKE}>{ICONS[name]}</svg>'


_VIEW_TITLES = {"V-01": "模板列表", "V-02": "创作编辑", "V-03": "结果预览", "V-04": "历史记录"}
_VIEW_ICON = {"V-01": "grid", "V-02": "plus", "V-03": "check", "V-04": "history"}


def _view_title(view_id: str) -> str:
    return _VIEW_TITLES.get(view_id, f"视图 {view_id}")


def _btn(label: str, hit: int, cls: str = "", nav: str = "", state: str = "", toast: str = "", icon: str = "") -> str:
    attrs = f'class="btn {cls}" data-hit="{hit}x{hit}"'
    if nav:
        attrs += f' data-nav-target="{nav}"'
    if state:
        attrs += f' data-set-state="{state}"'
    if toast:
        attrs += f' data-toast="{escape(toast)}"'
    glyph = _inline_icon(icon) if icon else ""
    return f"<button {attrs}>{glyph}{escape(label)}</button>"


def _skeleton(rows: int) -> str:
    return "".join('<div class="card skeleton"><i></i><i></i><i class="short"></i></div>' for _ in range(rows))


def _notice(title: str, body: str, action: str, tone: str = "") -> str:
    return f'<div class="notice {tone}"><h3>{escape(title)}</h3><p>{escape(body)}</p>{action}</div>'


def _panels(view_id: str, hit: int) -> Dict[str, str]:
    """四态内容。hit 是平台热区下限，按钮 CSS 用同一个值保证最小尺寸。"""
    retry = _btn("重试", hit, "ghost", state="loading", icon="retry")
    if view_id == "V-01":
        cards = "".join(
            f'<button class="card tpl" data-hit="{hit}x{hit}" data-nav-target="V-02">'
            f'<span class="thumb t{i}"></span><span class="meta"><b>{title}</b><em>{desc}</em></span></button>'
            for i, (title, desc) in enumerate([("极简白底", "清爽留白，适合日常使用"), ("商务蓝灰", "稳重配色，适合正式场合"), ("暖色手账", "柔和纸感，适合记录生活")])
        )
        chips = "".join(_btn(label, hit, "chip" + (" on" if i == 0 else ""), toast=f"已筛选：{label}") for i, label in enumerate(["全部", "常用", "最新"]))
        return {
            "default": f'<div class="chips">{chips}</div><div class="list">{cards}</div>',
            "loading": _skeleton(3),
            "empty": _notice("还没有模板", "新建一个模板，下次可以直接使用。", _btn("新建模板", hit, nav="V-02", icon="plus")),
            "error": _notice("模板加载失败", "网络不稳定，请稍后重试。", retry, "danger"),
        }
    if view_id == "V-02":
        rows = "".join(
            f'<div class="row"><span>{label}</span>{_btn(value, hit, "chip", toast=f"{label}已切换为{value}")}</div>'
            for label, value in [("输出格式", "高清"), ("背景处理", "自动"), ("文件命名", "按日期")]
        )
        return {
            "default": f'<div class="card canvas"><span class="paper"></span></div>{rows}<div class="cta">{_btn("开始生成", hit, "primary", nav="V-03")}</div>',
            "loading": '<div class="notice"><div class="ring"></div><h3>正在处理</h3><p>通常需要几秒钟。</p></div>',
            "empty": _notice("请先选择素材", "还没有可处理的内容。", _btn("去选模板", hit, nav="V-01", icon="grid")),
            "error": _notice("素材无法读取", "请换一份素材再试。", _btn("重新选择", hit, "ghost", nav="V-01"), "danger"),
        }
    if view_id == "V-03":
        return {
            "default": (
                '<div class="card result"><span class="paper big"></span></div>'
                f'<div class="actions">{_btn("保存", hit, "primary", toast="已保存到本地", icon="download")}'
                f'{_btn("分享", hit, "ghost", toast="已复制分享链接", icon="share")}'
                f'{_btn("再来一次", hit, "ghost", nav="V-02", icon="retry")}</div>'
            ),
            "loading": _skeleton(2),
            "empty": _notice("暂无结果", "先去生成一份吧。", _btn("返回编辑", hit, nav="V-02")),
            "error": _notice("生成失败", "处理没有完成，不会产生任何扣费。", retry, "danger"),
        }
    if view_id == "V-04":
        items = "".join(
            f'<button class="card hist" data-hit="{hit}x{hit}" data-nav-target="V-03"><span class="thumb t{i}"></span>'
            f'<span class="meta"><b>{title}</b><em>{when}</em></span></button>'
            for i, (title, when) in enumerate([("文档 0042", "今天 09:12"), ("文档 0041", "昨天 18:40"), ("文档 0040", "周二 11:05")])
        )
        return {
            "default": f'<div class="list">{items}</div>',
            "loading": _skeleton(3),
            "empty": _notice("暂无历史", "完成第一次生成后会出现在这里。", _btn("去创作", hit, nav="V-02", icon="plus")),
            "error": _notice("历史记录加载失败", "请检查网络后重试。", retry, "danger"),
        }
    return {
        "default": f'<div class="card"><h3>{escape(_view_title(view_id))}</h3><p>核心内容区。</p></div><div class="cta">{_btn("返回模板", hit, "primary", nav="V-01")}</div>',
        "loading": _skeleton(2),
        "empty": _notice("暂无内容", "这里还没有数据。", _btn("返回模板", hit, nav="V-01")),
        "error": _notice("加载失败", "请稍后重试。", retry, "danger"),
    }


def _device(platform: str, view_id: str, name: str) -> str:
    ios = platform == "ios"
    hit = 44 if ios else 48
    safe_top, safe_bottom = (74, 34) if ios else (32, 0)
    unit = "pt" if ios else "dp"
    panels = _panels(view_id, hit)
    body = "".join(f'<div class="panel" data-state="{state}">{panels[state]}</div>' for state in ("default", "loading", "empty", "error"))
    tabs = "".join(
        f'<button class="tab{" on" if tab == view_id else ""}" data-hit="{hit}x{hit}" data-nav-target="{tab}">{_inline_icon(_VIEW_ICON[tab])}<span>{label}</span></button>'
        for tab, label in (("V-01", "模板"), ("V-04", "历史"))
    )
    back = (
        f'<button class="icon-btn" data-hit="{hit}x{hit}" data-nav-target="V-01" aria-label="返回">{_inline_icon("back")}</button>'
        if view_id in ("V-02", "V-03")
        else '<span class="icon-btn ghosted"></span>'
    )
    island = '<span class="island"></span>' if ios else '<span class="punch"></span>'
    label = "iOS · HIG" if ios else "Android · Material 3"
    return f"""
  <section class="device {platform}" data-device="{platform}" data-safe-top="{safe_top}" data-safe-bottom="{safe_bottom}">
    <span class="plat">{label}</span>
    <div class="safe-top" data-label="安全区 {safe_top}{unit}" style="height:{safe_top}px">{island}<span class="clock">9:41</span></div>
    <header class="appbar">{back}<h1>{escape(_view_title(view_id))}</h1><span class="icon-btn ghosted"></span></header>
    <main class="content">{body}</main>
    <nav class="tabbar">{tabs}</nav>
    <div class="safe-bottom" data-label="安全区 {safe_bottom}{unit}" style="height:{safe_bottom}px"></div>
    <div class="toast" role="status"></div>
  </section>"""


def _screen_css() -> str:
    c = TOKENS["color"]
    root = ";".join(f"--color-{key.replace('_', '-')}:{value}" for key, value in c.items())
    return f"""
:root{{{root};--r-card:12px;--r-btn:12px}}
*{{box-sizing:border-box;margin:0}}
body{{font-family:-apple-system,"SF Pro Text","Roboto","PingFang SC",sans-serif;background:var(--color-stage);color:var(--color-text);min-height:100vh;padding:16px;display:flex;flex-direction:column;align-items:center;gap:12px}}
.stagebar{{display:flex;gap:8px;align-items:center;color:var(--color-surface);font-size:13px;flex-wrap:wrap;justify-content:center}}
.stagebar b{{font-size:15px}}
.stagebar button{{border:1px solid var(--color-border);background:transparent;color:var(--color-surface);padding:6px 12px;border-radius:999px;font-size:12px;cursor:pointer;min-height:32px}}
.stagebar button.on{{background:var(--color-primary);border-color:var(--color-primary)}}
.stage{{display:flex;gap:32px;flex-wrap:wrap;justify-content:center;align-items:flex-start}}
body[data-platform="ios"] .device.android,body[data-platform="android"] .device.ios{{display:none}}
.device{{position:relative;width:393px;height:852px;background:var(--color-background);border-radius:44px;overflow:hidden;display:flex;flex-direction:column;box-shadow:0 0 0 10px var(--color-text),0 24px 60px rgba(0,0,0,.45)}}
.device.android{{width:412px;height:892px;border-radius:28px;--hit:48px}}
.device.ios{{--hit:44px}}
.plat{{position:absolute;top:6px;right:14px;font-size:10px;color:var(--color-text-muted);z-index:3}}
.safe-top{{position:relative;display:flex;align-items:flex-end;justify-content:space-between;padding:0 28px 8px;background:var(--color-surface);flex:none}}
.safe-top .clock{{font-size:15px;font-weight:600}}
.island{{position:absolute;left:50%;top:11px;width:120px;height:34px;margin-left:-60px;background:var(--color-text);border-radius:20px}}
.punch{{position:absolute;left:50%;top:10px;width:14px;height:14px;margin-left:-7px;background:var(--color-text);border-radius:50%}}
.appbar{{display:flex;align-items:center;justify-content:space-between;padding:4px 8px;background:var(--color-surface);border-bottom:1px solid var(--color-border);flex:none}}
.appbar h1{{font-size:17px;font-weight:600;line-height:24px}}
.android .appbar h1{{font-size:22px;font-weight:500}}
.icon-btn{{min-width:var(--hit);min-height:var(--hit);display:inline-flex;align-items:center;justify-content:center;border:0;background:transparent;color:var(--color-text);border-radius:999px;cursor:pointer}}
.icon-btn.ghosted{{cursor:default}}
.ico{{width:22px;height:22px;flex:none}}
.content{{flex:1;overflow:auto;padding:16px;display:flex;flex-direction:column;gap:12px}}
.panel{{display:none;flex-direction:column;gap:12px}}
body[data-state="default"] .panel[data-state="default"],body[data-state="loading"] .panel[data-state="loading"],body[data-state="empty"] .panel[data-state="empty"],body[data-state="error"] .panel[data-state="error"]{{display:flex}}
.card{{background:var(--color-surface);border:1px solid var(--color-border);border-radius:var(--r-card);padding:12px;display:flex;gap:12px;align-items:center;text-align:left;font:inherit;color:inherit}}
button.card{{width:100%;min-width:var(--hit);min-height:var(--hit);cursor:pointer}}
.list{{display:flex;flex-direction:column;gap:12px}}
.thumb{{width:56px;height:56px;border-radius:8px;background:var(--color-primary-soft);flex:none;border:1px solid var(--color-border)}}
.thumb.t1{{background:var(--color-border)}}.thumb.t2{{background:var(--color-danger-soft)}}
.meta{{display:flex;flex-direction:column;gap:2px}}.meta b{{font-size:15px;font-weight:600}}.meta em{{font-style:normal;font-size:12px;color:var(--color-text-muted)}}
.chips{{display:flex;gap:8px}}
.btn{{display:inline-flex;align-items:center;justify-content:center;gap:6px;min-width:var(--hit);min-height:var(--hit);padding:0 16px;border-radius:var(--r-btn);border:1px solid var(--color-border);background:var(--color-surface);color:var(--color-text);font:inherit;font-size:15px;font-weight:600;cursor:pointer}}
.btn.primary{{background:var(--color-primary);border-color:var(--color-primary);color:var(--color-surface);width:100%}}
.btn.primary:active{{background:var(--color-primary-dark)}}
.btn.ghost{{background:transparent;color:var(--color-primary);border-color:var(--color-primary)}}
.btn.chip{{border-radius:999px;font-size:13px;padding:0 14px}}
.btn.chip.on{{background:var(--color-primary-soft);border-color:var(--color-primary);color:var(--color-primary-dark)}}
.row{{display:flex;justify-content:space-between;align-items:center;background:var(--color-surface);border:1px solid var(--color-border);border-radius:var(--r-card);padding:6px 6px 6px 14px;font-size:15px}}
.canvas,.result{{justify-content:center;padding:20px}}
.paper{{width:150px;height:200px;background:var(--color-background);border:1px solid var(--color-border);border-radius:6px;box-shadow:0 6px 16px rgba(15,23,42,.12)}}
.paper.big{{width:200px;height:270px}}
.actions{{display:flex;flex-direction:column;gap:8px}}
.cta{{margin-top:auto}}
.notice{{display:flex;flex-direction:column;align-items:center;text-align:center;gap:8px;padding:40px 16px}}
.notice h3{{font-size:17px}}.notice p{{font-size:14px;color:var(--color-text-muted)}}
.notice.danger h3{{color:var(--color-danger)}}
.ring{{width:44px;height:44px;border-radius:50%;border:4px solid var(--color-primary-soft);border-top-color:var(--color-primary);animation:spin 1s linear infinite}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
.skeleton{{flex-direction:column;align-items:stretch}}
.skeleton i{{display:block;height:14px;border-radius:6px;background:var(--color-border);animation:pulse 1.2s ease-in-out infinite}}
.skeleton i.short{{width:55%}}
@keyframes pulse{{50%{{opacity:.45}}}}
.tabbar{{display:flex;border-top:1px solid var(--color-border);background:var(--color-surface);flex:none}}
.tab{{flex:1;min-height:var(--hit);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;border:0;background:transparent;font:inherit;font-size:11px;color:var(--color-text-muted);cursor:pointer;padding:6px 0}}
.tab.on{{color:var(--color-primary)}}
.android .tab{{font-size:12px}}
.safe-bottom{{background:var(--color-surface);flex:none}}
.toast{{position:absolute;left:50%;bottom:110px;transform:translateX(-50%);background:var(--color-text);color:var(--color-surface);padding:8px 14px;border-radius:999px;font-size:13px;opacity:0;pointer-events:none;transition:opacity .2s;max-width:80%}}
.toast.show{{opacity:1}}
body[data-anno="1"] [data-hit]{{outline:1px dashed var(--color-danger);outline-offset:-1px}}
body[data-anno="1"] .safe-top,body[data-anno="1"] .safe-bottom{{background:var(--color-danger-soft)}}
body[data-anno="1"] .safe-top::after,body[data-anno="1"] .safe-bottom::after{{content:attr(data-label);position:absolute;left:50%;transform:translateX(-50%);font-size:10px;color:var(--color-danger);white-space:nowrap}}
body[data-anno="1"] .safe-top::after{{bottom:2px}}
body[data-anno="1"] .safe-bottom{{position:relative}}
body[data-anno="1"] .safe-bottom::after{{top:2px}}
"""


_SCREEN_JS = """
(function(){
  var b=document.body, hash=location.hash.replace('#','').split(',');
  function apply(c){
    if(c.platform)b.dataset.platform=c.platform;
    if(c.state)b.dataset.state=c.state;
    if(typeof c.anno!=='undefined')b.dataset.anno=c.anno?'1':'0';
    var bar=document.querySelectorAll('.stagebar [data-set-state]');
    for(var i=0;i<bar.length;i++)bar[i].classList.toggle('on',bar[i].dataset.setState===b.dataset.state);
  }
  apply({platform:hash[0]||'all',state:hash[1]||'default',anno:hash[2]==='anno'});
  window.addEventListener('message',function(e){if(e.data&&e.data.type==='mf-config')apply(e.data);});
  function cfgHash(){return '#'+(b.dataset.platform||'all')+','+(b.dataset.state||'default')+(b.dataset.anno==='1'?',anno':'');}
  function toast(el,msg){var t=el.closest('.device').querySelector('.toast');if(!t)return;t.textContent=msg;t.classList.add('show');setTimeout(function(){t.classList.remove('show');},1600);}
  document.addEventListener('click',function(e){
    var el=e.target.closest('[data-nav-target],[data-set-state],[data-toast]');
    var pick=e.target.closest('[data-hit],.card,h1,h3,.thumb')||e.target;
    if(window.parent!==window&&pick.closest('.device')){
      var cs=getComputedStyle(pick),r=pick.getBoundingClientRect();
      window.parent.postMessage({type:'mf-pick',tag:pick.tagName.toLowerCase(),label:(pick.textContent||'').trim().slice(0,24),w:Math.round(r.width),h:Math.round(r.height),hit:pick.dataset.hit||'',font:cs.fontSize+' / '+cs.fontWeight,radius:cs.borderRadius,color:cs.color,bg:cs.backgroundColor},'*');
    }
    if(!el)return;
    if(el.dataset.toast)toast(el,el.dataset.toast);
    if(el.dataset.setState){
      var go=el.dataset.setState;apply({state:'loading'});
      setTimeout(function(){apply({state:'default'});},900);
      return;
    }
    if(el.dataset.navTarget){
      var next=el.dataset.navTarget;
      apply({state:'loading'});
      setTimeout(function(){location.href=next+'.html'+cfgHash();},350);
    }
  });
  if(window.parent!==window)window.parent.postMessage({type:'mf-nav',view:document.body.dataset.view},'*');
})();
"""


def build_screen_html(view_id: str, name: str, platforms: List[str]) -> str:
    # 舞台工具条里的状态按钮只切换预览态，不是设备内的界面元素
    bar_buttons = "".join(f'<button data-force-state="{s}">{l}</button>' for s, l in (("default", "默认"), ("loading", "加载"), ("empty", "空态"), ("error", "错误")))
    devices = "".join(_device(platform, view_id, name) for platform in platforms)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(view_id)} {escape(_view_title(view_id))} · {escape(name)}</title>
<style>{_screen_css()}</style>
</head>
<body data-view="{escape(view_id)}" data-platform="all" data-state="default" data-anno="0">
<div class="stagebar"><b>{escape(view_id)} {escape(_view_title(view_id))}</b><span>预览状态：</span>{bar_buttons}</div>
<div class="stage">{devices}
</div>
<script>
{_SCREEN_JS}
document.querySelectorAll('[data-force-state]').forEach(function(btn){{
  btn.addEventListener('click',function(){{document.body.dataset.state=btn.dataset.forceState;
    document.querySelectorAll('[data-force-state]').forEach(function(o){{o.classList.toggle('on',o===btn);}});}});
}});
</script>
</body>
</html>
"""


def _workbench_html(name: str, views: List[str], platforms: List[str]) -> str:
    nav = "".join(
        f'<button class="nav" data-view="{v}" data-src="screens/{v}.html">{escape(v)} · {escape(_view_title(v))}</button>' for v in views
    )
    plat_buttons = "".join(f'<button class="seg" data-platform="{p}">{"iOS" if p == "ios" else "Android"}</button>' for p in platforms)
    colors = "".join(
        f'<div class="sw"><i style="background:{value}"></i><span>{key}<br><code>{value}</code></span></div>'
        for key, value in TOKENS["color"].items()
    )
    type_rows = "".join(
        f'<tr><td>{key}</td><td>{v["size"]}/{v["line"]}</td><td>{v["weight"]}</td></tr>' for key, v in TOKENS["typography"].items()
    )
    icons = "".join(f'<div class="ic"><svg {_STROKE}>{ICONS[k]}</svg><span>{k}</span></div>' for k in ICONS)
    first = views[0]
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(name)} · 设计工作台</title>
<style>
*{{box-sizing:border-box;margin:0}}
body{{font-family:-apple-system,"PingFang SC",sans-serif;background:#0B1220;color:#E2E8F0;height:100vh;display:grid;grid-template-columns:200px 1fr 260px;grid-template-rows:48px 1fr;font-size:13px}}
header{{grid-column:1/4;display:flex;align-items:center;gap:10px;padding:0 14px;background:#111A2E;border-bottom:1px solid #223049}}
header b{{font-size:14px;margin-right:auto}}
button{{font:inherit;color:inherit;cursor:pointer}}
.seg,.nav{{background:transparent;border:1px solid #223049;border-radius:8px;padding:6px 10px}}
.seg.on,.nav.on{{background:#0E8A5A;border-color:#0E8A5A;color:#fff}}
aside{{background:#0F172A;border-right:1px solid #223049;padding:10px;display:flex;flex-direction:column;gap:6px;overflow:auto}}
aside .nav{{text-align:left}}
main{{overflow:auto;display:flex;justify-content:center;padding:16px;background:#0B1220}}
iframe{{border:0;width:100%;max-width:1000px;height:100%;min-height:960px;background:#1E293B;border-radius:12px}}
.panel{{background:#0F172A;border-left:1px solid #223049;padding:12px;overflow:auto;display:flex;flex-direction:column;gap:14px}}
h4{{font-size:12px;color:#94A3B8;font-weight:600;letter-spacing:.04em}}
.sw{{display:flex;gap:8px;align-items:center;margin:4px 0}}.sw i{{width:26px;height:26px;border-radius:6px;border:1px solid #334155;flex:none}}.sw code{{color:#94A3B8}}
table{{width:100%;border-collapse:collapse}}td{{padding:3px 0;border-bottom:1px solid #1E293B}}
.icons{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}}.ic{{display:flex;flex-direction:column;align-items:center;gap:4px;color:#94A3B8;font-size:11px}}.ic svg{{width:24px;height:24px;color:#E2E8F0}}
#pick{{background:#111A2E;border:1px solid #223049;border-radius:8px;padding:10px;line-height:1.7}}
#pick em{{color:#94A3B8;font-style:normal}}
</style>
</head>
<body>
<header>
  <b>{escape(name)} · 设计工作台</b>
  <span>平台</span>{plat_buttons}
  <span>状态</span>
  <button class="seg st on" data-state="default">默认</button><button class="seg st" data-state="loading">加载</button><button class="seg st" data-state="empty">空态</button><button class="seg st" data-state="error">错误</button>
  <button class="seg" id="anno">标注层</button>
</header>
<aside>{nav}</aside>
<main><iframe id="frame" title="画板预览" src="screens/{first}.html"></iframe></main>
<section class="panel">
  <div><h4>点选检视</h4><div id="pick"><em>在画板上点击任意元素，查看尺寸、字号、圆角和颜色。</em></div></div>
  <div><h4>色板</h4>{colors}</div>
  <div><h4>字阶</h4><table>{type_rows}</table></div>
  <div><h4>图标</h4><div class="icons">{icons}</div></div>
</section>
<script>
(function(){{
  var frame=document.getElementById('frame'),cfg={{platform:'{platforms[0]}',state:'default',anno:false}};
  function hash(){{return '#'+cfg.platform+','+cfg.state+(cfg.anno?',anno':'');}}
  function send(){{try{{frame.contentWindow.postMessage({{type:'mf-config',platform:cfg.platform,state:cfg.state,anno:cfg.anno}},'*');}}catch(e){{}}}}
  function mark(sel,attr,val){{document.querySelectorAll(sel).forEach(function(b){{b.classList.toggle('on',b.dataset[attr]===val);}});}}
  function open(view){{frame.src='screens/'+view+'.html'+hash();mark('.nav','view',view);}}
  document.querySelectorAll('.nav').forEach(function(b){{b.addEventListener('click',function(){{open(b.dataset.view);}});}});
  document.querySelectorAll('.seg[data-platform]').forEach(function(b){{b.addEventListener('click',function(){{cfg.platform=b.dataset.platform;mark('.seg[data-platform]','platform',cfg.platform);send();}});}});
  document.querySelectorAll('.st').forEach(function(b){{b.addEventListener('click',function(){{cfg.state=b.dataset.state;mark('.st','state',cfg.state);send();}});}});
  document.getElementById('anno').addEventListener('click',function(){{cfg.anno=!cfg.anno;this.classList.toggle('on',cfg.anno);send();}});
  frame.addEventListener('load',send);
  window.addEventListener('message',function(e){{
    var d=e.data||{{}};
    if(d.type==='mf-nav')mark('.nav','view',d.view);
    if(d.type==='mf-pick')document.getElementById('pick').innerHTML=
      '<b>&lt;'+d.tag+'&gt;</b> '+(d.label?'“'+d.label+'”':'')+'<br><em>尺寸</em> '+d.w+' × '+d.h+'<br><em>最小热区</em> '+(d.hit||'—')+'<br><em>字号/字重</em> '+d.font+'<br><em>圆角</em> '+d.radius+'<br><em>文字色</em> '+d.color+'<br><em>背景色</em> '+d.bg;
  }});
  mark('.seg[data-platform]','platform',cfg.platform);mark('.nav','view','{first}');
}})();
</script>
</body>
</html>
"""


def build_design_bundle(name: str, platform: str, views: Optional[List[str]] = None) -> Dict[str, str]:
    """返回 {相对路径: 文件内容}，包含设计工作台、令牌、画板和图标。"""
    views = views or ["V-01", "V-02", "V-03", "V-04"]
    platforms = required_platforms(platform) or ["ios"]
    files: Dict[str, str] = {
        "tokens.json": json.dumps(TOKENS, ensure_ascii=False, indent=2) + "\n",
        "index.html": _workbench_html(name, views, platforms),
    }
    for view_id in views:
        files[f"screens/{view_id}.html"] = build_screen_html(view_id, name, platforms)
    for icon in ICONS:
        files[f"assets/icons/{icon}.svg"] = icon_svg(icon)
    return files


def design_manifest_block(platform: str, views: Optional[List[str]] = None) -> Dict[str, Any]:
    views = views or ["V-01", "V-02", "V-03", "V-04"]
    platforms = required_platforms(platform) or ["ios"]
    return {
        "platform": platform,
        "entry": "index.html",
        "tokens_path": "tokens.json",
        "screens": [{"view_id": v, "path": f"screens/{v}.html", "platforms": platforms} for v in views],
        "icons": [f"assets/icons/{icon}.svg" for icon in ICONS],
    }
