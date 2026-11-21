# Shared UI components

FitPilot uses custom React components and vanilla CSS rather than a component library.

## BrandMark
- Source: `frontend/src/BrandMark.tsx`
- Description: Reusable FitPilot compass/leaf brand mark used in the app shell and landing page.

```tsx
export default function BrandMark({ size = 28 }: { size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 28 28" fill="none" aria-hidden="true"><circle cx="14" cy="14" r="10.5" stroke="currentColor" strokeWidth="2.5"/><path d="M8.7 17.3 12.3 9l7 2.1-6.1 2.5-4.5 3.7Z" fill="currentColor"/><circle cx="14" cy="14" r="2" fill="currentColor"/></svg>
}
```

## Shared primitives

Buttons, cards, fields, badges, dialogs, disclosures, navigation items and status treatments are class-based primitives declared in:

- `frontend/src/styles.css`
- `frontend/src/workspace.css`
- `frontend/src/studio.css`

They are rendered inline by `App.tsx`, `AgentStudio.tsx`, `PlanView.tsx`, and the other page components.
