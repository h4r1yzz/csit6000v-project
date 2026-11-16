import test from 'node:test'
import assert from 'node:assert/strict'
import { PoseAnalyzer, jointAngle } from './analysis.ts'

function points(angle, move = 'Squat', side = 'left', confidence = 0.95) {
  const frame = Array.from({ length: 33 }, () => ({ x: 0.5, y: 0.5, visibility: 0 }))
  const index = move === 'Squat' ? side === 'left' ? [23, 25, 27] : [24, 26, 28] : side === 'left' ? [11, 13, 15] : [12, 14, 16]
  const radians = angle * Math.PI / 180
  frame[index[0]] = { x: 0.5, y: 0.2, visibility: confidence }
  frame[index[1]] = { x: 0.5, y: 0.5, visibility: confidence }
  frame[index[2]] = { x: 0.5 + Math.sin(radians) * 0.3, y: 0.5 - Math.cos(radians) * 0.3, visibility: confidence }
  return frame
}
function cycle(analyzer, angles, move = 'Squat', start = 0, side = 'left', confidence = 0.95) {
  let time = start
  for (const angle of angles) for (let n = 0; n < 14; n++) { analyzer.sample(points(angle, move, side, confidence), undefined, 1, time); time += 80 }
  return time
}
function circle(theta) {
  const frame = Array.from({ length: 33 }, () => ({ x: 0.5, y: 0.5, visibility: 0 }))
  frame[11] = { x: .5, y: .5, visibility: .95 }
  frame[13] = { x: .5 + .1 * Math.cos(theta), y: .5 + .1 * Math.sin(theta), visibility: .95 }
  frame[15] = { x: .5 + .3 * Math.cos(theta), y: .5 + .3 * Math.sin(theta), visibility: .95 }
  return frame
}

test('joint geometry handles right angles and rejects collapsed joints', () => {
  assert.equal(jointAngle({ x: 0, y: 1 }, { x: 0, y: 0 }, { x: 1, y: 0 }), 90)
  assert.ok(Number.isNaN(jointAngle({ x: 0, y: 0 }, { x: 0, y: 0 }, { x: 1, y: 0 })))
})
test('squat requires full extension, flexion, extension and counts once', () => {
  const analyzer = new PoseAnalyzer('Squat')
  cycle(analyzer, [175, 75, 175, 175])
  assert.equal(analyzer.reading.reps, 1)
  assert.equal(analyzer.summary('webcam').average_confidence, .95)
  assert.ok(analyzer.summary('webcam').range_of_motion.max > 155)
})
test('starting in flexion does not count a partial rep', () => {
  const analyzer = new PoseAnalyzer('Squat')
  cycle(analyzer, [75, 175])
  assert.equal(analyzer.reading.reps, 0)
})
test('small knee movement and low visibility cannot count repetitions', () => {
  const analyzer = new PoseAnalyzer('Squat')
  cycle(analyzer, [175, 140, 175, 145, 175])
  assert.equal(analyzer.reading.reps, 0)
  const low = new PoseAnalyzer('Squat')
  cycle(low, [175, 75, 175], 'Squat', 0, 'left', .4)
  assert.equal(low.reading.reps, 0)
  assert.equal(low.summary('upload').analyzed_frames, 0)
})
test('chooses visible right side and counts curls', () => {
  const analyzer = new PoseAnalyzer('Bicep curl')
  cycle(analyzer, [175, 30, 175], 'Bicep curl', 0, 'right')
  assert.equal(analyzer.reading.side, 'right')
  assert.equal(analyzer.reading.reps, 1)
})
test('visibility loss and a seek gap reset an incomplete repetition', () => {
  const analyzer = new PoseAnalyzer('Squat')
  const next = cycle(analyzer, [175, 75])
  analyzer.missing()
  cycle(analyzer, [175], 'Squat', next + 2000)
  assert.equal(analyzer.reading.reps, 0)
  const gap = new PoseAnalyzer('Squat')
  const time = cycle(gap, [175, 75])
  cycle(gap, [175], 'Squat', time + 2000)
  assert.equal(gap.reading.reps, 0)
})
test('arm circles count a complete rotation, not forward-back wobbling', () => {
  const full = new PoseAnalyzer('Arm circles')
  for (let i = 0; i <= 45; i++) full.sample(circle(i / 45 * Math.PI * 2), undefined, 1, i * 80)
  assert.equal(full.reading.reps, 1)
  const wobble = new PoseAnalyzer('Arm circles')
  for (let i = 0; i < 200; i++) wobble.sample(circle(Math.sin(i / 10)), undefined, 1, i * 80)
  assert.equal(wobble.reading.reps, 0)
})

test('landmark snapshots are numerical, bounded and sampled at least a second apart', () => {
  const analyzer = new PoseAnalyzer('Squat')
  for (let i = 0; i < 200; i++) analyzer.sample(points(175), undefined, 1, i * 80)
  const summary = analyzer.summary('webcam')
  assert.equal(summary.landmark_samples.length, 8)
  assert.equal(summary.landmark_samples[0].landmarks.length, 33)
  for (let i = 1; i < summary.landmark_samples.length; i++) assert.ok(summary.landmark_samples[i].time_seconds - summary.landmark_samples[i - 1].time_seconds >= 1)
  assert.ok(summary.landmark_samples.at(-1).time_seconds <= summary.duration_seconds)
  assert.deepEqual(Object.keys(summary.landmark_samples[0].landmarks[0]), ['x', 'y', 'z', 'visibility'])
  summary.landmark_samples[0].landmarks[0].x = 999
  assert.notEqual(analyzer.summary('webcam').landmark_samples[0].landmarks[0].x, 999)
  assert.equal(new PoseAnalyzer('Squat').summary('webcam').landmark_samples.length, 0)
})
test('invalid numerical landmark snapshots are omitted without inventing coordinates', () => {
  const analyzer = new PoseAnalyzer('Squat')
  const frame = points(175)
  frame[0].x = Infinity
  analyzer.sample(frame, undefined, 1, 0)
  assert.equal(analyzer.summary('webcam').landmark_samples.length, 0)
})

function bilateral(analyzer, sequence, move = 'Bicep curl', start = 0) {
  let time = start
  for (const [left, right] of sequence) for (let n = 0; n < 16; n++) {
    const frame = left === null ? points(175, move, 'left', 0) : points(left, move)
    if (right !== null) {
      const other = points(right, move, 'right')
      other.forEach((point, i) => { if (point.visibility) frame[i] = point })
    }
    analyzer.sample(frame, undefined, 1, time); time += 80
  }
  return time
}
test('alternating and simultaneous curls preserve independent arm totals', () => {
  const a = new PoseAnalyzer('Bicep curl')
  bilateral(a, [[175,175],[30,175],[175,175],[175,30],[175,175],[30,30],[175,175]])
  assert.deepEqual(a.summary('webcam').counts_by_side, {left: 2, right: 2})
  assert.equal(a.reading.reps, 4)
})
test('squats require agreement and abandon partial cycles on visible limb change', () => {
  const a = new PoseAnalyzer('Squat')
  bilateral(a, [[175,175],[75,175],[175,175]], 'Squat')
  assert.equal(a.reading.reps, 0)
  const b = new PoseAnalyzer('Squat')
  bilateral(b, [[175,null],[75,null],[null,175]], 'Squat')
  assert.equal(b.reading.reps, 0)
})
test('calibration excludes practice reps and persists accepted thresholds', () => {
  const a = new PoseAnalyzer('Bicep curl')
  a.startCalibration()
  assert.throws(() => a.finishCalibration(), /30 frames/)
  const next = bilateral(a, [[175,175],[30,30],[175,175]])
  assert.equal(a.reading.reps, 0)
  a.finishCalibration()
  bilateral(a, [[175,175],[30,30],[175,175]], 'Bicep curl', next)
  assert.equal(a.reading.reps, 2)
  assert.equal(a.summary('webcam').thresholds.calibrated, true)
})
test('calibration rejects tiny range and cancellation preserves completed reps', () => {
  const a = new PoseAnalyzer('Bicep curl')
  let next = bilateral(a, [[175,null],[30,null],[175,null]])
  a.startCalibration()
  next = bilateral(a, [[175,null],[165,null],[175,null]], 'Bicep curl', next)
  assert.throws(() => a.finishCalibration(), /60°/)
  a.cancelCalibration()
  bilateral(a, [[175,null]], 'Bicep curl', next)
  assert.equal(a.reading.reps, 1)
  assert.equal(a.reading.calibrating, false)
})

test('time-based counters tolerate short gaps but reject long occlusions and spikes', async () => {
  const { RepCounter } = await import('./counter.ts')
  for (const fps of [15, 30, 60]) {
    const counter = new RepCounter(90, 145)
    let t = 0
    const hold = value => { for (let i = 0; i < fps; i++) { counter.update(value, t); t += 1 / fps } }
    hold(175); hold(70)
    counter.update(null, t); t += .2
    hold(175)
    assert.equal(counter.count, 1)
    hold(70); counter.update(null, t); t += 1; hold(175)
    assert.equal(counter.count, 1)
    counter.update(30, t); t += 1 / fps; hold(175)
    assert.equal(counter.count, 1)
  }
})

test('curl counts an 80-degree bend using prototype thresholds', () => {
  const a = new PoseAnalyzer('Bicep curl')
  cycle(a, [170, 80, 170], 'Bicep curl')
  assert.equal(a.reading.reps, 1)
  assert.equal(a.summary('webcam').thresholds.bent, 90)
})
test('curl uses aspect-corrected image angles even when inferred world depth disagrees', () => {
  const a = new PoseAnalyzer('Bicep curl')
  let time = 0
  for (const [imageAngle, worldAngle] of [[175, 142], [50, 81], [175, 142]]) {
    for (let i = 0; i < 16; i++) {
      const frame = points(imageAngle, 'Bicep curl')
      frame.forEach(p => { p.x /= 16 / 9 })
      const world = points(worldAngle, 'Bicep curl').map(p => ({ ...p, z: 0 }))
      a.sample(frame, world, 16 / 9, time); time += 80
    }
  }
  assert.equal(a.reading.reps, 1)
  assert.equal(a.reading.angle, 175)
})
test('curl instructions expose each phase and missing joints', () => {
  const a = new PoseAnalyzer('Bicep curl')
  let time = cycle(a, [110], 'Bicep curl')
  assert.match(a.reading.arms.left.instruction, /Straighten past 145/)
  time = cycle(a, [175], 'Bicep curl', time)
  assert.match(a.reading.arms.left.instruction, /Bend below 90/)
  cycle(a, [75], 'Bicep curl', time)
  assert.match(a.reading.arms.left.instruction, /Bend reached/)
  assert.equal(a.reading.arms.right.angle, null)
  a.missing()
  assert.equal(a.reading.arms.left.angle, null)
  assert.match(a.reading.arms.left.instruction, /Show shoulder/)
})
