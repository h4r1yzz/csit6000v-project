import { cpSync, mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

// Keep the WASM runtime identical to the JS package resolved by npm ci.
const source = new URL('../node_modules/@mediapipe/tasks-vision/wasm/', import.meta.url)
const target = new URL('../public/mediapipe/wasm/', import.meta.url)
mkdirSync(target, { recursive: true })
cpSync(fileURLToPath(source), fileURLToPath(target), { recursive: true })
console.log('Prepared local MediaPipe runtime assets.')
