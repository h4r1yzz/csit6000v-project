// Port of AdvancedAIProject's camera-independent full-cycle counters.
export class RepCounter {
  bent: number
  extended: number
  count = 0
  phase: 'find_start' | 'ready' | 'return' = 'find_start'
  private candidate = ''
  private since = 0
  private started = 0
  private lastTime: number | null = null
  private lastValid: number | null = null
  smoothed: number | null = null
  constructor(bent: number, extended: number) { this.bent = bent; this.extended = extended }
  reset() { this.phase = 'find_start'; this.candidate = ''; this.smoothed = null; this.lastTime = null; this.lastValid = null }
  update(value: number | null, time: number) {
    if (this.lastTime !== null && time <= this.lastTime) this.reset()
    const dt = this.lastTime === null ? 1 : time - this.lastTime
    if (this.lastValid !== null && time - this.lastValid > .45) this.reset()
    this.lastTime = time
    if (value === null || !Number.isFinite(value)) { this.candidate = ''; return }
    this.lastValid = time
    const alpha = 1 - Math.exp(-dt / .08)
    this.smoothed = this.smoothed === null ? value : this.smoothed + alpha * (value - this.smoothed)
    const zone = this.smoothed >= this.extended ? 'extended' : this.smoothed <= this.bent ? 'bent' : 'middle'
    if (zone !== this.candidate) { this.candidate = zone; this.since = time }
    if (time - this.since < .12) return
    if (this.phase === 'find_start' && zone === 'extended') this.phase = 'ready'
    else if (this.phase === 'ready' && zone === 'bent') { this.phase = 'return'; this.started = time }
    else if (this.phase === 'return' && zone === 'extended') {
      this.phase = 'ready'
      if (time - this.started >= .25) this.count++
    }
  }
}
export class Calibration {
  private samples: number[] = []
  add(value: number | null) { if (value !== null && Number.isFinite(value)) this.samples.push(value) }
  thresholds() {
    if (this.samples.length < 30) throw new Error('Keep both joints visible for at least 30 frames and perform a slow practice cycle.')
    const sorted = [...this.samples].sort((a, b) => a - b)
    const low = sorted[Math.floor(sorted.length * .1)], high = sorted[Math.floor(sorted.length * .9)]
    if (high - low < 60 || high < 120 || low > 110) throw new Error('Show both straight and bent positions through at least 60° of movement.')
    const margin = Math.min(12, (high - low) * .15)
    return { bent: low + margin, extended: high - margin }
  }
}
