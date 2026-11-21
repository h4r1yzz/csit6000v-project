# FitPilot theme

## Compact token summary

- Background: `#f8faf9`
- Surface: `#ffffff`
- Ink: `#17241e`
- Muted text: `#61716a`
- Border: `#e3e9e5`
- Brand emerald: `#09815b`
- Brand dark: `#066548`
- Brand soft: `#e8f7ef`
- Font: DM Sans / system sans-serif
- Display font: DM Sans
- Cards: 13–18px radius, 1px cool-green border, extremely subtle shadow
- Buttons: 9–11px radius, 42–44px minimum height
- Sidebar: 248px desktop, 58px compact mobile
- Content: up to 1480px; Advanced should use a narrower readable work area
- Breakpoints: 1100px, 820px, 760px, 600px, 420px

## Raw token source

```css
:root {
  --ink:#17241e;
  --muted:#61716a;
  --line:#e3e9e5;
  --green:#09815b;
  --green-dark:#066548;
  --green-soft:#e8f7ef;
  --cream:#f8faf9;
  --display:'DM Sans',ui-sans-serif,system-ui,sans-serif;
  background:#f8faf9;
  color:#17241e;
}
```

Primary source files:
- `frontend/src/styles.css`
- `frontend/src/workspace.css`
- `frontend/src/studio.css`
- `frontend/src/LandingPage.css`
- `frontend/src/auth.css`
