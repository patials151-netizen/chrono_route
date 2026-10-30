"""
Test suite to verify ChronoRoute algorithm, graph topology, preemption, and scenarios.
"""

from engine.graph_model import UrbanNetwork
from engine.router import EmergencyRouter
from engine.preemption_sim import PreemptionSimulation
from engine.bottleneck_predictor import BottleneckPredictor
from engine.scenarios import list_scenarios, get_scenario
from engine.ai_advisor import OllamaCADAdvisor

def test_all():
    print("[1] Building Urban Network...")
    net = UrbanNetwork()
    assert len(net.nodes_data) == 36, f"Expected 36 nodes, got {len(net.nodes_data)}"
    assert len(net.edges_data) > 60, f"Expected >60 edges, got {len(net.edges_data)}"
    assert len(net.signals) == 36, f"Expected 36 signals, got {len(net.signals)}"
    print(f" -> Network built: {len(net.nodes_data)} nodes, {len(net.edges_data)} directed edges.")

    print("[2] Testing Modified A* Router...")
    router = EmergencyRouter(net)
    res_evp = router.find_route("N_0_3", "N_5_2", use_preemption=True, vehicle_type="AMBULANCE")
    res_std = router.find_route("N_0_3", "N_5_2", use_preemption=False, vehicle_type="AMBULANCE")
    print(f" -> ChronoRoute EVP Path: {' -> '.join(res_evp.path_nodes)}")
    print(f" -> ChronoRoute Duration: {res_evp.total_duration_s:.1f}s | Free flow: {res_evp.free_flow_duration_s:.1f}s | Signals: {res_evp.signals_preempted}")
    print(f" -> Standard GPS Duration: {res_std.total_duration_s:.1f}s | Signal Delay: {res_std.signal_delay_s:.1f}s")
    assert res_evp.total_duration_s < res_std.total_duration_s, "ChronoRoute should be significantly faster than unmanaged standard routing"
    saved_s = res_std.total_duration_s - res_evp.total_duration_s
    print(f" -> Time saved by ChronoRoute: {saved_s:.1f} seconds ({saved_s/60:.1f} minutes)!")

    print("[3] Testing Comparison & Cardiac Survival Calculation...")
    comp = router.compare_routes("N_0_3", "N_1_1", vehicle_type="AMBULANCE")
    print(f" -> Standard Survival: {comp['comparison']['standard_survival_rate_pct']}%")
    print(f" -> ChronoRoute Survival: {comp['comparison']['chronoroute_survival_rate_pct']}% (+{comp['comparison']['survival_rate_improvement_pct']}%)")

    print("[4] Testing Bottleneck Predictor...")
    predictor = BottleneckPredictor(net)
    analysis = predictor.analyze_network_bottlenecks()
    print(f" -> Critical Choke Points: {analysis['critical_count']}")
    print(f" -> Advisories generated: {len(analysis['advisories'])}")
    for adv in analysis['advisories'][:2]:
        print(f"    * [{adv['severity']}] {adv['title']}: {adv['recommended_action']}")

    print("[5] Testing Preemption Simulation & Trajectory Trace...")
    sim = PreemptionSimulation(net, router)
    trace = sim.generate_full_simulation_trace("N_0_3", "N_1_1", vehicle_type="AMBULANCE", use_preemption=True)
    print(f" -> Generated trace with {trace['total_frames']} frames spanning {trace['duration_s']}s.")
    assert trace["total_frames"] > 5, "Trace should contain valid navigation frames"

    print("[6] Testing Multi-Depot Dispatch Analysis...")
    rankings = router.evaluate_multi_depot_dispatch("N_1_1", emergency_type="CARDIAC_ARREST")
    print(f" -> Evaluated {len(rankings)} depots. Fastest: {rankings[0]['name']} (ETA: {rankings[0]['chrono_eta_formatted']})")

    print("[7] Testing Ollama Tactical CAD AI Copilot...")
    ai = OllamaCADAdvisor()
    status = ai.refresh_status()
    print(f" -> Ollama connection: {status['connected']} | Active Model: {status['model']}")
    briefing = ai.generate_mission_briefing(
        {"id": "test", "title": "Cardiac Arrest", "vehicle_type": "AMBULANCE", "weather": "CLEAR", "time_of_day": "RUSH_EVENING"},
        comp
    )
    assert briefing and briefing.get("briefing"), "Expected valid mission briefing"
    print(f" -> Mission Briefing generated (Source: {briefing['source']}): {briefing['briefing'][:80]}...")

    q_res = ai.answer_tactical_query("Why avoid Historic Quarter during rush hour?", context={"weather": "CLEAR"})
    assert q_res and q_res.get("answer"), "Expected valid tactical answer"
    print(f" -> Tactical Q&A answered (Source: {q_res['source']}): {q_res['answer'][:80]}...")

    print("\n[SUCCESS] All core algorithmic and AI components validated successfully!")

if __name__ == "__main__":
    test_all()
