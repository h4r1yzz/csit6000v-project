# FitPilot — UI research and tracker design

Date: 16 November 2026
Status: first implementation completed on 16 November 2026; remaining enhancements are identified below.
Target: the existing FitPilot React application, starting with its tracker.

## 1. Direction

Use a bright, spacious fitness dashboard around a focused live workout workspace. The tracker should immediately answer: **What exercise am I doing? Can the app see the required joints? What must happen for the next repetition to count?**

The two references serve different purposes: Dribbble informs the visual language; the workout-companion reference informs the side-by-side practice experience. Preserve FitPilot branding and existing data rather than reproducing another product's identity or placeholder metrics.

## 2. Reference research and confidence

### A. SaaS Workout — Landing Page

Source: [Vetrick Wilsen for Yow on Dribbble](https://dribbble.com/shots/24865917-SaaS-Workout-Landing-Page). The principal shot image was inspected directly.

Observed: a nearly white canvas; dark typography; a light headline with one bold phrase; vivid green primary actions; pastel peach, blue and mint feature panels; rounded cards with fine borders; generous whitespace; small playful illustrations. Dashboard previews organize metrics, schedules and charts into clear modules. Tilted preview cards and floating decorations belong to the marketing presentation.

Interpretation for FitPilot: adopt the light surfaces, crisp hierarchy and restrained pastel accents. Keep operational cards level and readable. Use playful details on overview and empty states; reduce decoration during a set. The screenshot does not establish an exact font family or color specification. Tokens below are original implementation proposals, not sampled brand values.

### B. AI workout companion

Requested source: [Qian Jiang's X post](https://x.com/qianjiang___/status/2114429212723744932). Direct X access returned 403. A [secondary page carrying the post preview](https://starbelo.com/use-case/qian-jiang-ai-workout-companion-real-time-feedback/) and its preview image were inspected.

Visible in the preview: two adjacent panels labeled for following a workout and practicing; demonstration video on the left; user camera and pose lines on the right; exercise context beneath the demo; feedback and workout controls beneath the camera.

The secondary description identifies real-time feedback as the concept. The full video, exact transitions, voice behavior, implementation and accuracy were not verified. Do not attribute a specific model, latency or counting method to the creator. Voice, countdown and rest behavior below are FitPilot proposals.

## 3. Current FitPilot audit

Based on the existing source and the screenshots/recording supplied in this chat:

| Current issue | Proposed response |
| --- | --- |
| Large promotional heading plus another heading inside the tracker | One compact heading: “Workout studio”. |
| Camera dominates vertically; results and cues fall below it | Put the counter and next cue beside/within the camera panel. |
| Equal visual emphasis on reps, angle, visibility and elapsed tracking time | Make completed reps primary; move diagnostics into Details. |
| Very small labels and low-contrast sage text in several components | Increase control/body sizes and use darker text on white. |
| A running process can look like successful movement detection | Separate camera running, joints visible, ready, counting and paused states. |
| User cannot tell which threshold is blocking a rep | Show the current counting stage and a plain-language next action. |
| No demonstration alongside practice | Add an exercise guide panel with an owned/licensed clip or original illustrated sequence. |
| Calibration has equal prominence to normal workout controls | Place it in “Adjust tracking”; expose it contextually if needed. |
| Generic coach chat competes with session feedback | Keep the live cue in the studio; reserve chat for explicit questions. |

The recent curl correction is a functional prerequisite, not evidence that every camera angle is accurate. Keep counting regression tests independent of the visual redesign.

## 4. Information architecture

Retain the app's existing destinations, with user-facing labels:

- Overview: next workout, weekly completion, recent activity.
- My plan: approved workouts and meals.
- Workout studio: the main camera/clip tracker; replaces “Form check”.
- Progress: saved sessions and trends from actual logs.
- Coaching team: planning and session-review agents.
- Preferences: equipment, goals and profile settings.

The app opens with a separate public landing page, as requested on 16 November. The landing page introduces the product before visitors enter the dashboard or studio. Apply the same visual direction inside the app. Do not add membership countdowns, subscription offers, wearable data or calorie estimates without corresponding product functionality.

## 5. Desktop studio layout

Use a compact title row, an exercise selector and source switch, then a two-column workspace. At a typical laptop viewport, users should see the camera, completed count, current cue and Pause/Finish controls without scrolling.

```text
┌──────────────┬────────────────────────────────────────────────────┐
│ FitPilot     │ Workout studio                 Local coaching      │
│              │ Bicep curl ▾   Camera / Analyze clip               │
│ Overview     ├──────────────────────┬─────────────────────────────┤
│ My plan      │ 01  Exercise guide   │ 02  Your practice           │
│ Studio       │                      │                             │
│ Progress     │ Demonstration        │ Camera + relevant joints    │
│ Coaching     │ or illustrated loop  │                    06 reps  │
│ Preferences  │                      │ Left 3 · Right 3            │
│              ├──────────────────────┼─────────────────────────────┤
│              │ Start → Bend →       │ Bend reached                │
│              │ Return               │ Straighten to finish        │
│              │ Short setup tips     │ ● Joints visible            │
│              │                      │ [Pause] [Finish workout]    │
│              └──────────────────────┴─────────────────────────────┤
│              │ Details ▾     Adjust tracking ▾                    │
└──────────────┴────────────────────────────────────────────────────┘
```

Proposed geometry:

- Sidebar: 216–232 px on desktop; collapse in focus mode.
- Workspace: maximum width 1440 px; 24–32 px outer padding.
- Columns: approximately 42% guide / 58% practice, with a 20–24 px gap.
- Media: natural aspect ratio with `object-fit: contain`; never crop out exercise joints to fill a card.
- Media height: adapt to viewport height rather than using an unconditional large minimum.
- Cue and counter use a fixed reserved area so changing text does not shift controls.
- Focus mode: camera, counter, cue and controls; hide guide/sidebar without stopping the stream.
- Move recent sessions below the workspace; do not put history between camera and controls.

## 6. Session flow and state language

| State | Visible message | Main action / behavior |
| --- | --- | --- |
| Idle | “Choose an exercise, then start your camera.” | Start camera; Analyze clip as secondary action. |
| Loading | “Preparing movement tracking…” | Show progress state and actionable retry on failure. |
| Permission denied | “Camera access is blocked.” | Explain permission recovery; keep clip input available. |
| Camera on, joints missing | “Show your shoulder, elbow and wrist.” | Highlight relevant framing guide; preserve completed count. |
| Ready | “You’re in position. Start when ready.” | Optional 3-second countdown, cancellable. |
| Awaiting extension | “Straighten your arm to begin.” | Count stays unchanged. |
| Awaiting bend | “Bend your elbow.” | Show start stage completed. |
| Awaiting return | “Bend reached. Straighten to finish.” | Increment only when the counter completes the cycle. |
| Rep completed | “Rep counted.” | Brief counter emphasis; optional sound. |
| Tracking interrupted | “Arm temporarily out of view.” | No inferred reps; preserve completed totals. |
| Paused | “Workout paused.” | Resume / Finish; clearly indicate whether camera remains on. |
| Finishing | “Review your session.” | Show results before Save. |
| Saved | “Workout saved.” | Review with coach / Start another session. |

The setup cue and counter phase must come from the analyzer, not from a timer or generic success animation. If a partial cycle is discarded after tracking loss, say “Tracking reset — straighten to begin.” A paused or hidden page must not fabricate a rep across resumption.

### Repetition semantics

For curls, keep the existing total as the sum of completed arm cycles for backward compatibility. Label it **Total arm reps**, with Left and Right counts always beside it. A simultaneous bilateral curl adds two; explain this in a compact tooltip. For squats, label the single combined value **Reps**. Never silently change stored count semantics during a visual redesign.

Show the count at 64–80 px on desktop and 48–64 px on mobile. Left/right labels refer to anatomical sides, regardless of mirror mode. If mirroring the preview, mirror video and overlay together; do not swap stored sides.

### Guide content

Each supported movement needs a matching guide: bicep curl, squat and arm circles. A demonstration is instructional, not an input that determines the user's count. Its playback time need not match the user. Label repeated guide playback “Demo loop”. Use an original illustrated sequence until a suitable owned/licensed video exists. Never use the reference creator's footage as an application asset by default.

## 7. Visual system — proposed tokens

| Token | Value | Use |
| --- | --- | --- |
| Canvas | `#F7F9F8` | App background |
| Surface | `#FFFFFF` | Cards and navigation |
| Main text | `#17241E` | Titles, count, body copy |
| Secondary text | `#53635B` | Supporting copy |
| Border | `#DDE5E0` | Card/input boundaries |
| Primary | `#087F5B` | Primary buttons with white text |
| Bright accent | `#23B47E` | Decorative marks and progress fills |
| Mint | `#E8F7EF` | Positive feedback surface |
| Sky | `#EAF4FD` | Guide and schedule accents |
| Peach | `#FFF1E3` | Recovery/rest accents |
| Lavender | `#F2EDFC` | Secondary summary accents |
| Warning | `#9A4A10` on `#FFF4E6` | Tracking interruption |
| Error | `#B42318` on `#FFF0EE` | Actionable errors |

Use one locally available sans-serif stack initially: `Inter, ui-sans-serif, system-ui, sans-serif`. If bundling a font later, include its license. Use 28–32 px/600 for page headings; 18–20 px/600 for panel headings; 15–16 px for instructions; 13–14 px for metadata. Set numeric counters to tabular figures.

Use a 4/8 px spacing rhythm, 16–20 px panel radii, 10–12 px control radii, 1 px borders and subtle shadows. Keep pill shapes for statuses. Use the existing Lucide icons consistently, with text labels for primary controls. These are proposed values; contrast and responsive behavior must be measured in implementation.

## 8. Coaching behavior and motion

During a set, display one actionable cue, not a scrolling chat transcript. Prioritize: missing joints → setup/phase → rep completion → optional technique heuristic. Suppress repetitive cues; update immediately when a meaningful state changes.

Keep local counting and immediate movement cues in the browser. The current backend agent reviews saved measurements; do not relabel that as continuous live AI video understanding. A later live language-model coach requires a separate contract for sampled measurements, latency, cancellation and data disclosure.

Optional audio is a later enhancement: off initially, opt-in per user, mute always reachable. Announce stable stage changes or completed reps rather than every angle update. Visual information remains complete without sound.

Use 120–180 ms transitions and a restrained rep-count emphasis. Respect reduced-motion settings. Do not animate skeleton jitter or hide confidence loss behind a cheerful animation.

## 9. Responsive and accessible behavior

- Above 1100 px: two-panel studio; fit essential actions in the viewport.
- 768–1100 px: compact navigation; two columns only when both remain usable.
- Below 768 px: camera first, then counter/cue/controls; collapsible exercise guide.
- A mobile action bar must respect safe-area insets and not cover cues.
- Provide comfortably sized controls (target at least 44 × 44 px), visible keyboard focus and text labels.
- Use text/icons as well as color for visibility and errors.
- Announce rep completion and material state changes politely; do not announce every frame.
- Preserve usability at 200% zoom and in landscape orientation.
- Explain empty measurements as “Not visible” rather than an unexplained dash.
- Put confidence percentages and exact threshold angles in Details. Do not present joint visibility as a form-quality score.

## 10. Implementation map

Repository: `/Users/harry/advancedAifrontend/CSIT6000V-fitness-tracker`.

| Area | Proposed work |
| --- | --- |
| `frontend/src/App.tsx` | Compact studio header; update navigation label; retain session history. |
| `frontend/src/PoseCoach.tsx` | Compose guide, camera, count, cue and control panels; preserve source/session lifecycle. |
| `frontend/src/PoseCoach.css` | Replace stacked layout with responsive workspace and scoped tokens. |
| `frontend/src/pose/analysis.ts` | Expose typed visibility/phase state; preserve tested repetition rules. |
| `frontend/src/pose/counter.ts` | Keep full-cycle logic independent of rendering. |
| `frontend/src/types.ts` | Align saved-session types with optional per-side counts/thresholds. |
| `frontend/src/styles.css`, `workspace.css` | Apply shared typography/surface improvements incrementally. |
| Backend schemas and feedback | Reuse saved-summary endpoints; extend only for real new persisted fields. |

Suggested UI components: `WorkoutStudio`, `ExerciseGuide`, `PracticeViewport`, `RepCounterPanel`, `LiveCue`, `SessionControls`, `TrackingDetails`, `SessionReview`.

Deliver in three passes:

1. **Studio usability:** layout, explicit counts, stage cues, source controls and responsive behavior. Preserve existing analyzer/API behavior.
2. **Guide and visual system:** original guide assets, pastel panels, typography, focus mode and consistent dashboard styling.
3. **Companion enhancements:** optional audio, workout-set/rest flow and carefully scoped live model commentary if requested. These are new functionality, not cosmetic tasks.

## 11. Acceptance criteria

- On a 1440 × 900 viewport, camera, rep count, next cue and Pause/Finish are visible together.
- On a 390 × 844 viewport, there is no horizontal scrolling and primary controls remain reachable.
- Switching between camera and clip releases resources and resets the intended session cleanly.
- Camera active with missing joints never displays a counting-success state.
- Curl totals and anatomical per-arm counts are unambiguous.
- A full valid cycle increments exactly once per arm; partials, long dropouts and source changes cannot fabricate counts.
- Existing squat and arm-circle tests continue passing.
- Calibration practice reps remain excluded; saved summaries retain threshold provenance.
- Finishing/retrying a save cannot create duplicate pose sessions or workout logs.
- Unavailable model assets, denied camera permission and interrupted tracking have actionable states.
- The guide, live feedback and saved-session coach review are visibly distinct.
- Live camera checks on intended devices and representative exercise clips supplement synthetic tests.
- Private user recordings and screenshots stay out of committed design assets and fixtures.

## 12. Remaining reference uncertainty

The side-by-side composition is supported by the inspected workout-companion preview. Its full interaction sequence and voice behavior remain unverified. A user-supplied copy of the X demonstration would allow closer motion/interaction analysis; the visual and layout specification above can proceed independently.

## Implementation update — 16 November 2026

Implemented: bright overview hero and emerald actions, pastel dashboard cards,
Workout studio navigation, responsive two-panel guide/practice layout, original
illustrated three-step guides for all three exercises, guide playback controls,
large completed counts with curl side totals, visible next-action cues, and
collapsible tracking diagnostics/calibration. On narrow screens, practice comes
before the guide. The existing camera, clip, count, save and review logic is retained.

Guide illustrations are original SVG sequences, not the reference creator's video.
Focus mode, audio coaching, rest/set sequencing and a separate session-review dialog
remain proposed enhancements. Build and 17 analyzer regressions passed; live browser
visual QA was not performed because browser access was previously declined.

## Landing-first navigation

The root URL opens the landing page independently of API availability. `#/app` opens the dashboard and `#/studio` opens Workout studio. The sidebar FitPilot logo returns to `#/`. Browser hash history provides back/forward navigation. The landing page includes labeled illustrative previews, features, a three-step introduction, privacy FAQs and working app-entry links. No login, pricing, testimonials or partner claims are invented. Source-level render checks cover the landing, dashboard, studio, return-home and section-anchor paths; live browser visual inspection remains unverified.
