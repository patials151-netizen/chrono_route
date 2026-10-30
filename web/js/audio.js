/**
 * ChronoRoute - Web Audio API Synthesizer
 * Generates realistic procedural audio effects:
 * - Dual-tone emergency siren
 * - DSRC / V2X Preemption Lock chime
 * - CAD Radio chirp
 * - Collision / Obstacle alarm
 */

class TacticalAudio {
  constructor() {
    this.ctx = null;
    this.enabled = true;
    this.sirenOsc1 = null;
    this.sirenOsc2 = null;
    this.sirenGain = null;
    this.isSirenPlaying = false;
  }

  init() {
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) {
        this.ctx = new AudioCtx();
      }
    }
    if (this.ctx && this.ctx.state === 'suspended') {
      this.ctx.resume();
    }
  }

  toggle() {
    this.enabled = !this.enabled;
    if (!this.enabled) {
      this.stopSiren();
    }
    return this.enabled;
  }

  // Preemption Signal Locked Green Chime (High-tech dual beep)
  playPreemptionLock() {
    if (!this.enabled) return;
    this.init();
    if (!this.ctx) return;

    const t = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();

    osc.type = 'sine';
    // Arpeggiated high tone
    osc.frequency.setValueAtTime(880, t); // A5
    osc.frequency.exponentialRampToValueAtTime(1760, t + 0.12); // A6

    gain.gain.setValueAtTime(0.18, t);
    gain.gain.exponentialRampToValueAtTime(0.001, t + 0.28);

    osc.connect(gain);
    gain.connect(this.ctx.destination);

    osc.start(t);
    osc.stop(t + 0.3);
  }

  // CAD Dispatch Beep
  playDispatchChirp() {
    if (!this.enabled) return;
    this.init();
    if (!this.ctx) return;

    const t = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();

    osc.type = 'triangle';
    osc.frequency.setValueAtTime(650, t);
    osc.frequency.setValueAtTime(920, t + 0.08);

    gain.gain.setValueAtTime(0.2, t);
    gain.gain.exponentialRampToValueAtTime(0.001, t + 0.22);

    osc.connect(gain);
    gain.connect(this.ctx.destination);

    osc.start(t);
    osc.stop(t + 0.24);
  }

  // Tactical Collision / Hazard Warning Alarm
  playHazardAlarm() {
    if (!this.enabled) return;
    this.init();
    if (!this.ctx) return;

    const t = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();

    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(320, t);
    osc.frequency.linearRampToValueAtTime(180, t + 0.25);

    gain.gain.setValueAtTime(0.28, t);
    gain.gain.exponentialRampToValueAtTime(0.001, t + 0.35);

    osc.connect(gain);
    gain.connect(this.ctx.destination);

    osc.start(t);
    osc.stop(t + 0.36);
  }

  // Procedural Emergency Siren (Wail)
  startSiren() {
    if (!this.enabled || this.isSirenPlaying) return;
    this.init();
    if (!this.ctx) return;

    try {
      this.sirenGain = this.ctx.createGain();
      this.sirenGain.gain.setValueAtTime(0.08, this.ctx.currentTime);

      this.sirenOsc1 = this.ctx.createOscillator();
      this.sirenOsc1.type = 'sawtooth';
      this.sirenOsc1.frequency.setValueAtTime(650, this.ctx.currentTime);

      // Low frequency oscillator for pitch modulation (wail effect)
      const lfo = this.ctx.createOscillator();
      lfo.frequency.setValueAtTime(0.65, this.ctx.currentTime); // 0.65 Hz sweep

      const lfoGain = this.ctx.createGain();
      lfoGain.gain.setValueAtTime(300, this.ctx.currentTime); // modulate ±300Hz

      lfo.connect(lfoGain);
      lfoGain.connect(this.sirenOsc1.frequency);

      this.sirenOsc1.connect(this.sirenGain);
      this.sirenGain.connect(this.ctx.destination);

      lfo.start();
      this.sirenOsc1.start();
      this.isSirenPlaying = true;
      this.sirenLfo = lfo;
    } catch (e) {
      console.warn('Siren init error', e);
    }
  }

  stopSiren() {
    if (!this.isSirenPlaying) return;
    try {
      if (this.sirenGain && this.ctx) {
        this.sirenGain.gain.exponentialRampToValueAtTime(0.0001, this.ctx.currentTime + 0.3);
      }
      setTimeout(() => {
        if (this.sirenOsc1) {
          this.sirenOsc1.stop();
          this.sirenOsc1.disconnect();
          this.sirenOsc1 = null;
        }
        if (this.sirenLfo) {
          this.sirenLfo.stop();
          this.sirenLfo.disconnect();
          this.sirenLfo = null;
        }
        this.isSirenPlaying = false;
      }, 350);
    } catch (e) {
      this.isSirenPlaying = false;
    }
  }
}

window.tacticalAudio = new TacticalAudio();
