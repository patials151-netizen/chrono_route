"""
ChronoRoute - Bottleneck Predictor & Dispatch Advisory System
Analyzes network geometry, historic traffic variance, weather conditions,
and road width constraints to forecast emergency vehicle entrapment zones
and issue proactive dispatch advisories.
"""

from typing import Dict, List, Tuple, Any
from .graph_model import UrbanNetwork


class BottleneckPredictor:
    """
    Forecasting model for identifying high-risk emergency entrapment zones.
    Produces risk heatmaps and actionable dispatcher recommendations.
    """

    def __init__(self, network: UrbanNetwork):
        self.network = network

    def analyze_network_bottlenecks(self) -> Dict[str, Any]:
        """
        Calculates composite risk score (0 to 100%) for all road segments in the network.
        Considers:
        1. Historic baseline risk index (empirical accident & gridlock data)
        2. Dynamic congestion load (time of day / rush hour)
        3. Physical road width (narrow single-lane streets have no shoulder to yield)
        4. Weather friction factor (snow/rain increases braking distance & queue blockages)
        """
        weather = self.network.weather_condition
        weather_multiplier = {
            "CLEAR": 1.0,
            "RAIN": 1.25,
            "FOG": 1.35,
            "BLIZZARD": 1.70
        }.get(weather, 1.0)

        high_risk_corridors = []
        medium_risk_corridors = []
        all_edges_risk = []

        for (u, v), edge in self.network.edges_data.items():
            base_risk = edge["historic_risk_index"]
            congestion = edge["current_congestion"]
            width_m = edge["width_m"]
            lanes = edge["lanes"]
            is_blocked = edge.get("blocked", False)

            if is_blocked:
                composite_risk = 100.0
            else:
                # Width penalty factor (narrow roads scale risk exponentially)
                width_penalty = max(0.0, (14.0 - width_m) / 14.0) * 0.35

                # Congestion factor
                congestion_penalty = (congestion ** 1.3) * 0.35

                # Historic risk baseline
                historic_component = base_risk * 0.30

                raw_score = (historic_component + congestion_penalty + width_penalty) * weather_multiplier
                composite_risk = min(99.0, max(5.0, raw_score * 100.0))

            u_node = self.network.nodes_data[u]
            v_node = self.network.nodes_data[v]

            risk_record = {
                "edge_id": f"{u}->{v}",
                "u": u,
                "v": v,
                "name": edge["name"],
                "road_class": edge["road_class"],
                "width_m": edge["width_m"],
                "lanes": edge["lanes"],
                "risk_score_pct": round(composite_risk, 1),
                "congestion_pct": round(congestion * 100, 1),
                "is_blocked": is_blocked,
                "risk_tier": "CRITICAL" if composite_risk >= 55.0 else ("ELEVATED" if composite_risk >= 35.0 else "LOW"),
                "coordinates": [
                    [u_node["lng"], u_node["lat"]],
                    [v_node["lng"], v_node["lat"]]
                ]
            }

            all_edges_risk.append(risk_record)
            if composite_risk >= 55.0:
                high_risk_corridors.append(risk_record)
            elif composite_risk >= 35.0:
                medium_risk_corridors.append(risk_record)

        # Sort highest risk first
        high_risk_corridors.sort(key=lambda x: x["risk_score_pct"], reverse=True)
        medium_risk_corridors.sort(key=lambda x: x["risk_score_pct"], reverse=True)

        # Generate intelligent Dispatcher Advisories using highest risk corridors
        advisory_pool = high_risk_corridors if high_risk_corridors else medium_risk_corridors
        advisories = self._generate_dispatcher_advisories(advisory_pool)

        return {
            "weather": weather,
            "time_of_day": self.network.time_of_day,
            "total_corridors": len(all_edges_risk),
            "critical_count": len(high_risk_corridors),
            "elevated_count": len(medium_risk_corridors),
            "critical_corridors": high_risk_corridors[:6],  # Top 6 critical choke points
            "advisories": advisories,
            "corridor_heat_records": all_edges_risk
        }

    def _generate_dispatcher_advisories(self, high_risk: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Synthesizes human-readable tactical alerts for dispatch operators."""
        advisories = []

        for corridor in high_risk[:4]:
            name = corridor["name"]
            score = corridor["risk_score_pct"]
            u = corridor["u"]
            v = corridor["v"]
            u_dist = self.network.nodes_data[u]["district"]

            if corridor["is_blocked"]:
                advisories.append({
                    "severity": "CRITICAL_HAZARD",
                    "corridor": name,
                    "risk_pct": 100.0,
                    "title": f"ROADWAY IMPASSE: {name}",
                    "message": f"Active emergency/obstacle detected on {name}. ChronoRoute router has dynamically severed edge from dispatch graph. All ambulances automatically rerouted to secondary boulevards.",
                    "recommended_action": "Enforce alternate perimeter routing via Central Boulevard."
                })
            elif corridor["road_class"] == "HISTORIC_NARROW":
                advisories.append({
                    "severity": "HIGH_ENTRAPMENT_RISK",
                    "corridor": name,
                    "risk_pct": score,
                    "title": f"Severe Entrapment Threat: {u_dist}",
                    "message": f"Historic narrow profile ({corridor['width_m']}m) combined with current congestion creates a {score}% vehicle entrapment probability. Private cars cannot pull to curb.",
                    "recommended_action": "Avoid dispatching heavy Ladder trucks here; route Medic units via wide Arterials with Preemption active."
                })
            elif corridor["road_class"] == "RIVER_CROSSING":
                advisories.append({
                    "severity": "CHOKE_POINT_ALERT",
                    "corridor": name,
                    "risk_pct": score,
                    "title": f"River Choke Point Bottleneck: {name}",
                    "message": f"Single bottleneck causeway exhibiting {score}% congestion risk. Bridge queue dissipation requires minimum 35s preemption advance warning.",
                    "recommended_action": "Dispatch secondary backup unit from Eastside Waterfront Depot if destination is east of the river."
                })
            else:
                advisories.append({
                    "severity": "CONGESTION_GRIDLOCK",
                    "corridor": name,
                    "risk_pct": score,
                    "title": f"Peak Surge Warning: {name}",
                    "message": f"Elevated gridlock risk ({score}%) during current time cycle. Green wave synchronization required.",
                    "recommended_action": "Engage continuous EVP corridor hold on approaching junctions."
                })

        return advisories
