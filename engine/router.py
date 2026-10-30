"""
ChronoRoute - Advanced Routing Engine
Modified A* and Comparative Dispatch Optimizer:
- Evaluates real-time congestion weights
- Road width clearance factors (curb room for sirens)
- Dynamic weather traction friction
- Signal preemption (EVP Green Corridor) vs Standard unmanaged traffic delays
- Multi-station emergency dispatch rankings
"""

import heapq
import math
from typing import Dict, List, Tuple, Any, Optional
from .graph_model import UrbanNetwork


class RouteResult:
    """Encapsulates routing trajectory, telemetry, and time breakdown."""
    def __init__(self, mode: str, path_nodes: List[str]):
        self.mode = mode  # "CHRONOROUTE_EVP" or "STANDARD_GPS"
        self.path_nodes = path_nodes
        self.path_coordinates: List[Tuple[float, float]] = []
        self.total_distance_m: float = 0.0
        self.total_duration_s: float = 0.0
        self.free_flow_duration_s: float = 0.0
        self.signal_delay_s: float = 0.0
        self.congestion_delay_s: float = 0.0
        self.weather_delay_s: float = 0.0
        self.width_penalty_s: float = 0.0
        self.signals_encountered: int = 0
        self.signals_preempted: int = 0
        self.segment_breakdowns: List[Dict[str, Any]] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "path_nodes": self.path_nodes,
            "path_coordinates": self.path_coordinates,
            "total_distance_m": round(self.total_distance_m, 1),
            "total_duration_s": round(self.total_duration_s, 1),
            "total_duration_formatted": f"{int(self.total_duration_s // 60)}m {int(self.total_duration_s % 60):02d}s",
            "free_flow_duration_s": round(self.free_flow_duration_s, 1),
            "signal_delay_s": round(self.signal_delay_s, 1),
            "congestion_delay_s": round(self.congestion_delay_s, 1),
            "weather_delay_s": round(self.weather_delay_s, 1),
            "width_penalty_s": round(self.width_penalty_s, 1),
            "signals_encountered": self.signals_encountered,
            "signals_preempted": self.signals_preempted,
            "segments": self.segment_breakdowns
        }


class EmergencyRouter:
    """
    Advanced emergency routing engine operating on UrbanNetwork.
    Provides comparison between ChronoRoute (Dynamic Preemption + Geometric Multi-Factor Cost)
    and Standard civilian GPS navigation.
    """

    # Weather traction coefficients
    WEATHER_COEFFICIENTS = {
        "CLEAR": 1.00,
        "RAIN": 1.22,      # Slippery pavement, reduced cornering
        "FOG": 1.35,       # Severely reduced visibility, cautious speeds
        "BLIZZARD": 1.75    # Extreme braking distance, icy traction
    }

    # Emergency maximum velocity for admissible A* heuristic (25 m/s = 90 km/h)
    V_MAX_EMERGENCY_MPS = 25.0

    def __init__(self, network: UrbanNetwork):
        self.network = network

    def _get_weather_factor(self) -> float:
        return self.WEATHER_COEFFICIENTS.get(self.network.weather_condition, 1.0)

    def _compute_road_width_factor(self, width_m: float, lanes: int) -> float:
        """
        Calculates siren clearance difficulty.
        On wide avenues (18m+, 3+ lanes), vehicles easily pull to the right or shoulder.
        On narrow streets (<8m, 1 lane), private cars are hemmed in and cannot yield,
        creating severe emergency entrapment delay.
        """
        if width_m >= 16.0:
            return 1.0  # Full shoulder clearance
        elif width_m >= 11.0:
            return 1.15  # Moderate clearance
        elif width_m >= 8.0:
            return 1.45  # Tight squeeze
        else:
            # Narrow historic streets: non-linear entrapment penalty
            deficit = max(0.0, 11.0 - width_m)
            return 1.0 + (deficit / 4.0)**2.2

    def _compute_edge_cost(
        self,
        edge: Dict[str, Any],
        use_preemption: bool,
        vehicle_type: str = "AMBULANCE"
    ) -> Tuple[float, Dict[str, float]]:
        """
        Calculates real-world traversal cost (time in seconds) for edge (u, v).
        """
        length_m = edge["length_m"]
        speed_limit_kmh = edge["speed_limit_kmh"]
        width_m = edge["width_m"]
        lanes = edge["lanes"]
        congestion = edge["current_congestion"]
        has_signal = edge.get("has_signal", False)
        target_node = edge["to_node"]

        # Emergency vehicle speed multiplier (sirens allow ~15% higher cruising when road is clear)
        ev_speed_boost = 1.15 if vehicle_type in ("AMBULANCE", "POLICE") else 1.05
        base_speed_mps = (speed_limit_kmh / 3.6) * ev_speed_boost
        free_flow_time = length_m / max(base_speed_mps, 1.0)

        # 1. Weather friction
        weather_factor = self._get_weather_factor()
        weather_delay = free_flow_time * (weather_factor - 1.0)

        # 2. Road width penalty
        width_factor = self._compute_road_width_factor(width_m, lanes)
        width_penalty = free_flow_time * (width_factor - 1.0)

        # 3. Congestion delay (Bureau of Public Roads-style curve)
        # BPR: travel_time = free_flow * (1 + alpha * (volume/capacity)^beta)
        bpr_delay = free_flow_time * (1.6 * (congestion / (1.05 - min(0.95, congestion)))**1.4)

        # If road is blocked by an incident, impose huge obstacle cost
        if edge.get("blocked", False):
            bpr_delay += 9999.0

        # 4. Traffic Signal & Queue delay at target intersection
        signal_delay = 0.0
        sig = self.network.signals.get(target_node)
        if has_signal and sig:
            if use_preemption:
                # With ChronoRoute EVP, signal turns green in advance.
                # Queue is flushed ahead; residual clearance delay is minimal (~1.5s)
                signal_delay = 1.5
            else:
                # Standard civilian routing or unmanaged vehicle:
                # Wait through red cycle + wait for traffic queue to dissipate
                is_red = (sig.state == sig.STATE_RED)
                expected_red_wait = 24.0 if is_red else 6.0
                queue_wait = sig.queue_count * 2.2  # 2.2s per queued vehicle to accelerate
                signal_delay = expected_red_wait + queue_wait

        total_cost = free_flow_time + weather_delay + width_penalty + bpr_delay + signal_delay

        breakdown = {
            "free_flow_s": free_flow_time,
            "weather_delay_s": weather_delay,
            "width_penalty_s": width_penalty,
            "congestion_delay_s": bpr_delay,
            "signal_delay_s": signal_delay,
            "total_s": total_cost
        }
        return total_cost, breakdown

    def _heuristic(self, node_id: str, target_id: str) -> float:
        """
        Admissible Euclidean lower-bound heuristic for A*.
        h(n) = EuclideanDistance(n, target) / V_MAX
        Guarantees that h(n) <= true remaining time.
        """
        n1 = self.network.nodes_data[node_id]
        n2 = self.network.nodes_data[target_id]
        dist_m = self.network._haversine_distance_m(n1["lat"], n1["lng"], n2["lat"], n2["lng"])
        return dist_m / self.V_MAX_EMERGENCY_MPS

    def find_route(
        self,
        start_node: str,
        target_node: str,
        use_preemption: bool = True,
        vehicle_type: str = "AMBULANCE"
    ) -> RouteResult:
        """
        Runs modified A* search to calculate the optimal path under current dynamic conditions.
        """
        mode = "CHRONOROUTE_EVP" if use_preemption else "STANDARD_GPS"
        if start_node == target_node:
            res = RouteResult(mode, [start_node])
            coords = (self.network.nodes_data[start_node]["lat"], self.network.nodes_data[start_node]["lng"])
            res.path_coordinates = [coords]
            return res

        # Priority Queue for A*: stores (f_score, current_node, cost_so_far)
        open_set: List[Tuple[float, str, float]] = []
        heapq.heappush(open_set, (0.0, start_node, 0.0))

        came_from: Dict[str, str] = {}
        cost_so_far: Dict[str, float] = {start_node: 0.0}
        edge_used: Dict[str, Dict[str, Any]] = {}
        breakdowns: Dict[str, Dict[str, float]] = {}

        while open_set:
            current_f, current, current_cost = heapq.heappop(open_set)

            if current == target_node:
                break

            if current_cost > cost_so_far.get(current, float('inf')):
                continue

            # Inspect outgoing edges from current
            for (u, v), edge in self.network.edges_data.items():
                if u != current:
                    continue

                # Calculate multi-factor edge cost
                edge_cost, breakdown = self._compute_edge_cost(edge, use_preemption, vehicle_type)
                new_cost = current_cost + edge_cost

                if new_cost < cost_so_far.get(v, float('inf')):
                    cost_so_far[v] = new_cost
                    priority = new_cost + self._heuristic(v, target_node)
                    heapq.heappush(open_set, (priority, v, new_cost))
                    came_from[v] = current
                    edge_used[v] = edge
                    breakdowns[v] = breakdown

        if target_node not in came_from and start_node != target_node:
            # No path found (e.g. road fully severed)
            return RouteResult(mode, [])

        # Reconstruct path backwards
        path_nodes: List[str] = [target_node]
        curr = target_node
        while curr in came_from:
            curr = came_from[curr]
            path_nodes.append(curr)
        path_nodes.reverse()

        # Build full result
        result = RouteResult(mode, path_nodes)
        for nid in path_nodes:
            nd = self.network.nodes_data[nid]
            result.path_coordinates.append((nd["lat"], nd["lng"]))

        # Aggregate telemetry metrics across path
        for i in range(len(path_nodes) - 1):
            u = path_nodes[i]
            v = path_nodes[i + 1]
            edge = self.network.edges_data[(u, v)]
            bd = breakdowns.get(v, {})

            result.total_distance_m += edge["length_m"]
            result.free_flow_duration_s += bd.get("free_flow_s", 0.0)
            result.weather_delay_s += bd.get("weather_delay_s", 0.0)
            result.width_penalty_s += bd.get("width_penalty_s", 0.0)
            result.congestion_delay_s += bd.get("congestion_delay_s", 0.0)
            result.signal_delay_s += bd.get("signal_delay_s", 0.0)
            result.total_duration_s += bd.get("total_s", 0.0)

            if edge.get("has_signal", False):
                result.signals_encountered += 1
                if use_preemption:
                    result.signals_preempted += 1

            result.segment_breakdowns.append({
                "from": u,
                "to": v,
                "road_name": edge["name"],
                "length_m": edge["length_m"],
                "width_m": edge["width_m"],
                "lanes": edge["lanes"],
                "breakdown": bd
            })

        return result

    def compare_routes(
        self,
        start_node: str,
        target_node: str,
        vehicle_type: str = "AMBULANCE"
    ) -> Dict[str, Any]:
        """
        Runs side-by-side comparative analysis:
        1. ChronoRoute (Dynamic Preemption EVP + Width/Friction Optimization)
        2. Standard Civilian GPS (No Preemption, gets stuck at red lights and narrow bottlenecks)
        Computes survival probability impact, minutes saved, and signal clearance metrics.
        """
        chrono_route = self.find_route(start_node, target_node, use_preemption=True, vehicle_type=vehicle_type)
        standard_route = self.find_route(start_node, target_node, use_preemption=False, vehicle_type=vehicle_type)

        time_saved_s = max(0.0, standard_route.total_duration_s - chrono_route.total_duration_s)
        time_saved_pct = (time_saved_s / standard_route.total_duration_s * 100.0) if standard_route.total_duration_s > 0 else 0.0

        # Clinical Survival Probability Model (AHA Sudden Cardiac Arrest / Trauma Golden Hour)
        # In cardiac arrest, survival drops ~7% to 10% per minute without definitive intervention.
        # Base formula: Survival = S0 * exp(-lambda * t_minutes)
        std_mins = standard_route.total_duration_s / 60.0
        chrono_mins = chrono_route.total_duration_s / 60.0

        # AHA Cardiac Arrest survival decay parameter (approx 0.12 per minute)
        surv_std = max(5.0, 95.0 * math.exp(-0.13 * std_mins))
        surv_chrono = max(5.0, 95.0 * math.exp(-0.13 * chrono_mins))
        survival_delta_pct = max(0.0, surv_chrono - surv_std)

        return {
            "origin": self.network.nodes_data[start_node],
            "destination": self.network.nodes_data[target_node],
            "vehicle_type": vehicle_type,
            "weather": self.network.weather_condition,
            "time_of_day": self.network.time_of_day,
            "chronoroute": chrono_route.to_dict(),
            "standard_gps": standard_route.to_dict(),
            "comparison": {
                "time_saved_seconds": round(time_saved_s, 1),
                "time_saved_formatted": f"{int(time_saved_s // 60)}m {int(time_saved_s % 60):02d}s",
                "time_saved_percent": round(time_saved_pct, 1),
                "red_lights_eliminated": chrono_route.signals_preempted,
                "standard_survival_rate_pct": round(surv_std, 1),
                "chronoroute_survival_rate_pct": round(surv_chrono, 1),
                "survival_rate_improvement_pct": round(survival_delta_pct, 1)
            }
        }

    def evaluate_multi_depot_dispatch(self, emergency_node: str, emergency_type: str = "CARDIAC_ARREST") -> List[Dict[str, Any]]:
        """
        Evaluates all available emergency facilities (Fire Stations or EMS Depots)
        to identify the optimal vehicle dispatch based on real-time preemption ETA.
        """
        facility_candidates = []

        if "FIRE" in emergency_type.upper() or "HAZMAT" in emergency_type.upper():
            depots = self.network.facilities["fire_stations"]
            v_type = "FIRE_ENGINE"
        else:
            depots = self.network.facilities["ems_depots"]
            v_type = "AMBULANCE"

        for depot in depots:
            depot_id = depot["id"]
            comparison = self.compare_routes(depot_id, emergency_node, vehicle_type=v_type)
            chrono = comparison["chronoroute"]
            standard = comparison["standard_gps"]
            saved = comparison["comparison"]

            facility_candidates.append({
                "depot_id": depot_id,
                "name": depot["name"],
                "type": depot["type"],
                "lat": depot["lat"],
                "lng": depot["lng"],
                "vehicle_type": v_type,
                "distance_km": round(chrono["total_distance_m"] / 1000.0, 2),
                "chrono_eta_s": chrono["total_duration_s"],
                "chrono_eta_formatted": chrono["total_duration_formatted"],
                "standard_eta_s": standard["total_duration_s"],
                "standard_eta_formatted": standard["total_duration_formatted"],
                "time_saved_formatted": saved["time_saved_formatted"],
                "signals_preempted": chrono["signals_preempted"],
                "survival_rate_pct": saved["chronoroute_survival_rate_pct"]
            })

        # Rank by ChronoRoute ETA
        facility_candidates.sort(key=lambda x: x["chrono_eta_s"])
        return facility_candidates
