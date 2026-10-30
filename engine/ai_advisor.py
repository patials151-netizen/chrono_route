"""
ChronoRoute - Ollama Tactical CAD AI Copilot
Integrates local Ollama LLM (Gemma 4:e4b) to deliver:
1. Intelligent CAD Mission Briefings with Clinical & Kinematic Reasoning
2. Mid-Mission Collision Dynamic Reroute Advisories
3. Real-Time Interactive Tactical Dispatch Q&A Copilot
"""

import json
import logging
import threading
import time
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional

logger = logging.getLogger("ChronoRoute.AI")

DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
TARGET_MODEL = "gemma4:e4b"


class OllamaCADAdvisor:
    """
    Tactical Dispatch AI powered by local Ollama (Gemma 4).
    Provides deep incident comprehension, clinical impact summaries,
    and adaptive rerouting explanations.
    """

    def __init__(self, host: str = DEFAULT_OLLAMA_URL, preferred_model: str = TARGET_MODEL):
        self.host = host.rstrip("/")
        self.preferred_model = preferred_model
        self.active_model = preferred_model
        self.is_connected = False
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        
        # Check connection initially
        self.refresh_status()

    def refresh_status(self) -> Dict[str, Any]:
        """Probes the Ollama daemon and detects models."""
        try:
            req = urllib.request.Request(f"{self.host}/api/tags", headers={"User-Agent": "ChronoRoute-CAD/1.0"})
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name", "") for m in data.get("models", [])]
                
                # Check for target model or variant
                if self.preferred_model in models:
                    self.active_model = self.preferred_model
                    self.is_connected = True
                elif any("gemma" in m.lower() for m in models):
                    self.active_model = next(m for m in models if "gemma" in m.lower())
                    self.is_connected = True
                elif len(models) > 0:
                    self.active_model = models[0]
                    self.is_connected = True
                else:
                    self.is_connected = False
        except Exception:
            self.is_connected = False

        return {
            "connected": self.is_connected,
            "host": self.host,
            "model": self.active_model,
            "preferred_model": self.preferred_model
        }

    def _call_chat(self, system_prompt: str, user_prompt: str, timeout: int = 25) -> Optional[Dict[str, str]]:
        """Invokes Ollama /api/chat with streaming disabled."""
        if not self.is_connected:
            self.refresh_status()
            if not self.is_connected:
                return None

        url = f"{self.host}/api/chat"
        payload = {
            "model": self.active_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                msg = result.get("message", {})
                content = msg.get("content", "").strip()
                thinking = msg.get("thinking", "").strip()
                if content:
                    return {"content": content, "thinking": thinking}
                elif thinking:
                    # If model put final synthesis in thinking
                    return {"content": thinking[:250], "thinking": thinking}
                return None
        except Exception as e:
            logger.warning(f"Ollama chat call failed: {e}")
            return None

    def generate_mission_briefing(self, scenario: Dict[str, Any], comparison: Dict[str, Any]) -> Dict[str, Any]:
        """
        Produces a crisp tactical CAD incident briefing from Gemma 4.
        Cached by scenario ID for instant UI updates.
        """
        scenario_id = scenario.get("id", "custom")
        cache_key = f"briefing_{scenario_id}_{scenario.get('weather')}_{scenario.get('time_of_day')}"

        with self._lock:
            if cache_key in self._cache:
                entry = self._cache[cache_key]
                return {
                    "source": "ollama-cache",
                    "model": self.active_model,
                    "briefing": entry["content"],
                    "reasoning": entry.get("thinking", "")
                }

        # Mission Context
        title = scenario.get("title", "Emergency Incident")
        veh = scenario.get("vehicle_type", "AMBULANCE")
        weather = scenario.get("weather", "CLEAR")
        tod = scenario.get("time_of_day", "RUSH_EVENING")
        c_dur = comparison.get("chronoroute", {}).get("duration_formatted", "3m 30s")
        s_dur = comparison.get("standard_gps", {}).get("duration_formatted", "6m 15s")
        time_saved = comparison.get("delta", {}).get("time_saved_formatted", "2m 45s")
        surv_c = comparison.get("survival_probability", {}).get("chronoroute_survival_pct", 30)
        surv_s = comparison.get("survival_probability", {}).get("standard_survival_pct", 22)
        surv_gain = comparison.get("survival_probability", {}).get("survival_gain_pct", 8)

        system_prompt = (
            "You are ChronoRoute Tactical CAD AI Copilot. Speak as an authoritative tactical dispatch operations expert. "
            "Write a concise, high-impact 2-sentence tactical briefing for the responding crew: "
            "highlight vehicle routing, preemption status, weather traction or road entrapment impact, and clinical survival gain."
        )

        user_prompt = (
            f"Mission: {title}\n"
            f"Vehicle: {veh} responding under {weather} weather and {tod} congestion.\n"
            f"ChronoRoute EVP ETA: {c_dur} vs Civilian GPS ETA: {s_dur} (Time saved: {time_saved}).\n"
            f"Survival Projection: ChronoRoute {surv_c}% vs Civilian {surv_s}% (+{surv_gain}% gain).\n"
            f"Generate tactical dispatcher transmission."
        )

        result = self._call_chat(system_prompt, user_prompt, timeout=22)

        if not result or not result.get("content"):
            content = (
                f"CAD DISPATCH: Priority {veh} response authorized under {weather.lower()} conditions. "
                f"ChronoRoute EVP preemption wave clears path in {c_dur} saving {time_saved} over civilian GPS, "
                f"securing a +{surv_gain}% boost in patient survival probability."
            )
            thinking = ""
            source = "fallback"
        else:
            content = result["content"]
            thinking = result.get("thinking", "")
            source = "ollama"

        with self._lock:
            self._cache[cache_key] = {"content": content, "thinking": thinking}

        return {
            "source": source,
            "model": self.active_model if source == "ollama" else "domain-engine",
            "briefing": content,
            "reasoning": thinking
        }

    def generate_reroute_advisory(self, u: str, v: str, edge_name: str, detour_info: Dict[str, Any]) -> Dict[str, Any]:
        """Synthesizes an immediate tactical advisory when an obstacle/collision occurs."""
        system_prompt = (
            "You are ChronoRoute Tactical CAD AI Copilot. A mid-route secondary collision has just blocked a corridor. "
            "Provide a crisp 2-sentence tactical advisory: confirm the blocked segment, the dynamic detour corridor, "
            "and signal wave reallocation."
        )

        user_prompt = (
            f"Urgent: Impasse detected at corridor {edge_name} ({u} -> {v}).\n"
            f"Original corridor is severed. Alternate detour ETA: {detour_info.get('duration_formatted', '4m 10s')}.\n"
            f"Signals preempted on detour: {detour_info.get('signals_preempted', 3)} green-wave junctions."
        )

        result = self._call_chat(system_prompt, user_prompt, timeout=20)

        if not result or not result.get("content"):
            content = (
                f"IMPASSE DETECTED: Corridor {edge_name} severed due to multi-vehicle collision. "
                f"ChronoRoute dynamic A* router has transitioned Medic unit to alternate boulevard, "
                f"locking {detour_info.get('signals_preempted', 3)} green-wave junctions with zero intersection dwell."
            )
            source = "fallback"
            thinking = ""
        else:
            content = result["content"]
            thinking = result.get("thinking", "")
            source = "ollama"

        return {
            "source": source,
            "model": self.active_model if source == "ollama" else "domain-engine",
            "advisory": content,
            "reasoning": thinking
        }

    def answer_tactical_query(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Interactive Dispatcher Q&A powered by Gemma 4.
        Answers operational questions using live CAD state.
        """
        system_prompt = (
            "You are ChronoRoute Tactical CAD AI Copilot, running locally via Gemma 4 on the municipal emergency dispatch server. "
            "You advise dispatchers, paramedics, and tactical fire chiefs on route optimization, Emergency Vehicle "
            "Preemption (EVP), American Heart Association (AHA) survival curves, road width entrapment metrics, "
            "and severe weather traction penalties. Answer directly in 2 to 4 authoritative sentences."
        )

        context_str = json.dumps(context or {}, indent=2)
        user_prompt = (
            f"CURRENT CAD STATE:\n{context_str}\n\n"
            f"DISPATCHER QUERY: {query}\n\n"
            f"Provide tactical CAD response:"
        )

        result = self._call_chat(system_prompt, user_prompt, timeout=25)

        if not result or not result.get("content"):
            q_lower = query.lower()
            if "historic" in q_lower or "narrow" in q_lower or "old town" in q_lower:
                content = (
                    "Tactical Analysis: Historic Quarter corridors have narrow curb-to-curb profiles (<8m) with single lanes. "
                    "In peak congestion, civilian vehicles are physically entrapped and cannot yield to emergency sirens. "
                    "ChronoRoute diverts around via Grand Boulevard where wide multi-lane geometry and EVP preemption save over 3 minutes."
                )
            elif "survival" in q_lower or "cardiac" in q_lower or "aha" in q_lower:
                content = (
                    "Clinical Decisional Matrix: AHA Ventricular Fibrillation clinical survival decays at 7-10% per unassisted minute. "
                    "By eliminating red light queue dwell via 350m C-V2X preemption lookahead, ChronoRoute delivers the patient "
                    "within the golden resuscitation window, projecting a +5% to +20% absolute survival gain."
                )
            elif "rain" in q_lower or "weather" in q_lower or "blizzard" in q_lower:
                content = (
                    "Atmospheric Kinematics Advisory: Precipitation increases road friction penalties from 1.22x (rain) to 1.75x (blizzard). "
                    "For heavy units (Ambulance 4-ton / Ladder 18-ton), braking distance increases by up to 60%, making green-wave signal clearance "
                    "vital to prevent intersection skids."
                )
            elif "bridge" in q_lower or "waterfront" in q_lower:
                content = (
                    "Choke-Point Advisory: The River Causeway bridge represents a high-vulnerability bottleneck. Bridge traffic queues flush "
                    "at 1.2 cars/second; ChronoRoute triggers preemption 35 seconds prior to arrival so the bridge deck is completely clear upon unit entry."
                )
            else:
                content = (
                    f"CAD Telemetry: Active mission evaluated with vehicle preemption armed. All traffic signals along the designated corridor "
                    f"are projected to cycle to PREEMPTED_GREEN upon vehicle 350-meter lookahead cone approach."
                )
            source = "fallback"
            thinking = ""
        else:
            content = result["content"]
            thinking = result.get("thinking", "")
            source = "ollama"

        return {
            "source": source,
            "model": self.active_model if source == "ollama" else "domain-engine",
            "answer": content,
            "reasoning": thinking
        }
