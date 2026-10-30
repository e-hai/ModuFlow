# Mobile Component Design Patterns for Canonical UI Bundles

This document provides zero-dependency, copy-paste ready HTML/CSS design patterns for Stage 06 deliverables conforming to Sketch MeaXure and HIG/Material specifications.

---

## 1. Mobile Card List Item (`mf-card`)

Interactive list item adhering to 44x44pt (iOS) / 48x48dp (Android) hit targets.

```html
<div class="mf-card" data-hit="44x44" data-nav-target="V-02" role="button" tabindex="0">
  <div class="mf-card-icon">
    <img src="../slices/icon_scan.svg" alt="Scan Icon" width="24" height="24">
  </div>
  <div class="mf-card-content">
    <div class="mf-card-header">
      <span class="mf-card-title">Doc_2026_10_30.pdf</span>
      <span class="mf-badge">PRO</span>
    </div>
    <p class="mf-card-subtitle">3 pages · 2.4 MB · High Quality</p>
  </div>
  <div class="mf-card-action">
    <img src="../slices/chevron_right.svg" alt="Open" width="16" height="16">
  </div>
</div>
```

```css
.mf-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  min-height: 56px;
  background: var(--color-surface, #ffffff);
  border-bottom: 1px solid var(--color-border, #f1f5f9);
  cursor: pointer;
  transition: background-color 0.15s ease;
}
.mf-card:active {
  background-color: var(--color-surface-hover, #f8fafc);
}
.mf-card-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: var(--color-primary-light, #eff6ff);
  display: flex;
  align-items: center;
  justify-content: center;
}
.mf-card-content {
  flex: 1;
  min-width: 0;
}
.mf-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.mf-card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary, #0f172a);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.mf-badge {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--color-primary, #2563eb);
  color: #ffffff;
}
.mf-card-subtitle {
  font-size: 13px;
  color: var(--color-text-secondary, #64748b);
  margin-top: 2px;
}
```

---

## 2. Chip Filter Bar (`mf-chip-bar`)

Horizontal scrollable filter bar with minimum 44px tap targets.

```html
<div class="mf-chip-bar" role="tablist">
  <button class="mf-chip active" data-hit="44x44" role="tab" aria-selected="true">All Documents</button>
  <button class="mf-chip" data-hit="44x44" role="tab" aria-selected="false">Recent</button>
  <button class="mf-chip" data-hit="44x44" role="tab" aria-selected="false">Shared</button>
  <button class="mf-chip" data-hit="44x44" role="tab" aria-selected="false">Starred</button>
</div>
```

```css
.mf-chip-bar {
  display: flex;
  gap: 8px;
  padding: 8px 16px;
  overflow-x: auto;
  scrollbar-width: none;
  -webkit-overflow-scrolling: touch;
}
.mf-chip-bar::-webkit-scrollbar {
  display: none;
}
.mf-chip {
  min-height: 44px;
  padding: 0 16px;
  border-radius: 22px;
  border: 1px solid var(--color-border, #e2e8f0);
  background: var(--color-surface, #ffffff);
  color: var(--color-text-secondary, #64748b);
  font-size: 13px;
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  white-space: nowrap;
  cursor: pointer;
  transition: all 0.15s ease;
}
.mf-chip.active {
  background: var(--color-primary, #2563eb);
  color: #ffffff;
  border-color: var(--color-primary, #2563eb);
  box-shadow: 0 2px 4px rgba(37, 99, 235, 0.2);
}
```

---

## 3. Form Input Field with Validation State

Standard mobile text input with floating label or clear top label, supporting error feedback.

```html
<div class="mf-form-group">
  <label for="doc-name" class="mf-label">Document Title</label>
  <div class="mf-input-wrapper">
    <input type="text" id="doc-name" class="mf-input" placeholder="e.g. Passport Scan" value="" />
    <button class="mf-input-clear" data-hit="44x44" aria-label="Clear input">
      <img src="../slices/close.svg" width="16" height="16" alt="Clear">
    </button>
  </div>
  <p class="mf-input-error" role="alert">Please enter a valid document title.</p>
</div>
```

```css
.mf-form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px 16px;
}
.mf-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-secondary, #475569);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.mf-input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}
.mf-input {
  width: 100%;
  min-height: 48px;
  padding: 0 44px 0 14px;
  border-radius: 10px;
  border: 1.5px solid var(--color-border, #cbd5e1);
  background: var(--color-surface, #ffffff);
  font-size: 15px;
  color: var(--color-text-primary, #0f172a);
  outline: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.mf-input:focus {
  border-color: var(--color-primary, #2563eb);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
}
.mf-input-wrapper.error .mf-input {
  border-color: var(--color-danger, #ef4444);
}
.mf-input-clear {
  position: absolute;
  right: 0;
  width: 44px;
  height: 44px;
  background: transparent;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.mf-input-error {
  display: none;
  font-size: 12px;
  color: var(--color-danger, #ef4444);
  margin-top: 2px;
}
.mf-input-wrapper.error + .mf-input-error {
  display: block;
}
```

---

## 4. Skeleton Pulse Animation (Loading State)

Zero-dependency pure CSS shimmer/pulse effect for `data-state="loading"`.

```html
<div class="mf-skeleton-card">
  <div class="mf-skeleton mf-skeleton-thumb"></div>
  <div class="mf-skeleton-lines">
    <div class="mf-skeleton mf-skeleton-title"></div>
    <div class="mf-skeleton mf-skeleton-subtitle"></div>
  </div>
</div>
```

```css
@keyframes mf-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.mf-skeleton {
  background: #e2e8f0;
  border-radius: 6px;
  animation: mf-pulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}
.mf-skeleton-card {
  display: flex;
  gap: 12px;
  padding: 14px 16px;
  border-bottom: 1px solid #f1f5f9;
}
.mf-skeleton-thumb {
  width: 44px;
  height: 44px;
  border-radius: 10px;
}
.mf-skeleton-lines {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  justify-content: center;
}
.mf-skeleton-title {
  width: 65%;
  height: 14px;
}
.mf-skeleton-subtitle {
  width: 40%;
  height: 12px;
}
```

---

## 5. Empty State Illustration Card

Used for `data-state="empty"`.

```html
<div class="mf-empty-state">
  <div class="mf-empty-icon">
    <img src="../slices/illustration_empty.svg" alt="Empty List" width="80" height="80">
  </div>
  <h3 class="mf-empty-title">No Scans Yet</h3>
  <p class="mf-empty-desc">Tap the button below to scan your first receipt, contract or whiteboard notes.</p>
  <button class="mf-btn-primary" data-hit="44x44" data-nav-target="V-02">
    Scan New Document
  </button>
</div>
```

```css
.mf-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 48px 24px;
  margin: auto;
}
.mf-empty-icon {
  margin-bottom: 20px;
  opacity: 0.85;
}
.mf-empty-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-text-primary, #0f172a);
  margin-bottom: 8px;
}
.mf-empty-desc {
  font-size: 14px;
  color: var(--color-text-secondary, #64748b);
  max-width: 280px;
  line-height: 1.5;
  margin-bottom: 24px;
}
.mf-btn-primary {
  min-width: 180px;
  min-height: 48px;
  padding: 0 24px;
  border-radius: 12px;
  border: none;
  background: var(--color-primary, #2563eb);
  color: #ffffff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25);
}
```

---

## 6. Error Banner with Retry Action

Used for `data-state="error"`.

```html
<div class="mf-error-state" role="alert">
  <div class="mf-error-icon">
    <img src="../slices/icon_warning.svg" width="36" height="36" alt="Error">
  </div>
  <h4 class="mf-error-title">Unable to Load Documents</h4>
  <p class="mf-error-message">The local storage sandbox could not be accessed. Please check permissions.</p>
  <button class="mf-btn-retry" data-hit="44x44" onclick="location.reload()">
    Try Again
  </button>
</div>
```

```css
.mf-error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 32px 20px;
  background: #fef2f2;
  border: 1px solid #fee2e2;
  border-radius: 16px;
  margin: 24px 16px;
}
.mf-error-icon {
  margin-bottom: 12px;
}
.mf-error-title {
  font-size: 16px;
  font-weight: 600;
  color: #991b1b;
  margin-bottom: 6px;
}
.mf-error-message {
  font-size: 13px;
  color: #b91c1c;
  max-width: 260px;
  line-height: 1.4;
  margin-bottom: 16px;
}
.mf-btn-retry {
  min-height: 44px;
  padding: 0 20px;
  background: #dc2626;
  color: #ffffff;
  border: none;
  border-radius: 10px;
  font-weight: 600;
  font-size: 13px;
  cursor: pointer;
}
```
