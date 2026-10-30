# 🚑 Project ChronoRoute
### *Emergency Vehicle Traffic Preemption & Multi-Factor Route Optimizer*

[![Python](https://img.shields.io/badge/Python-3.15-blue.svg)](https://python.org)
[![NetworkX](https://img.shields.io/badge/NetworkX-3.7-brightgreen.svg)](https://networkx.org/)
[![Leaflet](https://img.shields.io/badge/Leaflet-1.9.4-emerald.svg)](https://leafletjs.com/)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)]()

> **The Hook**: Instead of a generic GPS tracker, **ChronoRoute** is a heavy-duty algorithmic simulation showing how cities save lives during cardiac and fire emergencies through **Emergency Vehicle Preemption (EVP)**, geometric entrapment avoidance, and real-time bottleneck prediction.

---

## ⚡ The Real-World Problem

Every year, thousands of patients in acute ventricular fibrillation (V-Fib cardiac arrest) and third-degree burn victims lose critical minutes trapped behind red lights and bumper-to-bumper traffic queues.
* **The Clinical Golden Hour**: Clinical American Heart Association (AHA) data shows that for every minute of delayed emergency response, survival probability drops by **7% to 10%**.
* **Why Standard GPS Fails**: Civilian GPS engines (Google Maps, Waze, standard A*) only optimize for free-flow distance or average road speeds. They do not account for:
  1. **Intersection Red Light Dwell**: The inability of emergency sirens to phase-shift traffic signals.
  2. **Road Width Entrapment**: In narrow 1-lane historic streets ($< 8\text{ m}$), private civilian cars are hemmed in by parked vehicles and physically cannot yield to sirens.
  3. **Atmospheric Traction Penalties**: Rain, dense fog, and snow dramatically lengthen deceleration distances for 4-ton ambulances and 18-ton fire engines.

---

## 🧠 Architectural Highlights & Core Algorithms

```
                          ┌───────────────────────────┐
                          │   Dynamic Urban Network   │
                          │   (NetworkX Graph Model)  │
                          └─────────────┬─────────────┘
                                        │
        ┌───────────────────────────────┼───────────────────────────────┐
        ▼                               ▼                               ▼
┌──────────────┐               ┌─────────────────┐             ┌─────────────────┐
│  Modified A* │               │  EVP Preemption │             │    Bottleneck   │
│ Multi-Factor │               │  Lookahead Wave │             │    Predictor    │
│    Router    │               │    Simulator    │             │    & Advisory   │
└───────┬──────┘               └────────┬────────┘             └────────┬────────┘
        │                               │                               │
        └───────────────────────────────┼───────────────────────────────┘
                                        ▼
                        ┌───────────────────────────────┐
                        │   Tactical CAD Dashboard UI   │
                        │  (Leaflet + Web Audio API)    │
                        └───────────────────────────────┘
```

### 1. Modified A* Routing Algorithm
ChronoRoute evaluates edge traversal cost $Cost(e)$ using dynamic multi-factor weighting rather than simple static travel time:

$$Cost(e) = T_{\text{free}}(e) \times f_{\text{weather}} \times f_{\text{width}} + \Delta t_{\text{BPR}}(\text{congestion}) + \Delta t_{\text{signal}}(v)$$

Where:
* **Road Width Entrapment Factor ($f_{\text{width}}$)**:
  $$f_{\text{width}} = 1.0 + \max\left(0, \frac{11.0 - \text{width}_m}{4.0}\right)^{2.2}$$
  *(On a 22m arterial boulevard, $f_{\text{width}} = 1.0$; on a 6.8m alley, $f_{\text{width}} = 2.12\times$ delay!)*
* **Weather Friction Coefficient ($f_{\text{weather}}$)**:
  - Clear: $1.00\times$
  - Rain: $1.22\times$
  - Fog: $1.35\times$
  - Blizzard: $1.75\times$
* **BPR Congestion Delay**:
  $$\Delta t_{\text{BPR}} = T_{\text{free}} \cdot 1.6 \cdot \left(\frac{C_e}{1.05 - \min(0.95, C_e)}\right)^{1.4}$$
* **Admissible Euclidean Heuristic**:
  $$h(u, \text{target}) = \frac{\text{Distance}_{\text{Haversine}}(u, \text{target})}{V_{\text{max\_emergency}}}$$
  Guaranteeing mathematical admissibility ($h(n) \le h^*(n)$) and path optimality.

### 2. Traffic Light Preemption Simulation (EVP)
* As the vehicle moves along its path, it projects an automated **350-meter DSRC / C-V2X preemption lookahead cone**.
* Upcoming traffic signals transition through:
  $$\text{RED} \longrightarrow \text{YELLOW} \longrightarrow \mathbf{PREEMPTED\_GREEN} \longrightarrow \text{RECOVERY}$$
* **Dynamic Queue Flushing**: Queued civilian vehicles flush forward at $1.2\text{ cars/second}$ ahead of the emergency vehicle, ensuring that upon arrival, the intersection dwell time is virtually $0\text{ seconds}$.
* Once the vehicle crosses the junction ($d > 25\text{m}$), the signal enters a graceful recovery cycle.

### 3. Predictive Bottleneck Radar
Machine analyzer that computes a continuous **Vulnerability Score ($0-100\%$)** across all municipal corridors:
* Identifies critical choke points (single-lane river bridges, narrow historic corridors, rush-hour surge zones).
* Issues automated **Dispatcher Advisories** recommending alternate depot dispatches or preemptive perimeter routes.

### 4. AHA Sudden Cardiac Arrest & Trauma Survival Curve
Survival probability modeled according to American Heart Association clinical decay curves:

$$S(t) = S_0 \cdot e^{-\lambda \cdot t_{\text{minutes}}}$$

Where $S_0 = 95\%$ and $\lambda = 0.13\text{ min}^{-1}$. ChronoRoute displays live comparative survival metrics in real time!

### 5. Local Ollama Tactical CAD AI Copilot (`gemma4:e4b`)
ChronoRoute integrates your local **Ollama** daemon running **Gemma 4** (`gemma4:e4b`) for 100% offline tactical intelligence:
* **Live Incident Briefings**: Synthesizes mission-critical CAD transmissions combining vehicle kinematics, weather traction penalties, and clinical survival gains.
* **Dynamic Mid-Route Reroute Analysis**: Generates immediate emergency diversion advisories when a collision blocks the primary arterial.
* **Interactive Tactical CAD Copilot**: Dispatchers can inquire about choke points, bridge protocols, and weather impact via an interactive tactical chat bar or 1-click prompt chips.
* **Automatic Fallback**: If Ollama is offline, the app seamlessly defaults to built-in algorithmic domain heuristics without interruption.

---

## 🚀 Preconfigured Crisis Scenarios

1. **Code Red: Sudden Cardiac Arrest (Historic Quarter)**
   - Westside EMS 12 responding to Old Town.
   - Standard GPS gets stuck behind a 1-lane gridlock with 4 red lights.
   - ChronoRoute routes around via wide Grand Boulevard with automated EVP green wave, saving **3+ minutes** and boosting survival chance by **>20%**.
2. **4-Alarm High-Rise Fire (Waterfront Complex)**
   - Heavy 18-ton Ladder Fire Engine deployed from Downtown Station 4 in heavy rain.
   - EVP preemption flushes the River Causeway bridge queue 35 seconds prior to arrival.
3. **Mass Casualty Collision (Dynamic Mid-Route Rerouting)**
   - While the ambulance is in transit, a secondary collision blocks intersection corridor `N_2_2 -> N_3_2`.
   - ChronoRoute detects the impasse, calculates an instant detour in milliseconds, drops old signals, and locks the detour corridor green.
4. **Code Stroke: Neurovascular Emergency in Blizzard**
   - Freezing conditions and extreme braking distances. Evaluates traction penalties to preserve the critical thrombolytic tPA treatment window.

---

## 🛠️ Project Structure

```
chronoroute/
├── engine/
│   ├── graph_model.py          # Network topology, nodes, signals, geometry
│   ├── router.py               # Modified A* multi-factor routing & AHA curves
│   ├── preemption_sim.py       # EVP state machine, queue flusher, kinematics
│   ├── bottleneck_predictor.py # Risk scoring, choke point classification
│   ├── scenarios.py            # High-stakes crisis demonstration presets
│   └── ai_advisor.py           # Ollama Gemma 4 Tactical CAD AI Copilot & Q&A
├── web/
│   ├── index.html              # Tactical CAD Command Center interface
│   ├── css/
│   │   └── style.css           # Glassmorphism, radar HUD, tactical typography
│   ├── js/
│   │   ├── audio.js            # Web Audio API synthesized siren & EVP chimes
│   │   ├── map.js              # Leaflet map, animated vehicle SVG, radar cones
│   │   ├── simulation.js       # Kinematics controller, frame stepper, ticker
│   │   └── dashboard.js        # API bridge, telemetry dials, survival meters
│   └── assets/
│       ├── leaflet.js          # Offline Leaflet 1.9.4
│       └── leaflet.css         # Offline Leaflet CSS
├── server.py                   # Flask REST API & Static Web Server
├── test_engine.py              # Automated verification test suite
├── requirements.txt            # Python dependencies (Flask, NetworkX, Flask-CORS)
├── start_chronoroute.bat       # Windows 1-Click Double-Click Launcher (auto-opens browser)
├── start_chronoroute.ps1       # PowerShell Launcher
└── run_tests.bat               # 1-Click Algorithmic Test Suite Launcher
```

---

## 🖥️ Running ChronoRoute on your PC

### Option 1: 1-Click Quickstart (Recommended)
Simply **double-click [`start_chronoroute.bat`](file:///C:/Users/Sahil/.gemini/antigravity/scratch/chronoroute/start_chronoroute.bat)**!
- It automatically locates your Python installation.
- It checks that dependencies (`Flask`, `NetworkX`, `Flask-CORS`) are ready.
- It launches the local server and **automatically pops open your web browser** to **http://localhost:8080**.
- Press `Ctrl + C` in the console window whenever you want to close the server.

### Option 2: Via PowerShell
Run in terminal:
```powershell
powershell -ExecutionPolicy Bypass -File .\start_chronoroute.ps1
```

### Option 3: Direct Python Command
```powershell
& "C:\Users\Sahil\AppData\Local\Programs\Python\Python315\python.exe" server.py
```
Open **[http://localhost:8080](http://localhost:8080)** in your browser!

### Running Verification Tests
Double-click [`run_tests.bat`](file:///C:/Users/Sahil/.gemini/antigravity/scratch/chronoroute/run_tests.bat) or run:
```powershell
& "C:\Users\Sahil\AppData\Local\Programs\Python\Python315\python.exe" test_engine.py
```
#   c h r o n o _ r o u t e  
 #   c h r o n o _ r o u t e  
 