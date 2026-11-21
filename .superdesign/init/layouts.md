# Shared layouts

## App shell
- Source: `frontend/src/App.tsx`
- Description: Persistent desktop sidebar, sticky top bar, routed page content, app footer, Coach FAB, chat panel and activity dialog.

The shell renders:

```tsx
<div className="app-shell">
  <aside className="sidebar">
    <a className="brand">fitpilot.</a>
    <nav className="side-nav">
      Home · My week · Workout · Progress
      Preferences · Advanced
    </nav>
    <button className="profile-chip">Account</button>
  </aside>
  <main className="main-area">
    <header className="topbar">Breadcrumb · Sign out · Avatar</header>
    {activeView}
    <footer className="app-footer">Wellness disclaimer</footer>
  </main>
  <button className="coach-fab">Coach</button>
</div>
```

The complete implementation is in `frontend/src/App.tsx`; global shell styles are in `frontend/src/styles.css`, `frontend/src/workspace.css`, and `frontend/src/studio.css`.

## Landing layout
- Source: `frontend/src/LandingPage.tsx`
- Description: Public header, hero, product preview, features, how-it-works, FAQ and footer.

## Authentication layout
- Source: `frontend/src/AuthPage.tsx`
- Description: Split authentication page with account forms and supporting product content.
