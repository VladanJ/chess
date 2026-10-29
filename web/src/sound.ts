// Tiny synthesized sound effects (Web Audio): no audio files to load or license.

let ac: AudioContext | null = null;
let enabled = true;
let lastHit = 0;

export function setSoundEnabled(on: boolean): void {
  enabled = on;
}

/** Call from a user gesture (click/key) so browsers allow audio to start. */
export function unlockAudio(): void {
  if (!enabled) return;
  ac ??= new AudioContext();
  if (ac.state === "suspended") void ac.resume();
}

function tone(freq: number, dur: number, type: OscillatorType, vol: number, slideTo = freq, delay = 0): void {
  if (!enabled || !ac || ac.state !== "running") return;
  const t = ac.currentTime + delay;
  const osc = ac.createOscillator();
  const gain = ac.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, t);
  osc.frequency.exponentialRampToValueAtTime(slideTo, t + dur);
  gain.gain.setValueAtTime(vol, t);
  gain.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  osc.connect(gain).connect(ac.destination);
  osc.start(t);
  osc.stop(t + dur);
}

const notes = (freqs: number[], step: number, type: OscillatorType, vol: number) =>
  freqs.forEach((f, i) => tone(f, step * 1.6, type, vol, f, i * step));

export const sfx = {
  move: () => tone(520, 0.07, "triangle", 0.08, 640),
  /** Called every frame while fighting; throttled to a steady clash rhythm. */
  hit: () => {
    const now = performance.now();
    if (now - lastHit < 280) return;
    lastHit = now;
    tone(180 + Math.random() * 60, 0.05, "square", 0.035, 120);
  },
  death: () => tone(700, 0.28, "sine", 0.16, 110),
  promote: () => notes([523, 659, 784, 1047], 0.07, "triangle", 0.1),
  win: () => notes([523, 659, 784, 1047, 784, 1047], 0.11, "triangle", 0.12),
  lose: () => notes([523, 440, 349, 262], 0.16, "sine", 0.12),
};
