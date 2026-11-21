# Route map

Routing is hash-based and implemented in `frontend/src/Root.tsx`.

| Hash | View | Main component |
|---|---|---|
| `#home` | Public landing | `LandingPage.tsx` |
| `#/login` | Login | `AuthPage.tsx` |
| `#/preferences/setup` | First-run preferences | `App.tsx` + `Preferences.tsx` |
| `#/app` | Home | `App.tsx` |
| `#/week` | Weekly plan | `App.tsx` + `PlanView.tsx` |
| `#/week/today` | Today’s plan focus | `App.tsx` + `PlanView.tsx` |
| `#/workout` | Form tracker | `App.tsx` + `PoseCoach.tsx` |
| `#/progress` | Activity journal | `App.tsx` |
| `#/preferences` | Preferences | `App.tsx` + `Preferences.tsx` |
| `#/advanced` | Reviewer agent console | `App.tsx` + `AgentStudio.tsx` |

Legacy `#/studio` maps to Workout.
