# Pose estimation and movement tracking

`frontend/src/PoseCoach.tsx` owns camera/video controls, model initialization, rendering, session saving, and feedback requests. `frontend/src/pose/analysis.ts` contains the pure movement state machine. `frontend/src/PoseCoach.css` styles the tracker.

## Input and inference

Choose a webcam or a local video clip. Webcam capture requests video without audio and needs browser permission. Uploaded clips must be video files of at most 500 MB; codec support depends on the browser. Neither input sends frames to FastAPI.

The browser loads the MediaPipe Tasks Vision WASM runtime from jsDelivr and Google's pretrained Pose Landmarker Lite model. Initialization first requests GPU execution and retries with CPU execution if GPU initialization fails. Model download failures appear as an actionable tracker error.

Inference runs in video mode for one person and is capped at approximately 15 frames per second. It runs on the browser's main thread. Slow devices may therefore show reduced responsiveness; moving inference into a worker is a future performance improvement.

The skeleton uses the source video's aspect ratio so landmarks remain aligned with the displayed person. Camera/video source changes, pausing, switching exercise, seeking, replaying, and unmounting reset or stop the appropriate analysis loop. Stopping or leaving the camera releases its media tracks.

## Confidence and geometry

The analyzer chooses the side with the clearest required joints, then keeps that side while it remains visible. The minimum joint visibility/presence threshold is 0.65. Missing/low-confidence joints cannot advance the rep state. Switching sides, a visibility gap, a backward timestamp, or a frame gap longer than 500 ms resets the incomplete movement.

Squats require hip, knee, and ankle landmarks. Curls and arm circles require shoulder, elbow, and wrist landmarks. When available, world-coordinate landmarks are used for knee/elbow angles; the fallback computes angles from image coordinates corrected for the video aspect ratio. World estimates still depend on camera placement and model accuracy.

Average confidence and tracked duration summarize usable samples, rather than total clip length or elapsed wall-clock time. Paused or untracked intervals do not count as confident movement time.

## Repetition rules

| Movement | Rules |
| --- | --- |
| Squat | Establish an extended knee angle above 155°, move below 100°, then return above 155°. |
| Bicep curl | Establish an extended elbow angle above 145°, flex below 60°, then return above 145°. |
| Arm circles | Track signed wrist rotation around the shoulder in the frontal image plane until approximately one full revolution is accumulated. Reverse movement cancels accumulated rotation. |

Knee/elbow angles use exponential smoothing with a 0.4 weight on the new sample. A target phase must be held for 100 ms. Returning from flexion must take at least 300 ms and completed reps must be at least 700 ms apart. These rules reduce threshold jitter and incomplete-rep counts.

For circles, tracking discontinuities greater than 60° between samples reset rotation instead of counting a jump. The wrist must be far enough from the shoulder to establish a usable circle radius. At least 700 ms is required between counted circles. This supports arm circles visibly rotating in the camera plane; small forward/backward circles may not be measurable.

The tracker suggests a side view for squats/curls and a frontal view for circles. It reports movement cues and an elbow-swing cue for curls. It does not provide clinical knee-alignment, injury, or correct-technique guarantees.

## Session lifecycle

1. Start tracking and collect at least ten usable frames. Zero reps can still be saved for feedback.
2. Choose perceived effort from 1 to 10.
3. Select **Save & log session**. The browser pauses analysis and POSTs a derived summary to `/api/pose-sessions`.
4. After the summary is saved, a workout entry is created through `/api/workouts`, with summary ID and detected metrics in its notes.
5. Select **Review this session** to run `exercise_feedback` with the saved `pose_session_id`.

Saving the summary and creating a workout are separate requests. If the workout request fails after summary creation, the UI retains the summary ID and offers **Retry workout log**, avoiding another pose-summary record. A lost response after a successful server write can still create a duplicate on retry because the API does not implement request idempotency keys.

A saved session is frozen until a new session is started. Feedback requires live inference and fails visibly when the model is unavailable. The LLM receives structured measurements, bounded numerical landmark snapshots, and relevant profile/context. It does not see the recorded clip.

## Summary fields

| Field | Meaning |
| --- | --- |
| `exercise` | Squat, Bicep curl, or Arm circles |
| `duration_seconds` | Time accumulated between usable tracked samples |
| `reps` | Repetitions completed by the movement state machine |
| `analyzed_frames` | Number of usable analyzer samples |
| `average_confidence` | Average minimum confidence over the required joints |
| `range_of_motion.min/max` | Observed smoothed knee/elbow angle or frontal wrist rotation in degrees |
| `form_cues` | Distinct analysis cues recorded during the session |
| `source` | `webcam` or `upload` |
| `landmark_samples` | Up to eight numerical snapshots, each with `time_seconds` and 33 `{x,y,z,visibility}` landmarks |

Landmark snapshots retain the eight most recent usable samples, spaced at least one second of confident tracking apart. Coordinates come from observed image-normalized landmarks; no poses are synthesized. Samples containing nonfinite or out-of-range coordinates are omitted. Snapshot times are relative to the decimal confident-tracking duration. Saving persists these numerical samples and makes them available in feedback/model context. No image or video data is included.

For arm circles, minimum/maximum wrapped angles do not describe clinical shoulder range of motion. They describe the image-plane wrist rotation values seen during the session.

## Tests and remaining validation

Pure analysis tests cover geometry, both sides, complete squat/curl cycles, incomplete/low-confidence movement, timing discontinuities, circles, and summary values. With Node.js 22.18+:

```bash
node --test frontend/src/pose/analysis.test.mjs
```

The app itself builds with Node.js 20+, but these tests use Node's newer built-in TypeScript loading. Real webcam permission, GPU/CPU model loading, skeleton alignment, clip decoding, and accuracy on representative people still need browser/device validation. Use the manual checklist in [the README manual checklist](../README.md#manual-verification).

Official API references: [Pose Landmarker for web](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker/web_js), [PoseLandmarker JavaScript API](https://developers.google.com/edge/api/mediapipe/js/tasks-vision.poselandmarker).

## Integrated bilateral counter

The browser tracker now ports the pure counting logic from AdvancedAIProject;
MediaPipe still performs inference locally. It does not run the Python YOLO model.
Curls count each arm independently; the displayed total is left plus right, so a
simultaneous curl adds two. Squats use one combined counter: both visible legs
must agree on an endpoint, and a visibility-side change abandons the partial cycle.
Arm-circle tracking is unchanged. Full cycles use time-based smoothing, 120 ms
endpoint holds and a minimum 250 ms bent-to-extended return.

After selecting a camera or clip, choose **Calibrate range**, start tracking, and
perform a slow practice cycle with the same anatomical side continuously visible.
Choose **Use this range** to apply that side's demonstrated range to both sides.
At least 30 valid measurements and 60 degrees of motion are required. Practice
reps are excluded; saving is disabled during calibration. Cancel preserves the
previous thresholds. New session resets calibration. Counts measure threshold
cycles, not validated exercise technique. Entire-pose loss resets partial cycles;
individual arm dropouts of up to 450 ms preserve phase but cannot provide endpoint
hold time.

Saved summaries optionally include `counts_by_side`, `counting_method` and
`thresholds` (including `calibrated`). Existing summaries remain supported.
The feedback agent reports per-arm counts and calibrated-range provenance.

## Local model assets

The Lite model is bundled at `frontend/public/models/pose_landmarker_lite.task`.
The `predev` and `prebuild` npm hooks copy WASM assets from the installed
`@mediapipe/tasks-vision` package, keeping the runtime version aligned with its
JavaScript wrapper. Runtime loading no longer depends on Google or jsDelivr.
Run `npm run dev` or `npm run build` through npm so these hooks execute.

### Curl counting correction

Curls use the prototype's 90° bent / 145° extended thresholds and aspect-corrected
2D shoulder/elbow/wrist angles. Inferred world-depth angles can disagree with
visible elbow flexion, particularly in frontal views. Squat geometry and the
full-cycle requirement remain unchanged. Per-arm stage messages now identify the
next endpoint; the video badge distinguishes measuring from missing joints.
Regression tests cover an 80° curl and conflicting image/world geometry.
