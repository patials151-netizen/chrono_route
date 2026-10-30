/**
 * ChronoRoute - Dashboard & Tactical Operations Orchestrator
 * Connects UI widgets, REST endpoints, live telemetry, and simulation events.
 */

document.addEventListener('DOMContentLoaded', async () => {
  console.log('[*] Initializing ChronoRoute Tactical CAD Dashboard...');

  // State
  let networkData = null;
  let activeScenarioId = 'cardiac_arrest_historic';
  let activeComparison = null;
  let bottleneckData = null;
  let aiStatus = null;

  // Initialize Map
  window.chronoMap.init(40.7150, -74.0050, 14);

  // 0. Check Ollama AI Status
  await checkAiStatus();

  // 1. Fetch Network Topology
  try {
    const netRes = await fetch('/api/network');
    const netJson = await netRes.json();
    networkData = netJson;

    // Render road network and facilities
    window.chronoMap.renderNetwork(netJson.geojson);
    window.chronoMap.renderFacilities(netJson.facilities);
    window.chronoMap.updateSignals(netJson.signals, netJson.nodes);
  } catch (err) {
    console.error('Failed to load network:', err);
  }

  // 2. Load Initial Scenario
  await loadScenario(activeScenarioId);

  // 3. Load Bottlenecks & Advisories
  await refreshBottlenecks();

  // Wire Event Listeners
  setupEventListeners();

  // Wire Simulation Tick Callback
  window.simController.onTickCallback = (frame) => {
    // Update live HUD
    const speedEl = document.getElementById('hud-speed');
    if (speedEl) speedEl.innerHTML = `${frame.speed_kmh.toFixed(1)} <small>km/h</small>`;

    const savedEl = document.getElementById('hud-time-saved');
    if (savedEl && activeComparison) {
      const savedSec = activeComparison.comparison.time_saved_seconds;
      const m = Math.floor(savedSec / 60);
      const s = Math.round(savedSec % 60);
      savedEl.textContent = `+${m}m ${s < 10 ? '0' : ''}${s}s`;
    }

    const distEl = document.getElementById('hud-dist');
    if (distEl && activeComparison) {
      const totalDist = activeComparison.chronoroute.total_distance_m;
      const remainingDist = Math.max(0, totalDist - frame.distance_traveled_m);
      distEl.innerHTML = `${(remainingDist / 1000).toFixed(2)} <small>km</small>`;
    }
  };

  // Wire Simulation Finish Callback
  window.simController.onFinishCallback = () => {
    const playBtn = document.getElementById('btn-sim-play');
    const pauseBtn = document.getElementById('btn-sim-pause');
    if (playBtn) {
      playBtn.disabled = false;
      playBtn.textContent = '↺ REPLAY MISSION';
    }
    if (pauseBtn) pauseBtn.disabled = true;
  };

  // ==========================================
  // HELPER FUNCTIONS
  // ==========================================

  async function loadScenario(scenarioId) {
    try {
      const res = await fetch('/api/scenario/load', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario_id: scenarioId })
      });
      const data = await res.json();
      if (data.status !== 'success') return;

      const scen = data.scenario;
      activeComparison = data.comparison;

      // Update UI cards
      document.getElementById('incident-id').textContent = `CAD #${scenarioId.slice(0, 8).toUpperCase()}`;
      document.getElementById('incident-priority').textContent = scen.priority.replace(/_/g, ' ');
      document.getElementById('incident-title').textContent = scen.title;
      document.getElementById('incident-status').textContent = scen.patient_status;
      document.getElementById('incident-origin').textContent = scen.start_node;
      document.getElementById('incident-dest').textContent = scen.target_node;

      // Update Weather & TOD Indicators
      updateHeaderBadges(scen.weather, scen.time_of_day);

      // Render AI Mission Briefing from Ollama Gemma 4
      if (data.ai_briefing) {
        renderAiBriefing(data.ai_briefing);
      }

      // Render Routes on Map
      const chronoCoords = data.comparison.chronoroute.path_coordinates;
      const stdCoords = data.comparison.standard_gps.path_coordinates;
      window.chronoMap.renderRoutes(chronoCoords, stdCoords);

      // Load Trace into Simulation Controller
      window.simController.loadTrace(data.trace_evp, scen.vehicle_type);

      // Update Comparison & Survival Panel
      renderComparisonMetrics(data.comparison);

      // Refresh Multi-depot analysis for target
      await refreshDepotRankings(scen.target_node, scen.emergency_type);

      // Reset transport buttons
      const playBtn = document.getElementById('btn-sim-play');
      const pauseBtn = document.getElementById('btn-sim-pause');
      if (playBtn) {
        playBtn.disabled = false;
        playBtn.textContent = '▶ DEPLOY UNIT';
      }
      if (pauseBtn) pauseBtn.disabled = true;

      window.simController.logTicker(`Emergency Incident Loaded: ${scen.title}. Optimized EVP corridor calculated.`);
    } catch (err) {
      console.error('Error loading scenario:', err);
    }
  }

  function renderComparisonMetrics(comp) {
    const chrono = comp.chronoroute;
    const std = comp.standard_gps;
    const stats = comp.comparison;

    // Verses Columns
    document.getElementById('chrono-eta').textContent = chrono.total_duration_formatted;
    document.getElementById('chrono-delay').innerHTML = `Signal Delay: <strong>${chrono.signal_delay_s.toFixed(1)}s</strong>`;
    document.getElementById('chrono-lights').innerHTML = `Preempted: <strong>${chrono.signals_preempted} Green Waves</strong>`;

    document.getElementById('std-eta').textContent = std.total_duration_formatted;
    document.getElementById('std-delay').innerHTML = `Signal Delay: <strong>${std.signal_delay_s.toFixed(1)}s</strong>`;
    document.getElementById('std-lights').innerHTML = `Stuck at: <strong>${std.signals_encountered} Red Lights</strong>`;

    // Survival Meters
    const survChrono = stats.chronoroute_survival_rate_pct;
    const survStd = stats.standard_survival_rate_pct;
    const survDelta = stats.survival_rate_improvement_pct;

    document.getElementById('bar-chrono-survival').style.width = `${survChrono}%`;
    document.getElementById('label-chrono-survival').textContent = `${survChrono}%`;

    document.getElementById('bar-std-survival').style.width = `${survStd}%`;
    document.getElementById('label-std-survival').textContent = `${survStd}%`;

    document.getElementById('survival-delta-badge').textContent = `+${survDelta}% CHANCE`;

    // Factor Breakdown
    document.getElementById('val-freeflow').textContent = `${chrono.free_flow_duration_s.toFixed(1)}s`;
    const signalSaved = Math.max(0, std.signal_delay_s - chrono.signal_delay_s);
    document.getElementById('val-signal-saved').textContent = `-${signalSaved.toFixed(1)}s SAVED`;
    document.getElementById('val-width-saved').textContent = `-${Math.max(0, std.width_penalty_s - chrono.width_penalty_s).toFixed(1)}s`;
    document.getElementById('val-weather-friction').textContent = `+${chrono.weather_delay_s.toFixed(1)}s`;
    document.getElementById('val-queue-flushed').textContent = `${chrono.signals_preempted * 8} Vehicles Cleared`;

    // HUD banner
    document.getElementById('hud-time-saved').textContent = stats.time_saved_formatted;
  }

  async function refreshDepotRankings(targetNode, emergencyType) {
    try {
      const res = await fetch('/api/dispatch-analysis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_node: targetNode, emergency_type: emergencyType })
      });
      const data = await res.json();
      if (data.status !== 'success') return;

      const depotListEl = document.getElementById('depot-list');
      depotListEl.innerHTML = '';
      document.getElementById('depot-count').textContent = `${data.rankings.length} DEPOTS EVALUATED`;

      data.rankings.forEach((r, idx) => {
        const item = document.createElement('div');
        item.className = `depot-item ${idx === 0 ? 'recommended' : ''}`;
        item.innerHTML = `
          <div class="depot-item-header">
            <span class="depot-name">${idx === 0 ? '★ ' : ''}${r.name}</span>
            <span class="depot-rank-tag">${idx === 0 ? 'FASTEST ETA' : `RANK #${idx + 1}`}</span>
          </div>
          <div class="depot-metrics">
            <span>Dist: ${r.distance_km} km</span>
            <span class="chrono-eta">EVP: ${r.chrono_eta_formatted}</span>
            <span class="saved">Saves: ${r.time_saved_formatted}</span>
          </div>
        `;
        depotListEl.appendChild(item);
      });
    } catch (err) {
      console.error('Failed to load depot rankings:', err);
    }
  }

  async function refreshBottlenecks() {
    try {
      const res = await fetch('/api/bottlenecks');
      const data = await res.json();
      if (data.status !== 'success') return;

      bottleneckData = data.analysis;
      document.getElementById('critical-choke-count').textContent = `${bottleneckData.critical_count} CHOKE POINTS`;

      // Advisory Feed
      const feedEl = document.getElementById('advisory-feed');
      feedEl.innerHTML = '';

      (bottleneckData.advisories || []).forEach(adv => {
        const item = document.createElement('div');
        item.className = `advisory-item ${adv.severity}`;
        item.innerHTML = `
          <div class="advisory-title">⚠️ ${adv.title} (${Math.round(adv.risk_pct)}% Risk)</div>
          <div class="advisory-text">${adv.message}</div>
          <div class="advisory-action">➔ REC: ${adv.recommended_action}</div>
        `;
        feedEl.appendChild(item);
      });

      // Update Heatmap if active
      const chkHeat = document.getElementById('chk-heatmap');
      if (chkHeat && chkHeat.checked) {
        window.chronoMap.toggleBottleneckHeat(true, bottleneckData.corridor_heat_records);
      }
    } catch (err) {
      console.error('Failed to load bottlenecks:', err);
    }
  }

  function updateHeaderBadges(weather, tod) {
    const weatherMap = {
      'CLEAR': { icon: '☀️', label: 'CLEAR SKIES' },
      'RAIN': { icon: '🌧️', label: 'RAIN (+22% SLIP)' },
      'FOG': { icon: '🌫️', label: 'DENSE FOG (+35%)' },
      'BLIZZARD': { icon: '❄️', label: 'BLIZZARD (+75%)' }
    };
    const todMap = {
      'OFF_PEAK': { icon: '🟢', label: 'OFF-PEAK' },
      'RUSH_MORNING': { icon: '🌅', label: 'MORNING SURGE' },
      'RUSH_EVENING': { icon: '🌆', label: 'EVENING GRIDLOCK' },
      'NIGHT': { icon: '🌙', label: 'NIGHT CYCLE' }
    };

    const w = weatherMap[weather] || weatherMap['CLEAR'];
    const t = todMap[tod] || todMap['RUSH_EVENING'];

    document.getElementById('weather-label').textContent = w.label;
    document.getElementById('current-weather-badge').querySelector('.icon').textContent = w.icon;

    document.getElementById('tod-label').textContent = t.label;
    document.getElementById('current-tod-badge').querySelector('.icon').textContent = t.icon;

    // Sync button active states
    document.querySelectorAll('.weather-btn-group .env-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.weather === weather);
    });
    document.querySelectorAll('.tod-btn-group .env-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tod === tod);
    });
  }

  function setupEventListeners() {
    // Scenario Select
    document.getElementById('scenario-select').addEventListener('change', (e) => {
      activeScenarioId = e.target.value;
      loadScenario(activeScenarioId);
    });

    // Audio Toggle
    const btnAudio = document.getElementById('btn-audio-toggle');
    btnAudio.addEventListener('click', () => {
      const enabled = window.tacticalAudio.toggle();
      document.getElementById('audio-icon').textContent = enabled ? '🔊' : '🔇';
      btnAudio.querySelector('.btn-text').textContent = enabled ? 'AUDIO ON' : 'MUTED';
    });

    // Transport Controls
    const btnPlay = document.getElementById('btn-sim-play');
    const btnPause = document.getElementById('btn-sim-pause');
    const btnReset = document.getElementById('btn-sim-reset');

    btnPlay.addEventListener('click', () => {
      window.simController.play();
      btnPlay.disabled = true;
      btnPause.disabled = false;
    });

    btnPause.addEventListener('click', () => {
      window.simController.pause();
      btnPlay.disabled = false;
      btnPause.disabled = true;
    });

    btnReset.addEventListener('click', () => {
      window.simController.reset();
      btnPlay.disabled = false;
      btnPlay.textContent = '▶ DEPLOY UNIT';
      btnPause.disabled = true;
    });

    // Speed Multipliers
    document.querySelectorAll('.speed-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.speed-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const speed = parseFloat(btn.dataset.speed);
        window.simController.setSpeed(speed);
      });
    });

    // Dynamic Collision Injection
    document.getElementById('btn-inject-obstacle').addEventListener('click', async () => {
      window.tacticalAudio.playHazardAlarm();
      window.simController.logTicker(`🚨 [HAZARD REPORTED] Sudden multi-car pileup reported ahead on arterial! Triggering dynamic ChronoRoute detour calculation...`);

      try {
        const res = await fetch('/api/simulation/reroute', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ u: 'N_2_2', v: 'N_3_2' })
        });
        const data = await res.json();
        if (data.status === 'success') {
          // Re-load updated scenario comparison to redraw paths
          await loadScenario(activeScenarioId);

          if (data.ai_advisory) {
            const adv = data.ai_advisory.advisory;
            window.simController.logTicker(`⚡ [AI DETOUR ENGAGED] ${adv}`);
            appendCopilotMessage('ai', adv, data.ai_advisory.reasoning, 'ALERT: DYNAMIC COLLISION DETOUR');
          } else {
            window.simController.logTicker(`⚡ [DETOUR ENGAGED] ChronoRoute instantly diverted unit to alternate 4-lane boulevard. Green wave re-synchronized.`);
          }
        }
      } catch (e) {
        console.error('Reroute failed:', e);
      }
    });

    // Weather Buttons
    document.querySelectorAll('.weather-btn-group .env-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const weather = btn.dataset.weather;
        await fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ weather })
        });
        await loadScenario(activeScenarioId);
        await refreshBottlenecks();
      });
    });

    // TOD Buttons
    document.querySelectorAll('.tod-btn-group .env-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const tod = btn.dataset.tod;
        await fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ time_of_day: tod })
        });
        await loadScenario(activeScenarioId);
        await refreshBottlenecks();
      });
    });

    // Layer Toggles
    document.getElementById('chk-evp-route').addEventListener('change', (e) => {
      window.chronoMap.toggleEvpPath(e.target.checked);
    });

    document.getElementById('chk-std-route').addEventListener('change', (e) => {
      window.chronoMap.toggleStdPath(e.target.checked);
    });

    document.getElementById('chk-signals').addEventListener('change', (e) => {
      window.chronoMap.toggleSignals(e.target.checked);
    });

    document.getElementById('chk-heatmap').addEventListener('change', (e) => {
      if (bottleneckData) {
        window.chronoMap.toggleBottleneckHeat(e.target.checked, bottleneckData.corridor_heat_records);
      }
    });

    // Wire AI Copilot UI
    setupAiCopilot();
  }

  // ==========================================
  // OLLAMA GEMMA 4 AI COPILOT FUNCTIONS
  // ==========================================

  async function checkAiStatus() {
    try {
      const res = await fetch('/api/ai/status');
      const data = await res.json();
      if (data.status === 'success') {
        aiStatus = data.ai;
        const modelLabel = document.getElementById('ai-model-label');
        const copilotModel = document.getElementById('copilot-model-name');
        if (modelLabel) {
          modelLabel.textContent = aiStatus.connected 
            ? `OLLAMA: ${aiStatus.model.toUpperCase()}`
            : 'OLLAMA: OFFLINE (FALLBACK)';
        }
        if (copilotModel) {
          copilotModel.textContent = aiStatus.model;
        }
      }
    } catch (e) {
      console.warn('Ollama status check failed, using fallback mode:', e);
    }
  }

  function renderAiBriefing(briefingData) {
    const textEl = document.getElementById('ai-mission-briefing');
    const sourceEl = document.getElementById('ai-source-tag');
    const btnReasoning = document.getElementById('btn-view-reasoning');
    const reasoningDrawer = document.getElementById('ai-reasoning-drawer');

    if (textEl) {
      textEl.textContent = briefingData.briefing;
    }

    if (sourceEl) {
      const isOllama = briefingData.source.startsWith('ollama');
      sourceEl.textContent = isOllama
        ? `Engine: Ollama (${briefingData.model})`
        : `Engine: ChronoRoute CAD Domain`;
    }

    if (btnReasoning && reasoningDrawer) {
      if (briefingData.reasoning && briefingData.reasoning.trim().length > 0) {
        btnReasoning.style.display = 'inline-block';
        reasoningDrawer.textContent = briefingData.reasoning;
        btnReasoning.onclick = () => {
          const isShown = reasoningDrawer.style.display === 'block';
          reasoningDrawer.style.display = isShown ? 'none' : 'block';
          btnReasoning.textContent = isShown ? 'Reasoning ▾' : 'Hide Reasoning ▴';
        };
      } else {
        btnReasoning.style.display = 'none';
        reasoningDrawer.style.display = 'none';
      }
    }
  }

  function setupAiCopilot() {
    const modal = document.getElementById('ai-copilot-drawer');
    const btnOpen = document.getElementById('btn-toggle-ai-copilot');
    const btnClose = document.getElementById('btn-close-copilot');
    const form = document.getElementById('copilot-form');
    const input = document.getElementById('copilot-input');

    if (!modal) return;

    if (btnOpen) {
      btnOpen.addEventListener('click', () => {
        modal.classList.remove('hidden');
        if (input) input.focus();
      });
    }

    if (btnClose) {
      btnClose.addEventListener('click', () => {
        modal.classList.add('hidden');
      });
    }

    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        modal.classList.add('hidden');
      }
    });

    // Prompt chips
    document.querySelectorAll('.copilot-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const query = chip.dataset.query;
        if (input) input.value = query;
        sendCopilotQuery(query);
      });
    });

    // Chat submit
    if (form) {
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        const query = input.value.trim();
        if (!query) return;
        sendCopilotQuery(query);
        input.value = '';
      });
    }
  }

  async function sendCopilotQuery(query) {
    appendCopilotMessage('user', query);

    // Add placeholder for AI response
    const placeholderId = `ai-msg-${Date.now()}`;
    const log = document.getElementById('copilot-chat-log');
    const placeholder = document.createElement('div');
    placeholder.className = 'chat-msg ai-msg';
    placeholder.id = placeholderId;
    placeholder.innerHTML = `
      <div class="msg-sender">CHRONOROUTE CAD AI (${aiStatus?.model || 'GEMMA 4'}):</div>
      <div class="msg-body"><em>⚡ Synthesizing tactical assessment...</em></div>
    `;
    log.appendChild(placeholder);
    log.scrollTop = log.scrollHeight;

    try {
      const res = await fetch('/api/ai/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: query,
          context: {
            scenario_id: activeScenarioId,
            comparison: activeComparison?.comparison
          }
        })
      });

      const data = await res.json();
      const el = document.getElementById(placeholderId);
      if (el && data.status === 'success') {
        const ans = data.result.answer;
        const reasoning = data.result.reasoning;
        el.querySelector('.msg-body').textContent = ans;

        if (reasoning && reasoning.trim().length > 0) {
          const rDiv = document.createElement('div');
          rDiv.className = 'msg-thinking';
          rDiv.textContent = `[Reasoning Process]:\n${reasoning.slice(0, 300)}...`;
          el.appendChild(rDiv);
        }
      }
    } catch (err) {
      const el = document.getElementById(placeholderId);
      if (el) {
        el.querySelector('.msg-body').textContent = 'Tactical communication timeout. Please try again.';
      }
    }

    log.scrollTop = log.scrollHeight;
  }

  function appendCopilotMessage(sender, text, reasoning = null, tag = null) {
    const log = document.getElementById('copilot-chat-log');
    if (!log) return;

    const msg = document.createElement('div');
    msg.className = `chat-msg ${sender === 'user' ? 'user-msg' : 'ai-msg'}`;
    const senderTitle = sender === 'user' ? 'TACTICAL DISPATCHER:' : (tag || `CHRONOROUTE CAD AI (${aiStatus?.model || 'GEMMA 4'}):`);

    let html = `
      <div class="msg-sender">${senderTitle}</div>
      <div class="msg-body">${text}</div>
    `;

    if (reasoning && reasoning.trim().length > 0) {
      html += `<div class="msg-thinking">[Reasoning]:\n${reasoning.slice(0, 300)}...</div>`;
    }

    msg.innerHTML = html;
    log.appendChild(msg);
    log.scrollTop = log.scrollHeight;
  }
});
