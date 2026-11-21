import { useEffect, useRef, useState } from 'react'
import { AlertCircle, Camera, CameraOff, Check, LoaderCircle, Pause, Play, RotateCcw, ShieldCheck, Sparkles } from 'lucide-react'
import { DrawingUtils, FilesetResolver, PoseLandmarker } from '@mediapipe/tasks-vision'
import { api } from './api'
import { PoseAnalyzer } from './pose/analysis'
import type { Move, Reading } from './pose/analysis'
import './PoseCoach.css'
import ExerciseGuide from './ExerciseGuide'

type Props = {
  onLog: (exercise: string, minutes: number, effort: number, notes: string) => Promise<void>
  onSessionSaved?: () => void | Promise<void>
}
type AgentFeedback = { source: string; output: { summary?: string; observations?: string[]; suggestions?: string[]; confidence_note?: string } }
const MOVES: Move[] = ['Squat', 'Bicep curl', 'Arm circles']
const clock = (seconds: number) => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`
const MODEL = '/models/pose_landmarker_lite.task'

export default function PoseCoach({ onLog, onSessionSaved }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const taskRef = useRef<PoseLandmarker | null>(null)
  const initialization = useRef<Promise<PoseLandmarker | null> | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const rafRef = useRef(0)
  const mounted = useRef(true)
  const intent = useRef(0)
  const analyzerRef = useRef(new PoseAnalyzer('Squat'))
  const sourceRef = useRef<'webcam' | null>(null)
  const lastFrame = useRef(-1)
  const lastInference = useRef(0)
  const lastUi = useRef(0)
  const runningRef = useRef(false)
  const savedIdRef = useRef<number | null>(null)
  const savedSummaryRef = useRef<ReturnType<PoseAnalyzer['summary']> | null>(null)
  const [exercise, setExercise] = useState<Move>('Squat')
  const [source, setSource] = useState<'webcam' | null>(null)
  const [loading, setLoading] = useState(false)
  const [cameraPending, setCameraPending] = useState(false)
  const [cameraActive, setCameraActive] = useState(false)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')
  const [reading, setReading] = useState<Reading>(analyzerRef.current.reading)
  const [aspect, setAspect] = useState(16 / 9)
  const [saved, setSaved] = useState(false)
  const [saving, setSaving] = useState(false)
  const [effort, setEffort] = useState(5)
  const [feedback, setFeedback] = useState<AgentFeedback | null>(null)
  const [feedbackBusy, setFeedbackBusy] = useState(false)
  const [feedbackError, setFeedbackError] = useState('')

  function pause() {
    intent.current++
    runningRef.current = false
    cancelAnimationFrame(rafRef.current)
    videoRef.current?.pause()
    if (mounted.current) { setRunning(false); setReading({ ...analyzerRef.current.reading }) }
  }

  function stopCamera(clearSource = true) {
    intent.current++
    pause()
    streamRef.current?.getTracks().forEach(track => track.stop())
    streamRef.current = null
    if (clearSource && videoRef.current) videoRef.current.srcObject = null
    if (clearSource && sourceRef.current === 'webcam') { sourceRef.current = null; setSource(null) }
    setCameraActive(false); setCameraPending(false)
  }

  function resetSession(move: Move = exercise) {
    pause()
    analyzerRef.current = new PoseAnalyzer(move)
    setReading({ ...analyzerRef.current.reading })
    lastFrame.current = -1
    savedIdRef.current = null; savedSummaryRef.current = null
    setSaved(false); setFeedback(null); setFeedbackError(''); setError('')
  }

  useEffect(() => {
    mounted.current = true
    const pageHidden = () => { if (document.hidden) pause() }
    document.addEventListener('visibilitychange', pageHidden)
    return () => {
      mounted.current = false; intent.current++
      cancelAnimationFrame(rafRef.current)
      streamRef.current?.getTracks().forEach(track => track.stop())
      if (videoRef.current) videoRef.current.srcObject = null
      taskRef.current?.close(); taskRef.current = null
      document.removeEventListener('visibilitychange', pageHidden)
    }
  }, [])

  async function initialize(): Promise<PoseLandmarker | null> {
    if (taskRef.current) return taskRef.current
    if (initialization.current) return initialization.current
    setLoading(true); setError('')
    initialization.current = (async () => {
      try {
        const vision = await FilesetResolver.forVisionTasks('/mediapipe/wasm')
        let task: PoseLandmarker
        const options = { runningMode: 'VIDEO' as const, numPoses: 1, minPoseDetectionConfidence: 0.6, minPosePresenceConfidence: 0.6, minTrackingConfidence: 0.6 }
        try { task = await PoseLandmarker.createFromOptions(vision, { ...options, baseOptions: { modelAssetPath: MODEL, delegate: 'GPU' } }) }
        catch { task = await PoseLandmarker.createFromOptions(vision, { ...options, baseOptions: { modelAssetPath: MODEL, delegate: 'CPU' } }) }
        if (!mounted.current) { task.close(); return null }
        taskRef.current = task
        return task
      } catch (error) {
        console.error('Local pose model initialization failed:', error)
        if (mounted.current) setError('The pose tracker could not initialize. Reload the page and try again. If this persists, restart the app with npm run dev and check the browser console for the loading error.')
        return null
      } finally {
        initialization.current = null
        if (mounted.current) setLoading(false)
      }
    })()
    return initialization.current
  }

  function startLoop() {
    cancelAnimationFrame(rafRef.current)
    runningRef.current = true; setRunning(true)
    const draw = (now: number) => {
      const video = videoRef.current, canvas = canvasRef.current, task = taskRef.current
      if (!mounted.current || !runningRef.current || !video || !canvas || !task) return
      if (video.paused || video.ended) { pause(); return }
      // Inference is synchronous; cap at 15 fps and never process a frame twice.
      if (video.readyState >= 2 && video.currentTime !== lastFrame.current && now - lastInference.current >= 66) {
        lastFrame.current = video.currentTime; lastInference.current = now
        try {
          const result = task.detectForVideo(video, now)
          const ctx = canvas.getContext('2d')
          if (ctx) {
            if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) { canvas.width = video.videoWidth; canvas.height = video.videoHeight }
            ctx.clearRect(0, 0, canvas.width, canvas.height)
            const landmarks = result.landmarks[0]
            if (landmarks) {
              const visible = landmarks.map(p => ({ ...p, visibility: (p.visibility ?? 0) >= 0.65 ? p.visibility : 0 }))
              const painter = new DrawingUtils(ctx)
              painter.drawConnectors(visible, PoseLandmarker.POSE_CONNECTIONS.filter(c => visible[c.start].visibility >= 0.65 && visible[c.end].visibility >= 0.65), { color: '#badb88', lineWidth: Math.max(2, canvas.width / 300) })
              painter.drawLandmarks(visible.filter(p => p.visibility >= 0.65), { color: '#ffffff', fillColor: '#6e9b51', lineWidth: 1, radius: Math.max(3, canvas.width / 240) })
              analyzerRef.current.sample(landmarks, result.worldLandmarks[0], video.videoWidth / video.videoHeight, video.currentTime * 1000)
            } else analyzerRef.current.missing()
          }
          if (now - lastUi.current > 150) { setReading({ ...analyzerRef.current.reading }); lastUi.current = now }
        } catch {
          pause(); setError('Pose tracking stopped unexpectedly. Reset the session and try again.'); return
        }
      }
      rafRef.current = requestAnimationFrame(draw)
    }
    rafRef.current = requestAnimationFrame(draw)
  }

  async function play() {
    if (saving || saved || !sourceRef.current) return
    const currentVideo = videoRef.current
    if (currentVideo?.ended) { resetSession(); currentVideo.currentTime = 0 }
    const request = ++intent.current
    const task = await initialize()
    if (!task || request !== intent.current || !mounted.current) return
    const video = videoRef.current
    if (!video) return
    try {
      await video.play()
      if (request !== intent.current || !mounted.current) { video.pause(); return }
      startLoop()
    } catch { setError('The camera preview could not play. Restart the camera and try again.') }
  }

  async function startCamera() {
    if (cameraPending || saving) return
    stopCamera(); resetSession()
    const request = ++intent.current
    setCameraPending(true)
    try {
      if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) throw new Error('Camera access requires localhost or HTTPS and a supported browser.')
      const task = await initialize()
      if (!task || request !== intent.current) return
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false })
      if (!mounted.current || request !== intent.current) { stream.getTracks().forEach(track => track.stop()); return }
      streamRef.current = stream
      setCameraActive(true)
      const video = videoRef.current
      if (!video) { stream.getTracks().forEach(track => track.stop()); return }
      video.removeAttribute('src'); video.srcObject = stream
      sourceRef.current = 'webcam'; setSource('webcam')
      await video.play()
      if (request !== intent.current) return
      startLoop()
    } catch (e) {
      if (request !== intent.current || !mounted.current) return
      stopCamera()
      const name = e instanceof Error ? e.name : ''
      setError(name === 'NotAllowedError' ? 'Camera permission was denied. Allow camera access in your browser.' : name === 'NotFoundError' ? 'No camera was found. Connect a camera and try again.' : e instanceof Error && e.message.includes('requires') ? e.message : 'The camera could not start. Check that another app is not using it.')
    } finally { if (mounted.current) setCameraPending(false) }
  }

  async function saveSession() {
    if (saving || saved || analyzerRef.current.reading.calibrating || !sourceRef.current) return
    pause(); setSaving(true); setError('')
    try {
      const summary = savedSummaryRef.current ?? analyzerRef.current.summary(sourceRef.current)
      if (summary.analyzed_frames < 10) throw new Error('Track at least 10 confident frames before saving a session.')
      if (savedIdRef.current === null) {
        const result = await api.post<{ id: number }>('/api/pose-sessions', summary)
        savedIdRef.current = result.id; savedSummaryRef.current = summary
      }
      await onLog(summary.exercise, Math.max(1, Math.ceil(summary.duration_seconds / 60)), effort, `${summary.reps} reps${summary.counts_by_side ? ` (left ${summary.counts_by_side.left}, right ${summary.counts_by_side.right}; total arm cycles)` : ''}; ${Math.round(summary.average_confidence * 100)}% landmark confidence; ${summary.range_of_motion.min}–${summary.range_of_motion.max}° angle range; pose session #${savedIdRef.current}`)
      if (mounted.current) { setSaved(true); void onSessionSaved?.() }
    } catch (e) { if (mounted.current) setError(e instanceof Error ? e.message : 'The session could not be saved. Please retry.') }
    finally { if (mounted.current) setSaving(false) }
  }

  async function getFeedback() {
    if (savedIdRef.current === null || feedbackBusy) return
    setFeedbackBusy(true); setFeedbackError('')
    try {
      const result = await api.post<AgentFeedback>('/api/agents/exercise_feedback/run', { pose_session_id: savedIdRef.current })
      if (mounted.current) setFeedback(result)
    } catch (e) { if (mounted.current) setFeedbackError(e instanceof Error ? e.message : 'Feedback could not be loaded. Try again.') }
    finally { if (mounted.current) setFeedbackBusy(false) }
  }

  const sessionFrozen = saving || savedIdRef.current !== null
  return <section className="pose-card pose-tracker" aria-label="Pose estimation tracker">
    <div className="studio-intro"><div><span className="studio-eyebrow">A LITTLE MOVEMENT. A BETTER DAY.</span><h1>Your workout, <strong>in focus.</strong></h1><p>A little guidance on one side. Your progress on the other.</p></div><span className="pose-privacy"><ShieldCheck size={14} /> Video stays on your device</span></div>
    <div className="tracker-controls">
      <label className="field compact"><span>Movement</span><select value={exercise} disabled={saving || feedbackBusy} onChange={e => { const move = e.target.value as Move; setExercise(move); resetSession(move) }}>{MOVES.map(move => <option key={move}>{move}</option>)}</select></label>
      {source === 'webcam' && cameraActive ? <button className="quiet-button tracker-source-button" disabled={saving} onClick={() => stopCamera(false)}><CameraOff size={16} /> Stop camera</button> : <button className="quiet-button tracker-source-button" disabled={cameraPending || loading || saving || feedbackBusy} onClick={() => void startCamera()}>{cameraPending ? <LoaderCircle size={16} className="spin" /> : <Camera size={16} />} {cameraPending ? 'Starting camera…' : 'Use camera'}</button>}
      <span className="tracker-file">Live camera · audio off</span>
    </div>
    <div className="studio-workspace"><ExerciseGuide exercise={exercise}/><div className="practice-panel">
    <div className="studio-panel-title"><span className="panel-number">02</span><h2>Your practice</h2><span className="studio-tag">Live camera</span></div>
    <div className={`tracker-stage ${source ? 'has-video' : ''}`}>
      <div className="tracker-video-frame" style={{ aspectRatio: aspect, width: `min(100%, ${aspect * 360}px)`, display: source ? undefined : 'none' }}>
        <video ref={videoRef} muted playsInline preload="metadata" aria-label="Live movement camera" onLoadedMetadata={() => { const v = videoRef.current; if (v?.videoWidth && v.videoHeight) setAspect(v.videoWidth / v.videoHeight) }} onEnded={pause} onError={() => { if (sourceRef.current) { pause(); setError('The camera preview could not be opened. Restart the camera and try again.') } }} />
        <canvas ref={canvasRef} className="tracker-overlay" aria-hidden="true" />
        <span className={`tracker-live ${running ? 'is-running' : ''}`}><i />{running ? reading.calibrating ? 'CALIBRATING' : reading.angle === null ? 'JOINTS NOT VISIBLE' : 'MEASURING' : 'PAUSED'}</span>
      </div>
      {!source && <div className="tracker-empty"><div className="camera-orbit"><Camera size={29} /></div><strong>Your space to move.</strong><span>{exercise === 'Squat' ? 'Step back until your hips, knees and ankles are visible.' : exercise === 'Bicep curl' ? 'Keep your shoulder, elbow and wrist in view.' : 'Face the camera with room to extend your arms.'}</span><button className="primary-button" disabled={cameraPending || loading} onClick={() => void startCamera()}><Camera size={15} /> Start your camera</button></div>}
      {loading && <div className="tracker-loading" role="status"><LoaderCircle className="spin" size={24} /><strong>Preparing your pose model…</strong><span>Loading the pose model from this app…</span></div>}
    </div>
    <div className="studio-score"><div className="studio-reps" aria-live="polite" aria-atomic="true"><strong>{String(reading.reps).padStart(2, '0')}</strong><span>{exercise === 'Bicep curl' ? 'Total arm reps' : 'Completed reps'}</span></div>{exercise === 'Bicep curl' && <div className="studio-side-counts"><span>Left <b>{reading.leftReps ?? 0}</b></span><span>Right <b>{reading.rightReps ?? 0}</b></span></div>}<div className="studio-time"><strong>{clock(reading.seconds)}</strong><span>Time in view</span></div></div>
    <div className="tracker-cue" role="status"><span className={`live-dot ${!running || reading.angle === null ? 'inactive' : ''}`} /><div><strong>{saved ? 'Session saved' : !source ? 'Ready when you are' : !running ? 'Session paused' : reading.calibrating ? 'Learning your range' : reading.angle === null ? 'Let’s get you in frame' : 'Your next move'}</strong><p>{saved ? 'Your movement is saved. Ask the coach for a session review below.' : !source ? 'Start your camera to begin.' : !running ? 'Resume tracking when you’re ready to continue.' : reading.feedback}</p></div></div>
    {source && <div className="tracker-playback"><button className="primary-button small" disabled={loading || sessionFrozen || (source === 'webcam' && !cameraActive)} onClick={() => running ? pause() : void play()}>{running ? <Pause size={15} /> : <Play size={15} />}{running ? 'Pause' : 'Start tracking'}</button><span className="tracker-angle-note">{exercise === 'Arm circles' ? 'Wrist rotation · face camera' : 'Joint angle · side view recommended'}</span></div>}
    <div className="tracker-actions"><button className="quiet-button" disabled={saving || feedbackBusy} onClick={() => resetSession()}><RotateCcw size={14} /> New session</button><label className="tracker-effort">Effort <select value={effort} disabled={saving || saved} onChange={e => setEffort(Number(e.target.value))} aria-label="Perceived effort from 1 to 10">{Array.from({ length: 10 }, (_, i) => <option key={i + 1} value={i + 1}>{i + 1}/10</option>)}</select></label><button className="primary-button small" disabled={reading.calibrating || reading.frames < 10 || saving || saved || feedbackBusy} onClick={() => void saveSession()}>{saving ? <LoaderCircle size={14} className="spin" /> : saved ? <Check size={14} /> : <Check size={14} />}{saving ? 'Saving…' : saved ? 'Session saved' : savedIdRef.current ? 'Retry workout log' : 'Finish & save'}</button></div>
    </div></div>
    {error && <div className="inline-error" role="alert"><AlertCircle size={16} />{error}</div>}
    <details className="studio-details"><summary>Tracking details &amp; calibration <span>Angles, visibility and your counting range</span></summary><div className="studio-details-content">
    {source && exercise !== 'Arm circles' && <div className="tracker-controls">
      <button className="quiet-button" disabled={sessionFrozen || feedbackBusy} onClick={() => {
        try {
          if (reading.calibrating) analyzerRef.current.finishCalibration()
          else analyzerRef.current.startCalibration()
          setReading({ ...analyzerRef.current.reading }); setError('')
        } catch (e) { setError(e instanceof Error ? e.message : 'Calibration failed.') }
      }}>{reading.calibrating ? 'Use this range' : 'Calibrate range'}</button>
      {reading.calibrating && <button className="quiet-button" onClick={() => { analyzerRef.current.cancelCalibration(); setReading({ ...analyzerRef.current.reading }); setError('') }}>Cancel calibration</button>}
      <span className="tracker-angle-note">{reading.calibrating ? 'Start tracking and perform a slow practice cycle. Keep the same side visible.' : 'Optional: use your demonstrated range for both sides.'}</span>
    </div>}
    {exercise === 'Bicep curl' && reading.arms && <div className="tracker-arm-status" aria-label="Curl counting stages">{(['left', 'right'] as const).map(side => <div key={side}><strong>{side === 'left' ? 'Left' : 'Right'} arm · {reading.arms?.[side].angle === null ? 'not visible' : `${reading.arms?.[side].angle}°`}</strong><span>{reading.arms?.[side].instruction}</span></div>)}</div>}
    {exercise === 'Bicep curl' && <p className="tracker-angle-note">Left arm: {reading.leftReps ?? 0} · Right arm: {reading.rightReps ?? 0} · Total = left + right (a simultaneous curl counts as two).</p>}

    <div className="tracker-metrics" aria-label="Movement measurements"><div><strong>{reading.angle === null ? '—' : `${reading.angle}°`}</strong><span>{exercise === 'Squat' ? 'knee angle' : exercise === 'Bicep curl' ? 'elbow angle' : 'wrist rotation'}</span></div><div><strong>{reading.confidence ? `${Math.round(reading.confidence * 100)}%` : '—'}</strong><span>joint visibility</span></div><div><strong>{clock(reading.seconds)}</strong><span>confident tracking</span></div></div>


    </div></details>
    {saved && <div className="tracker-agent"><div className="tracker-agent-heading"><div><Sparkles size={16} /><strong>Exercise feedback agent</strong></div><button className="text-link" disabled={feedbackBusy} onClick={() => void getFeedback()}>{feedbackBusy ? 'Reviewing…' : feedback ? 'Review again' : 'Review this session'} {!feedbackBusy && <Sparkles size={13} />}</button></div>{feedback && <div className="tracker-agent-result"><span className="source-pill">{feedback.source === 'local_fallback' ? 'LEGACY REVIEW' : 'AI REVIEW'}</span><p>{feedback.output.summary}</p>{feedback.output.observations?.length ? <ul>{feedback.output.observations.map((text, i) => <li key={i}>{text}</li>)}</ul> : null}{feedback.output.suggestions?.length ? <ul>{feedback.output.suggestions.map((text, i) => <li key={i}>{text}</li>)}</ul> : null}<small>{feedback.output.confidence_note}</small></div>}{feedbackError && <p className="inline-error" role="alert">{feedbackError}</p>}</div>}
    <p className="tracker-disclaimer">Repetitions are estimates from visible joints. Camera position affects accuracy. Saving shares session measurements and up to eight numerical landmark snapshots with the backend and feedback agent.</p>
  </section>
}
