/**
 * ChronoRoute - Simulation Execution & Vehicle Kinematics Controller
 * Drives frame-by-frame animation, lookahead signal preemption triggers,
 * ticker logs, and dynamic mid-route detour adaptation.
 */

class SimulationController {
  constructor() {
    this.isPlaying = false;
    this.speedMultiplier = 1.0;
    this.frames = [];
    this.currentFrameIdx = 0;
    this.animInterval = null;
    this.activeScenario = null;
    this.activeVehicleType = 'AMBULANCE';
    this.preemptedHistory = new Set();
    this.onTickCallback = null;
    this.onFinishCallback = null;
  }

  loadTrace(traceData, vehicleType = 'AMBULANCE') {
    this.reset();
    this.frames = traceData.frames || [];
    this.activeVehicleType = vehicleType;
    this.currentFrameIdx = 0;
    this.preemptedHistory.clear();

    if (this.frames.length > 0) {
      const f = this.frames[0];
      window.chronoMap.updateVehiclePosition(f.lat, f.lng, f.heading_deg, this.activeVehicleType);
    }
  }

  play() {
    if (this.frames.length === 0) return;
    this.isPlaying = true;
    window.tacticalAudio.startSiren();
    window.tacticalAudio.playDispatchChirp();

    const baseFrameIntervalMs = 250; // 4 Hz
    clearInterval(this.animInterval);

    this.animInterval = setInterval(() => {
      this.stepForward();
    }, baseFrameIntervalMs / this.speedMultiplier);
  }

  pause() {
    this.isPlaying = false;
    clearInterval(this.animInterval);
    window.tacticalAudio.stopSiren();
  }

  reset() {
    this.pause();
    this.currentFrameIdx = 0;
    this.preemptedHistory.clear();
    const pBar = document.getElementById('sim-progress-bar');
    if (pBar) pBar.style.width = '0%';

    if (this.frames.length > 0) {
      const f = this.frames[0];
      window.chronoMap.updateVehiclePosition(f.lat, f.lng, f.heading_deg, this.activeVehicleType);
    }
  }

  setSpeed(speed) {
    this.speedMultiplier = speed;
    if (this.isPlaying) {
      this.play(); // restart interval with new timing
    }
  }

  stepForward() {
    if (this.currentFrameIdx >= this.frames.length - 1) {
      // Reached destination!
      this.pause();
      window.tacticalAudio.playDispatchChirp();
      this.logTicker(`🏁 UNIT ARRIVED AT SCENE. Scene secured. Preemption corridor safely restored to municipal cycle.`);
      if (this.onFinishCallback) this.onFinishCallback();
      return;
    }

    this.currentFrameIdx++;
    const frame = this.frames[this.currentFrameIdx];

    // Update map vehicle marker & radar
    window.chronoMap.updateVehiclePosition(
      frame.lat,
      frame.lng,
      frame.heading_deg,
      this.activeVehicleType,
      350
    );

    // Check for newly preempted signals
    (frame.preempted_signals || []).forEach(sigId => {
      if (!this.preemptedHistory.has(sigId)) {
        this.preemptedHistory.add(sigId);
        window.tacticalAudio.playPreemptionLock();
        this.logTicker(`⚡ [EVP LOCK] Intersection ${sigId} preempted to GREEN. Queue flushing initiated. Lookahead radar confirmed.`);
      }
    });

    // Check for cleared signals
    (frame.cleared_signals || []).forEach(sigId => {
      // Released
    });

    // Update Progress bar
    const progressPct = ((this.currentFrameIdx + 1) / this.frames.length) * 100;
    const pBar = document.getElementById('sim-progress-bar');
    if (pBar) pBar.style.width = `${progressPct}%`;

    // Notify listeners
    if (this.onTickCallback) {
      this.onTickCallback(frame);
    }
  }

  logTicker(message) {
    const ticker = document.getElementById('ticker-content');
    if (ticker) {
      ticker.textContent = message;
    }
  }
}

window.simController = new SimulationController();
