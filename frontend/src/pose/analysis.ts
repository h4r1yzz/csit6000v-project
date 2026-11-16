import { RepCounter, Calibration } from './counter.ts'
export type Move = 'Squat' | 'Bicep curl' | 'Arm circles'
export type Point = { x: number; y: number; z?: number; visibility?: number; presence?: number }
export type LandmarkSample = { time_seconds: number; landmarks: { x: number; y: number; z: number; visibility: number }[] }
export type PoseSummary = {
  exercise: Move
  duration_seconds: number
  reps: number
  analyzed_frames: number
  average_confidence: number
  range_of_motion: { min: number; max: number }
  form_cues: string[]
  landmark_samples: LandmarkSample[]
  counts_by_side?: { left: number; right: number }
  counting_method?: string
  thresholds?: { bent: number; extended: number; calibrated: boolean }
  source: 'webcam' | 'upload'
}
export type ArmReading = { angle: number | null; instruction: string }
export type Reading = { arms?: { left: ArmReading; right: ArmReading }; leftReps?: number; rightReps?: number; calibrating?: boolean; reps: number; angle: number | null; confidence: number; side: 'left' | 'right' | null; feedback: string; frames: number; seconds: number }
const VISIBILITY = 0.65
const SIDES = { left: { shoulder: 11, elbow: 13, wrist: 15, hip: 23, knee: 25, ankle: 27 }, right: { shoulder: 12, elbow: 14, wrist: 16, hip: 24, knee: 26, ankle: 28 } }

/** World coordinates avoid image aspect distortion; image points are scaled first. */
export function jointAngle(a: Point, b: Point, c: Point): number {
  const u = [a.x - b.x, a.y - b.y, (a.z ?? 0) - (b.z ?? 0)]
  const v = [c.x - b.x, c.y - b.y, (c.z ?? 0) - (b.z ?? 0)]
  const length = Math.hypot(...u) * Math.hypot(...v)
  return length > 1e-8 ? Math.acos(Math.max(-1, Math.min(1, u.reduce((sum, n, i) => sum + n * v[i], 0) / length))) * 180 / Math.PI : NaN
}
function confidence(point?: Point): number {
  return point && Number.isFinite(point.x) && Number.isFinite(point.y) ? Math.min(point.visibility ?? 0, point.presence ?? 1) : 0
}

export class PoseAnalyzer {
  readonly exercise: Move
  private reps = 0
  private frames = 0
  private confidenceSum = 0
  private durationMs = 0
  private previousTime: number | null = null
  private side: 'left' | 'right' | null = null
  private counters: Record<'left' | 'right' | 'combined', RepCounter>
  private visibleSource = ''
  private calibration: Calibration | null = null
  private calibrationSide: 'left' | 'right' | null = null
  private calibrated = false
  private previousTheta: number | null = null
  private circleStarted = 0
  private rotation = 0
  private lastRep = -Infinity
  private minAngle = Infinity
  private maxAngle = -Infinity
  private cues = new Set<string>()
  private landmarkSamples: LandmarkSample[] = []
  private lastSnapshotMs = -Infinity
  reading: Reading = { reps: 0, angle: null, confidence: 0, side: null, feedback: 'Keep the whole movement in frame in good lighting.', frames: 0, seconds: 0 }

  constructor(exercise: Move) {
    this.exercise = exercise
    const bent = exercise === 'Squat' ? 100 : 90, extended = exercise === 'Squat' ? 155 : 145
    this.counters = { left: new RepCounter(bent, extended), right: new RepCounter(bent, extended), combined: new RepCounter(bent, extended) }
  }

  startCalibration() {
    if (this.exercise === 'Arm circles') return
    this.calibration = new Calibration(); this.calibrationSide = null; this.resetMotion()
    this.reading = { ...this.reading, calibrating: true, feedback: 'Perform a slow practice cycle with one side continuously visible, then use this range.' }
  }

  finishCalibration() {
    if (!this.calibration) return
    const thresholds = this.calibration.thresholds()
    for (const counter of Object.values(this.counters)) Object.assign(counter, thresholds)
    this.calibration = null; this.calibrationSide = null; this.calibrated = true; this.resetMotion()
    this.reading = { ...this.reading, calibrating: false, feedback: 'Range applied to both sides. Extend to begin counting; practice repetitions were excluded.' }
  }

  cancelCalibration() {
    this.calibration = null; this.calibrationSide = null; this.resetMotion()
    this.reading = { ...this.reading, calibrating: false, feedback: 'Calibration cancelled. Extend to begin counting.' }
  }

  private resetMotion() {
    Object.values(this.counters).forEach(counter => counter.reset())
    this.visibleSource = ''; this.previousTheta = null; this.rotation = 0
  }

  missing(): Reading {
    this.resetMotion(); this.previousTime = null
    const instruction = 'Show shoulder, elbow and wrist together.'
    this.reading = { ...this.reading, arms: { left: { angle: null, instruction }, right: { angle: null, instruction } }, angle: null, confidence: 0, feedback: this.exercise === 'Squat' ? 'Show your hip, knee and ankle together.' : instruction }
    return this.reading
  }

  sample(points: Point[], world: Point[] | undefined, aspect: number, timestamp: number): Reading {
    const required = (side: keyof typeof SIDES) => {
      const s = SIDES[side]
      return this.exercise === 'Squat' ? [s.hip, s.knee, s.ankle] : [s.shoulder, s.elbow, s.wrist]
    }
    const sideConfidence = (side: keyof typeof SIDES) => Math.min(...required(side).map(i => confidence(points[i])))
    const best = sideConfidence('left') >= sideConfidence('right') ? 'left' : 'right'
    const chosen = this.side && sideConfidence(this.side) >= VISIBILITY ? this.side : best
    const visible = sideConfidence(chosen)
    if (visible < VISIBILITY) return this.missing()
    if (this.side !== chosen && this.exercise === 'Arm circles') this.resetMotion()
    this.side = chosen
    if (this.previousTime !== null) {
      const delta = timestamp - this.previousTime
      if (delta < 0 || delta > 500) this.resetMotion()
      else this.durationMs += delta
    }
    this.previousTime = timestamp
    // Share at most eight numerical snapshots, sampled no more than once per
    // second of confident tracking. Images and video frames never leave the browser.
    if (this.durationMs - this.lastSnapshotMs >= 1000 && points.length === 33) {
      const landmarks = points.map(p => ({ x: p.x, y: p.y, z: p.z ?? 0, visibility: p.visibility ?? 0 }))
      if (landmarks.every(p => Number.isFinite(p.x) && p.x >= -2 && p.x <= 3 && Number.isFinite(p.y) && p.y >= -2 && p.y <= 3 && Number.isFinite(p.z) && p.z >= -10 && p.z <= 10 && Number.isFinite(p.visibility) && p.visibility >= 0 && p.visibility <= 1)) {
        this.landmarkSamples.push({ time_seconds: Number((this.durationMs / 1000).toFixed(3)), landmarks })
        this.landmarkSamples = this.landmarkSamples.slice(-8)
        this.lastSnapshotMs = this.durationMs
      }
    }
    this.frames++; this.confidenceSum += visible
    const s = SIDES[chosen]
    const coord = (index: number): Point => world?.[index] && Number.isFinite(world[index].z) ? world[index] : { x: points[index].x * aspect, y: points[index].y, z: 0 }
    let currentAngle: number
    let cue = ''
    let arms: Reading['arms']
    if (this.exercise === 'Arm circles') {
      // Frontal image plane measures shoulder-relative rotation, not depth motion.
      const dx = (points[s.wrist].x - points[s.shoulder].x) * aspect
      const dy = points[s.wrist].y - points[s.shoulder].y
      const shoulderToElbow = Math.hypot((points[s.elbow].x - points[s.shoulder].x) * aspect, points[s.elbow].y - points[s.shoulder].y)
      if (Math.hypot(dx, dy) < Math.max(0.06, shoulderToElbow * 0.8)) {
        this.previousTheta = null; this.rotation = 0
        cue = 'Face the camera and extend your arm comfortably so the circle is visible.'
      } else {
        const theta = Math.atan2(dy, dx)
        if (this.previousTheta === null) this.circleStarted = timestamp
        if (this.previousTheta !== null) {
          let delta = theta - this.previousTheta
          if (delta > Math.PI) delta -= Math.PI * 2
          if (delta < -Math.PI) delta += Math.PI * 2
          // A large jump is a tracking discontinuity, not a valid rotation.
          if (Math.abs(delta) < Math.PI / 3) this.rotation += delta
          else this.rotation = 0
          if (Math.abs(this.rotation) >= Math.PI * 2 - 0.15 && timestamp - this.circleStarted >= 700 && timestamp - this.lastRep >= 700) {
            this.reps++; this.lastRep = timestamp; this.rotation = 0; this.circleStarted = timestamp
          }
        }
        this.previousTheta = theta
        cue = 'Make smooth circles facing the camera; keep your shoulder relaxed.'
      }
      currentAngle = (Math.atan2(dy, dx) * 180 / Math.PI + 360) % 360
    } else {
      const measure = (side: 'left' | 'right'): number | null => {
        if (sideConfidence(side) < VISIBILITY) return null
        const indices = required(side)
        if (indices.some(i => points[i].x <= 0 || points[i].x >= 1 || points[i].y <= 0 || points[i].y >= 1)) return null
        // Match AdvancedAIProject's pixel-plane curl geometry. Monocular world
        // depth can report a visibly straight arm as bent in a frontal view.
        const coordinates = indices.map(i => this.exercise === 'Bicep curl'
          ? { x: points[i].x * aspect, y: points[i].y, z: 0 } : coord(i))
        const value = jointAngle(...coordinates as [Point, Point, Point])
        return Number.isFinite(value) ? value : null
      }
      const values = { left: measure('left'), right: measure('right') }
      const valid = Object.values(values).filter((v): v is number => v !== null)
      if (!valid.length) return this.missing()
      currentAngle = values[chosen] ?? valid[0]
      if (this.calibration) {
        this.calibrationSide ??= chosen
        this.calibration.add(values[this.calibrationSide])
        cue = `Practice slowly with your ${this.calibrationSide} side visible. This range will apply to both sides; practice reps are excluded.`
      } else if (this.exercise === 'Bicep curl') {
        this.counters.left.update(values.left, timestamp / 1000)
        this.counters.right.update(values.right, timestamp / 1000)
        this.reps = this.counters.left.count + this.counters.right.count
        const armReading = (side: 'left' | 'right'): ArmReading => {
          const counter = this.counters[side], angle = values[side]
          const instruction = angle === null ? 'Show shoulder, elbow and wrist together.'
            : counter.phase === 'find_start' ? `Straighten past ${Math.round(counter.extended)}° and briefly hold to start.`
            : counter.phase === 'ready' ? `Bend below ${Math.round(counter.bent)}° and briefly hold.`
            : `Bend reached — straighten past ${Math.round(counter.extended)}° to finish.`
          return { angle: angle === null ? null : Math.round(angle), instruction }
        }
        arms = { left: armReading('left'), right: armReading('right') }
        cue = `${chosen === 'left' ? 'Left' : 'Right'} arm: ${arms[chosen].instruction}`
      } else {
        const source = Object.keys(values).filter(side => values[side as 'left' | 'right'] !== null).join('+')
        const counter = this.counters.combined
        if (this.visibleSource && source !== this.visibleSource) counter.reset()
        this.visibleSource = source
        const value = valid.every(v => v >= counter.extended) ? Math.min(...valid)
          : valid.every(v => v <= counter.bent) ? Math.max(...valid) : (counter.bent + counter.extended) / 2
        counter.update(value, timestamp / 1000)
        this.reps = counter.count
        cue = 'Stand tall, lower, then stand tall again. Both visible legs must reach each endpoint together.'
      }
      if (this.exercise === 'Bicep curl' && !this.calibration) {
        const shoulder = points[s.shoulder], elbow = points[s.elbow], hip = points[s.hip]
        const torso = hip ? Math.hypot((hip.x - shoulder.x) * aspect, hip.y - shoulder.y) : 0
        if (confidence(hip) >= VISIBILITY && torso > 0 && Math.abs(elbow.x - shoulder.x) * aspect / torso > 0.45) cue += ' Keep your upper arm steady.'
      }
    }
    this.minAngle = Math.min(this.minAngle, currentAngle); this.maxAngle = Math.max(this.maxAngle, currentAngle)
    this.cues.add(cue)
    this.reading = { arms, leftReps: this.counters.left.count, rightReps: this.counters.right.count, calibrating: this.calibration !== null, reps: this.reps, angle: Math.round(currentAngle), confidence: visible, side: chosen, feedback: cue, frames: this.frames, seconds: this.durationMs / 1000 }
    return this.reading
  }

  summary(source: 'webcam' | 'upload'): PoseSummary {
    return {
      ...(this.exercise === 'Arm circles' ? {} : { counting_method: this.exercise === 'Bicep curl' ? 'full_cycles_per_arm_sum' : 'bilateral_full_cycles', thresholds: { bent: this.counters.combined.bent, extended: this.counters.combined.extended, calibrated: this.calibrated } }),
      ...(this.exercise === 'Bicep curl' ? { counts_by_side: { left: this.counters.left.count, right: this.counters.right.count } } : {}),
      exercise: this.exercise, duration_seconds: Math.max(1, Number((this.durationMs / 1000).toFixed(3))), reps: this.reps,
      analyzed_frames: this.frames, average_confidence: this.frames ? Number((this.confidenceSum / this.frames).toFixed(3)) : 0,
      range_of_motion: { min: Number.isFinite(this.minAngle) ? Math.round(this.minAngle) : 0, max: Number.isFinite(this.maxAngle) ? Math.round(this.maxAngle) : 0 },
      form_cues: [...this.cues].slice(-8), landmark_samples: this.landmarkSamples.map(sample => ({ time_seconds: sample.time_seconds, landmarks: sample.landmarks.map(p => ({ ...p })) })), source,
    }
  }
}
