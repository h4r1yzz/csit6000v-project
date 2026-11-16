import { useEffect, useState } from 'react'
import { Pause, Play, ArrowUpRight } from 'lucide-react'
import type { Move } from './pose/analysis'

const guides: Record<Move, { subtitle: string; steps: string[]; cues: string[] }> = {
  'Bicep curl': { subtitle: 'Upper body · controlled movement', steps: ['Extend', 'Curl', 'Return'], cues: ['Begin with your arm comfortably straight.', 'Bend your elbow while keeping your upper arm steady.', 'Lower your hand and straighten to complete the rep.'] },
  Squat: { subtitle: 'Lower body · bodyweight', steps: ['Stand', 'Lower', 'Rise'], cues: ['Stand tall with your hip, knee and ankle in view.', 'Lower your hips through a comfortable range.', 'Return to standing to finish the repetition.'] },
  'Arm circles': { subtitle: 'Mobility · shoulder movement', steps: ['Reach', 'Circle', 'Complete'], cues: ['Face the camera and extend your arms comfortably.', 'Move your hands in smooth circles around your shoulders.', 'Complete a full circle without reversing direction.'] },
}

export default function ExerciseGuide({ exercise }: { exercise: Move }) {
  const [step, setStep] = useState(0)
  const [playing, setPlaying] = useState(true)
  useEffect(() => { setStep(0) }, [exercise])
  useEffect(() => {
    if (!playing) return
    const timer = window.setInterval(() => setStep(value => (value + 1) % 3), 1200)
    return () => window.clearInterval(timer)
  }, [playing, exercise])
  useEffect(() => { if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) setPlaying(false) }, [])
  const guide = guides[exercise]
  const crouch = exercise === 'Squat' && step === 1
  const shoulderY = crouch ? 155 : 112
  const hipY = crouch ? 236 : 211
  const arms = exercise === 'Bicep curl'
    ? step === 1 ? [`M 171 ${shoulderY} L 149 169 L 157 111`, `M 229 ${shoulderY} L 251 169 L 243 111`] : [`M 171 ${shoulderY} L 149 169 L 139 215`, `M 229 ${shoulderY} L 251 169 L 261 215`]
    : exercise === 'Squat'
      ? crouch ? ['M 171 155 L 137 150 L 110 145', 'M 229 155 L 263 150 L 290 145'] : ['M 171 112 L 152 160 L 150 199', 'M 229 112 L 248 160 L 250 199']
      : step === 0 ? ['M 171 112 L 128 112 L 82 112', 'M 229 112 L 272 112 L 318 112'] : step === 1 ? ['M 171 112 L 144 78 L 120 38', 'M 229 112 L 256 78 L 280 38'] : ['M 171 112 L 130 142 L 96 166', 'M 229 112 L 270 142 L 304 166']
  return <aside className="exercise-guide">
    <div className="studio-panel-title"><span className="panel-number">01</span><h2>Follow the movement</h2><span className="studio-tag">Illustrated guide</span></div>
    <div className="guide-scene">
      <span className="guide-scene-label">YOUR PACE. YOUR PROGRESS.</span>
      <svg viewBox="0 0 400 340" role="img" aria-label={`${exercise}: ${guide.steps[step]}`}>
        <defs><linearGradient id="guide-shirt" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#29b88c"/><stop offset="1" stopColor="#08765a"/></linearGradient></defs>
        <circle cx="200" cy="165" r="133" fill="#ffffff" opacity=".55"/>
        <path d="M40 300H360" stroke="#c5dcd5" strokeWidth="1"/>
        <ellipse cx="200" cy="304" rx="120" ry="17" fill="#b9d6cd"/>
        <rect x="43" y="246" width="29" height="47" rx="6" fill="#edd3b7"/>
        <path d="M58 250V188M58 224Q24 219 34 192Q60 193 58 224M58 213Q87 205 82 183Q56 186 58 213" fill="#86b69f" stroke="#74a98e" strokeWidth="2"/>
        <g strokeLinecap="round" strokeLinejoin="round">
          <path d={crouch ? 'M184 232 L153 258 L168 296 M216 232 L247 258 L232 296' : 'M184 208 L178 251 L172 296 M216 208 L222 251 L228 296'} stroke="#263c37" strokeWidth="22" fill="none"/>
          <path d="M171 297L155 301M229 297L245 301" stroke="#f9faf8" strokeWidth="14"/>
          <path d={`M174 ${shoulderY-7} Q200 ${shoulderY-20} 226 ${shoulderY-7} L229 ${hipY} Q200 ${hipY+13} 171 ${hipY} Z`} fill="url(#guide-shirt)"/>
          {arms.map((d,i) => <path key={i} d={d} stroke="#d5a17f" strokeWidth="15" fill="none"/>)}
          <path d={`M200 ${shoulderY-13}V${shoulderY-25}`} stroke="#d5a17f" strokeWidth="15"/>
          <circle cx="200" cy={shoulderY-44} r="22" fill="#ddb08e"/>
          <path d={`M179 ${shoulderY-46} Q177 ${shoulderY-77} 208 ${shoulderY-66} Q225 ${shoulderY-65} 222 ${shoulderY-44} L214 ${shoulderY-55} Q197 ${shoulderY-49} 187 ${shoulderY-57}Z`} fill="#293b35"/>
          <circle cx="192" cy={shoulderY-44} r="1.5" fill="#293b35"/><circle cx="208" cy={shoulderY-44} r="1.5" fill="#293b35"/>
          <path d={`M195 ${shoulderY-34}Q200 ${shoulderY-30} 205 ${shoulderY-34}`} stroke="#996f54" strokeWidth="2" fill="none"/>
        </g>
        <circle cx="324" cy="64" r="24" fill="#fff"/><path d="M315 65l6 6 12-14" stroke="#16805e" strokeWidth="3" fill="none"/>
      </svg>
      <div className="guide-playbar"><span><i />{guide.steps[step]}</span><button onClick={() => setPlaying(value => !value)} aria-label={playing ? 'Pause exercise guide' : 'Play exercise guide'}>{playing ? <Pause size={15}/> : <Play size={15}/>} {playing ? 'Pause guide' : 'Play guide'}</button></div>
    </div>
    <div className="guide-description"><span className="studio-eyebrow">{guide.subtitle}</span><h3>{exercise}<ArrowUpRight size={20}/></h3><div className="guide-steps">{guide.steps.map((label,i) => <button key={label} className={step === i ? 'selected' : ''} onClick={() => {setStep(i);setPlaying(false)}}><span>{i+1}</span>{label}</button>)}</div><p>{guide.cues[step]}</p><small>Guide playback is independent of your repetition count.</small></div>
  </aside>
}
