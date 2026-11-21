# Extractable components

## AppShell
- Source: `frontend/src/App.tsx`
- Category: layout
- Description: Sidebar, top bar, page container, footer and Coach FAB.
- Extractable props: `activeView`, `accountName`, `hasActivePlan`
- Hardcoded: FitPilot brand, nav labels, icons and shell classes

## BrandMark
- Source: `frontend/src/BrandMark.tsx`
- Category: basic
- Description: FitPilot compass/leaf mark.
- Extractable props: `size`
- Hardcoded: SVG geometry

## WorkflowTrace
- Source: `frontend/src/AgentStudio.tsx`
- Category: basic
- Description: Expandable workflow-stage results with status and provenance.
- Extractable props: `runs`
- Hardcoded: status icons and result presentation

## RunDetails
- Source: `frontend/src/AgentStudio.tsx`
- Category: basic
- Description: Agent run metadata and nested structured result renderer.
- Extractable props: `run`
- Hardcoded: source/status presentation

The shell is currently embedded in `App.tsx`, so it is better passed as source context than extracted into a reusable canvas component for this single-page redesign.
