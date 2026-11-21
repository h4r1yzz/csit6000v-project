# Page dependency trees

## Public landing
Entry: `frontend/src/Root.tsx`
- `frontend/src/LandingPage.tsx`
  - `frontend/src/BrandMark.tsx`
  - `frontend/src/MovementCollage.tsx`
  - `frontend/src/LandingPage.css`

## Authenticated app shell
Entry: `frontend/src/Root.tsx`
- `frontend/src/App.tsx`
  - `frontend/src/BrandMark.tsx`
  - `frontend/src/api.ts`
  - `frontend/src/types.ts`
  - `frontend/src/PlanView.tsx`
    - `frontend/src/AgentStudio.tsx`
  - `frontend/src/Preferences.tsx`
  - `frontend/src/PoseCoach.tsx`
    - `frontend/src/ExerciseGuide.tsx`
    - `frontend/src/pose/analysis.ts`
    - `frontend/src/PoseCoach.css`

## Advanced reviewer console
Entry: `frontend/src/Root.tsx`
- `frontend/src/App.tsx` (sidebar, topbar, footer, Coach FAB)
  - `frontend/src/AgentStudio.tsx` (runner, result panel, history and workflow)
  - `frontend/src/api.ts`
  - `frontend/src/types.ts`
- `frontend/src/styles.css`
- `frontend/src/workspace.css`
- `frontend/src/studio.css`

## My week
Entry: `frontend/src/App.tsx`
- `frontend/src/PlanView.tsx`
  - `frontend/src/AgentStudio.tsx` (workflow trace helpers)
- `frontend/src/types.ts`

## Workout
Entry: `frontend/src/App.tsx`
- `frontend/src/PoseCoach.tsx`
  - `frontend/src/ExerciseGuide.tsx`
  - `frontend/src/pose/analysis.ts`
  - `frontend/src/pose/counter.ts`
