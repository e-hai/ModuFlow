# MeaXure & Canonical UI Data Attributes Specification

This reference defines the standard HTML `data-*` attributes and postMessage protocol required for Stage 06 Canonical Design Bundles.

---

## 1. Physical Constraints Attributes

| Attribute | Expected Values | Description |
| :--- | :--- | :--- |
| `data-device` | `"ios"`, `"android"` | Applied to the root `#phone-frame` container to declare the platform frame context. |
| `data-safe-top` | Integer (`"74"`, `"71"`, `"32"`, `"24"`) | Defines top safe-area inset in pt/dp to avoid overlapping the Dynamic Island (≥71pt) or punch-hole camera (≥24dp). |
| `data-safe-bottom` | Integer (`"34"`, `"16"`) | Defines bottom safe-area inset in pt/dp to prevent home bar obstruction (≥34pt on iOS). |
| `data-hit` | `"44x44"`, `"48x48"` | Enforces physical tap target bounding box minimum dimensions via CSS `[data-hit]`. |

### Example
```html
<div class="device-frame" data-device="ios" data-safe-top="74" data-safe-bottom="34">
  <button class="nav-btn" data-hit="44x44" data-nav-target="V-02">
    <img src="../slices/back.svg" alt="Back" width="20" height="20">
  </button>
</div>
```

---

## 2. State & Navigation Attributes

| Attribute | Expected Values | Description |
| :--- | :--- | :--- |
| `data-state` | `"default"`, `"loading"`, `"empty"`, `"error"` | Declares which state panel the container represents. The workbench state-switcher toggles `.is-active` based on this attribute. |
| `data-nav-target` | View ID (e.g. `"V-01"`, `"V-02"`, `"V-05"`) | Links interactive elements to target screens in `manifest.json`. Triggers screen transition in the workbench. |
| `data-toast` | Text message (e.g. `"Document saved successfully"`) | Triggers temporary floating toast feedback when tapped. |

### Example
```html
<!-- Four State Panels in Screen Container -->
<div class="state-panel is-active" data-state="default">
  <!-- Main content -->
</div>

<div class="state-panel" data-state="loading">
  <!-- Skeleton loader -->
</div>

<div class="state-panel" data-state="empty">
  <!-- Empty placeholder -->
</div>

<div class="state-panel" data-state="error">
  <!-- Error card with retry -->
</div>
```

---

## 3. PostMessage Inspection Protocol (`window.postMessage`)

The screen iframes communicate bidirectionally with the outer MeaXure workbench (`workbench.template.html` / `index.html`) using structured JSON events.

### Outbound Events (Screen -> Workbench)

#### 1. `mf-pick` (Element Selection)
Dispatched whenever a user clicks or hovers an element in inspect mode.
```json
{
  "type": "mf-pick",
  "tag": "button",
  "id": "scan-cta",
  "className": "mf-btn-primary min-w-[44px]",
  "role": "button",
  "text": "Start Scanning",
  "hit": "44x44",
  "navTarget": "V-02",
  "bounds": {
    "left": 24,
    "top": 740,
    "width": 345,
    "height": 52
  },
  "fontSize": "16px",
  "fontWeight": "600",
  "fontFamily": "-apple-system, BlinkMacSystemFont",
  "color": "#ffffff",
  "backgroundColor": "#2563eb",
  "borderRadius": "12px",
  "margin": "0px",
  "padding": "0px 24px"
}
```

#### 2. `mf-navigate` (Screen Transition)
Dispatched when an element with `data-nav-target` is clicked.
```json
{
  "type": "mf-navigate",
  "target": "V-02"
}
```

### Inbound Events (Workbench -> Screen)

#### 1. `mf-set-state`
Instructs the screen iframe to switch its active state panel.
```json
{
  "type": "mf-set-state",
  "state": "loading"
}
```

#### 2. `mf-set-platform`
Instructs the screen iframe to update its platform-specific styling or safe-area padding.
```json
{
  "type": "mf-set-platform",
  "platform": "android"
}
```

#### 3. `mf-set-inspect`
Enables or disables the dashed red MeaXure hover and selection bounding outlines.
```json
{
  "type": "mf-set-inspect",
  "inspect": true
}
```
