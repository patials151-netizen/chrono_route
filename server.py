"""
ChronoRoute - Control Center Web & REST API Server
Integrates NetworkX routing, EVP signal state machine, bottleneck predictor,
and serves the tactical emergency operations dashboard.
"""

import os
import sys
import threading
import time
import webbrowser
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from engine.graph_model import UrbanNetwork
from engine.router import EmergencyRouter
from engine.preemption_sim import PreemptionSimulation
from engine.bottleneck_predictor import BottleneckPredictor
from engine.scenarios import SCENARIOS, list_scenarios, get_scenario
from engine.ai_advisor import OllamaCADAdvisor

# Setup directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")

app = Flask(__name__, static_folder=WEB_DIR, static_url_path="")
CORS(app)

# Initialize core domain engine & Ollama AI
network = UrbanNetwork()
router = EmergencyRouter(network)
simulation = PreemptionSimulation(network, router)
predictor = BottleneckPredictor(network)
ai_advisor = OllamaCADAdvisor()


@app.route("/")
def index():
    return send_from_directory(WEB_DIR, "index.html")


@app.route("/<path:path>")
def static_proxy(path):
    file_path = os.path.join(WEB_DIR, path)
    if os.path.exists(file_path):
        return send_from_directory(WEB_DIR, path)
    return send_from_directory(WEB_DIR, "index.html")


@app.route("/api/network", methods=["GET"])
def get_network():
    """Returns complete network topology, nodes, edges, signals, and facilities."""
    geojson_data = network.to_geojson()
    return jsonify({
        "status": "success",
        "weather": network.weather_condition,
        "time_of_day": network.time_of_day,
        "facilities": network.facilities,
        "signals": {nid: sig.to_dict() for nid, sig in network.signals.items()},
        "nodes": network.nodes_data,
        "geojson": geojson_data
    })


@app.route("/api/scenarios", methods=["GET"])
def get_scenarios():
    """Returns list of pre-configured crisis scenarios."""
    return jsonify({
        "status": "success",
        "scenarios": list_scenarios()
    })


@app.route("/api/scenario/load", methods=["POST"])
def load_scenario():
    """Loads a specific crisis scenario with associated network parameters."""
    data = request.get_json() or {}
    scenario_id = data.get("scenario_id", "cardiac_arrest_historic")
    scen = get_scenario(scenario_id)

    # Reset any previous blockages
    for edge in network.edges_data.values():
        edge["blocked"] = False
        edge["current_congestion"] = edge["base_congestion"]

    # Apply scenario parameters
    network.set_weather(scen["weather"])
    network.set_time_of_day(scen["time_of_day"])

    # If scenario specifies an incident blockage
    if scen.get("incident_blockage"):
        u, v = scen["incident_blockage"]
        network.set_incident_blockage(u, v, blocked=True)

    # Compute comparison
    start = scen["start_node"]
    target = scen["target_node"]
    comparison = router.compare_routes(start, target, vehicle_type=scen["vehicle_type"])
    trace = simulation.generate_full_simulation_trace(start, target, vehicle_type=scen["vehicle_type"], use_preemption=True)
    std_trace = simulation.generate_full_simulation_trace(start, target, vehicle_type=scen["vehicle_type"], use_preemption=False)

    # Synthesize AI Tactical Dispatch Briefing with Ollama
    ai_briefing = ai_advisor.generate_mission_briefing(scen, comparison)

    return jsonify({
        "status": "success",
        "scenario": scen,
        "comparison": comparison,
        "trace_evp": trace,
        "trace_standard": std_trace,
        "ai_briefing": ai_briefing
    })


@app.route("/api/route", methods=["POST"])
def calculate_route():
    """
    Computes comparative route optimization between ChronoRoute EVP and Standard GPS.
    Payload: { "start_node": "...", "target_node": "...", "vehicle_type": "AMBULANCE" }
    """
    data = request.get_json() or {}
    start_node = data.get("start_node", "N_0_3")
    target_node = data.get("target_node", "N_1_1")
    vehicle_type = data.get("vehicle_type", "AMBULANCE")

    comparison = router.compare_routes(start_node, target_node, vehicle_type=vehicle_type)
    return jsonify({
        "status": "success",
        "data": comparison
    })


@app.route("/api/dispatch-analysis", methods=["POST"])
def dispatch_analysis():
    """
    Evaluates multi-depot emergency response rankings to find the fastest unit.
    Payload: { "target_node": "...", "emergency_type": "CARDIAC_ARREST" }
    """
    data = request.get_json() or {}
    target_node = data.get("target_node", "N_1_1")
    emergency_type = data.get("emergency_type", "CARDIAC_ARREST")

    rankings = router.evaluate_multi_depot_dispatch(target_node, emergency_type=emergency_type)
    return jsonify({
        "status": "success",
        "target_node": target_node,
        "emergency_type": emergency_type,
        "rankings": rankings
    })


@app.route("/api/bottlenecks", methods=["GET"])
def get_bottlenecks():
    """Returns predictive bottleneck risk heat analysis and dispatcher advisories."""
    analysis = predictor.analyze_network_bottlenecks()
    return jsonify({
        "status": "success",
        "analysis": analysis
    })


@app.route("/api/settings", methods=["POST"])
def update_settings():
    """
    Updates weather conditions or time of day.
    Payload: { "weather": "RAIN", "time_of_day": "RUSH_EVENING" }
    """
    data = request.get_json() or {}
    if "weather" in data:
        network.set_weather(data["weather"])
    if "time_of_day" in data:
        network.set_time_of_day(data["time_of_day"])

    return jsonify({
        "status": "success",
        "weather": network.weather_condition,
        "time_of_day": network.time_of_day
    })


@app.route("/api/simulation/start", methods=["POST"])
def start_simulation():
    """Starts an active simulation mission."""
    data = request.get_json() or {}
    start_node = data.get("start_node", "N_0_3")
    target_node = data.get("target_node", "N_1_1")
    vehicle_type = data.get("vehicle_type", "AMBULANCE")
    use_preemption = data.get("use_preemption", True)

    state = simulation.start_mission(start_node, target_node, vehicle_type=vehicle_type, use_preemption=use_preemption)
    return jsonify({
        "status": "success",
        "state": state
    })


@app.route("/api/simulation/step", methods=["POST"])
def step_simulation():
    """Advances active simulation by dt seconds."""
    data = request.get_json() or {}
    dt = float(data.get("dt", 1.0))
    state = simulation.step(dt)
    return jsonify({
        "status": "success",
        "state": state
    })


@app.route("/api/simulation/trace", methods=["POST"])
def get_simulation_trace():
    """Generates complete high-resolution trajectory trace for smooth browser playback."""
    data = request.get_json() or {}
    start_node = data.get("start_node", "N_0_3")
    target_node = data.get("target_node", "N_1_1")
    vehicle_type = data.get("vehicle_type", "AMBULANCE")
    use_preemption = data.get("use_preemption", True)
    tick_hz = float(data.get("tick_hz", 3.0))

    trace = simulation.generate_full_simulation_trace(
        start_node, target_node, vehicle_type=vehicle_type, use_preemption=use_preemption, tick_hz=tick_hz
    )
    return jsonify({
        "status": "success",
        "trace": trace
    })


@app.route("/api/simulation/reroute", methods=["POST"])
def trigger_reroute():
    """Injects an obstacle/blockage and prompts mid-mission re-routing."""
    data = request.get_json() or {}
    u = data.get("u", "N_2_2")
    v = data.get("v", "N_3_2")

    reroute_res = simulation.trigger_dynamic_reroute(u, v)
    edge_info = network.edges_data.get((u, v)) or network.edges_data.get((v, u)) or {}
    edge_name = edge_info.get("name", f"{u} to {v}")
    ai_advisory = ai_advisor.generate_reroute_advisory(u, v, edge_name, reroute_res)

    return jsonify({
        "status": "success",
        "reroute": reroute_res,
        "state": simulation.get_state(),
        "ai_advisory": ai_advisory
    })


@app.route("/api/ai/status", methods=["GET"])
def get_ai_status():
    """Returns Ollama status and active model."""
    status = ai_advisor.refresh_status()
    return jsonify({
        "status": "success",
        "ai": status
    })


@app.route("/api/ai/briefing", methods=["POST"])
def generate_ai_briefing():
    """Generates an AI mission briefing for arbitrary parameters."""
    data = request.get_json() or {}
    scenario = data.get("scenario", {})
    comparison = data.get("comparison", {})
    briefing = ai_advisor.generate_mission_briefing(scenario, comparison)
    return jsonify({
        "status": "success",
        "briefing": briefing
    })


@app.route("/api/ai/chat", methods=["POST"])
def ai_chat():
    """Interactive Tactical CAD Copilot Q&A endpoint powered by Ollama Gemma 4."""
    data = request.get_json() or {}
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"status": "error", "message": "Query parameter is required"}), 400

    context = data.get("context", {
        "weather": network.weather_condition,
        "time_of_day": network.time_of_day
    })
    result = ai_advisor.answer_tactical_query(query, context=context)
    return jsonify({
        "status": "success",
        "query": query,
        "result": result
    })


def _launch_browser(port):
    time.sleep(1.2)
    url = f"http://localhost:{port}"
    print(f"[*] Opening Tactical CAD Dashboard: {url}")
    try:
        webbrowser.open(url)
    except Exception:
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    url = f"http://localhost:{port}"
    print("=" * 68)
    print("  🚑 CHRONOROUTE - EMERGENCY DISPATCH & PREEMPTION CAD")
    print("=" * 68)
    print(f"  URL: {url}")
    print("  Status: Active & Listening")
    print("  To exit: Press Ctrl+C")
    print("=" * 68)

    if "--no-browser" not in sys.argv:
        threading.Thread(target=_launch_browser, args=(port,), daemon=True).start()

    app.run(host="127.0.0.1", port=port, debug=False)
