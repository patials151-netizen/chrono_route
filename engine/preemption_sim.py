"""
ChronoRoute - Real-Time Preemption Simulator
Simulates emergency vehicle motion along computed trajectories, dynamic
radar/DSRC preemption cones, intersection queue flushing, signal transitions,
and dynamic re-routing upon obstacle injection.
"""

import math
from typing import Dict, List, Tuple, Any, Optional
from .graph_model import UrbanNetwork, TrafficSignal
from .router import EmergencyRouter, RouteResult


class VehicleKinematics:
    """Models physical vehicle motion along GPS waypoints."""
    def __init__(self, vehicle_id: str, vehicle_type: str = "AMBULANCE"):
        self.vehicle_id = vehicle_id
        self.vehicle_type = vehicle_type
        self.current_lat = 0.0
        self.current_lng = 0.0
        self.heading_deg = 0.0
        self.speed_kmh = 0.0
        self.target_speed_kmh = 65.0
        self.distance_traveled_m = 0.0
        self.status = "IDLE"  # IDLE, EN_ROUTE, ARRIVED, REROUTING
        self.preemption_radius_m = 350.0  # DSRC / Cellular-V2X preemption range
        self.active_preempted_signals: List[str] = []
        self.total_time_saved_s = 0.0
        self.total_queue_cleared = 0


class PreemptionSimulation:
    """
    Manages live or discrete simulation ticks for emergency vehicle transit:
    - Tracks vehicle position along RouteResult path
    - Triggers Emergency Vehicle Preemption (EVP) at upcoming intersections
    - Flushes waiting traffic queues
    - Releases signals into recovery phase once vehicle passes
    """

    def __init__(self, network: UrbanNetwork, router: EmergencyRouter):
        self.network = network
        self.router = router
        self.vehicle: Optional[VehicleKinematics] = None
        self.current_route: Optional[RouteResult] = None
        self.route_waypoints: List[Dict[str, Any]] = []
        self.current_waypoint_idx = 0
        self.sim_time_s = 0.0
        self.is_active = False
        self.cleared_signals: List[str] = []

    def start_mission(
        self,
        start_node: str,
        target_node: str,
        vehicle_type: str = "AMBULANCE",
        use_preemption: bool = True
    ) -> Dict[str, Any]:
        """Initializes an emergency transit mission."""
        self.vehicle = VehicleKinematics(f"UNIT-{vehicle_type[:3]}-1", vehicle_type=vehicle_type)
        self.current_route = self.router.find_route(start_node, target_node, use_preemption=use_preemption, vehicle_type=vehicle_type)
        self.sim_time_s = 0.0
        self.is_active = True
        self.cleared_signals = []

        # Prepare detailed waypoints along route
        self.route_waypoints = []
        for i, node_id in enumerate(self.current_route.path_nodes):
            node_data = self.network.nodes_data[node_id]
            self.route_waypoints.append({
                "index": i,
                "node_id": node_id,
                "lat": node_data["lat"],
                "lng": node_data["lng"],
                "label": node_data["label"],
                "has_signal": node_data["has_signal"]
            })

        if self.route_waypoints:
            first = self.route_waypoints[0]
            self.vehicle.current_lat = first["lat"]
            self.vehicle.current_lng = first["lng"]
            self.vehicle.status = "EN_ROUTE"
            self.current_waypoint_idx = 0

        # Perform initial lookahead preemption check
        self._evaluate_preemption_lookahead()

        return self.get_state()

    def step(self, dt: float = 1.0) -> Dict[str, Any]:
        """
        Advances simulation by dt seconds.
        Updates vehicle position, signal states, and preemption zones.
        """
        if not self.is_active or not self.vehicle or self.vehicle.status != "EN_ROUTE":
            return self.get_state()

        self.sim_time_s += dt

        # Update all network traffic signals
        for sig in self.network.signals.values():
            sig.update_tick(dt, self.sim_time_s)

        if self.current_waypoint_idx >= len(self.route_waypoints) - 1:
            # Arrived at emergency scene!
            self.vehicle.status = "ARRIVED"
            self.vehicle.speed_kmh = 0.0
            self.is_active = False
            self._release_all_preemptions()
            return self.get_state()

        current_target_wp = self.route_waypoints[self.current_waypoint_idx + 1]
        dist_to_target = self.network._haversine_distance_m(
            self.vehicle.current_lat, self.vehicle.current_lng,
            current_target_wp["lat"], current_target_wp["lng"]
        )

        # Calculate speed based on upcoming road segment
        u_node = self.route_waypoints[self.current_waypoint_idx]["node_id"]
        v_node = current_target_wp["node_id"]
        edge = self.network.edges_data.get((u_node, v_node))

        speed_limit = edge["speed_limit_kmh"] if edge else 50.0
        # If target signal is still red (non-preempted mode), vehicle must slow down
        sig = self.network.signals.get(v_node)
        if sig and sig.state == TrafficSignal.STATE_RED and dist_to_target < 80.0:
            target_speed = 10.0  # Decelerating before red signal
        else:
            # EVP Green wave allows cruising at optimal emergency speed
            target_speed = min(speed_limit * 1.15, 80.0)

        # Smooth acceleration / deceleration
        accel = 8.0 * dt  # km/h per sec
        if self.vehicle.speed_kmh < target_speed:
            self.vehicle.speed_kmh = min(target_speed, self.vehicle.speed_kmh + accel)
        else:
            self.vehicle.speed_kmh = max(target_speed, self.vehicle.speed_kmh - accel)

        speed_mps = (self.vehicle.speed_kmh / 3.6)
        step_distance_m = speed_mps * dt

        if step_distance_m >= dist_to_target:
            # Reached next intersection waypoint
            self.vehicle.current_lat = current_target_wp["lat"]
            self.vehicle.current_lng = current_target_wp["lng"]
            self.vehicle.distance_traveled_m += dist_to_target

            # Vehicle passed this intersection: release its preemption
            reached_node_id = current_target_wp["node_id"]
            if reached_node_id in self.network.signals:
                self.network.signals[reached_node_id].release_preemption()
                if reached_node_id not in self.cleared_signals:
                    self.cleared_signals.append(reached_node_id)
                if reached_node_id in self.vehicle.active_preempted_signals:
                    self.vehicle.active_preempted_signals.remove(reached_node_id)

            self.current_waypoint_idx += 1
            if self.current_waypoint_idx >= len(self.route_waypoints) - 1:
                self.vehicle.status = "ARRIVED"
                self.vehicle.speed_kmh = 0.0
                self.is_active = False
        else:
            # Interpolate coordinates towards target waypoint
            fraction = step_distance_m / max(dist_to_target, 0.001)
            self.vehicle.current_lat += (current_target_wp["lat"] - self.vehicle.current_lat) * fraction
            self.vehicle.current_lng += (current_target_wp["lng"] - self.vehicle.current_lng) * fraction
            self.vehicle.distance_traveled_m += step_distance_m

            # Calculate heading in degrees
            dlat = current_target_wp["lat"] - self.vehicle.current_lat
            dlng = current_target_wp["lng"] - self.vehicle.current_lng
            self.vehicle.heading_deg = (math.degrees(math.atan2(dlng, dlat)) + 360) % 360

        # Evaluate lookahead to trigger upcoming preemption signals
        self._evaluate_preemption_lookahead()

        return self.get_state()

    def _evaluate_preemption_lookahead(self):
        """
        Detects upcoming traffic signals within preemption radius / ETA horizon
        and commands them to enter PREEMPTED_GREEN state with queue flushing.
        """
        if not self.vehicle or self.vehicle.status != "EN_ROUTE":
            return

        # Check future waypoints along route
        for i in range(self.current_waypoint_idx + 1, len(self.route_waypoints)):
            wp = self.route_waypoints[i]
            dist_to_wp = self.network._haversine_distance_m(
                self.vehicle.current_lat, self.vehicle.current_lng,
                wp["lat"], wp["lng"]
            )

            # Preemption horizon: within preemption radius (~350m)
            if dist_to_wp <= self.vehicle.preemption_radius_m:
                node_id = wp["node_id"]
                sig = self.network.signals.get(node_id)
                if sig and not sig.preempted:
                    # Trigger Preemption!
                    # Duration enough to comfortably reach and clear intersection
                    duration = max(20.0, (dist_to_wp / 15.0) + 15.0)
                    saved = sig.trigger_preemption(duration, self.sim_time_s)
                    self.vehicle.total_time_saved_s += saved
                    self.vehicle.total_queue_cleared += int(sig.original_queue)
                    if node_id not in self.vehicle.active_preempted_signals:
                        self.vehicle.active_preempted_signals.append(node_id)
            else:
                # Outside preemption horizon
                break

    def _release_all_preemptions(self):
        """Releases all active preemptions back to city cycle."""
        if self.vehicle:
            for node_id in list(self.vehicle.active_preempted_signals):
                if node_id in self.network.signals:
                    self.network.signals[node_id].release_preemption()
            self.vehicle.active_preempted_signals.clear()

    def trigger_dynamic_reroute(self, blocked_u: str, blocked_v: str) -> Dict[str, Any]:
        """
        Simulates sudden incident/accident blocking the current corridor.
        Recalculates modified A* route from current position, redirects EVP corridor.
        """
        self.network.set_incident_blockage(blocked_u, blocked_v, blocked=True)

        if not self.vehicle or self.vehicle.status != "EN_ROUTE":
            return {"status": "NO_ACTIVE_MISSION"}

        # Current node is the last reached waypoint
        current_node = self.route_waypoints[self.current_waypoint_idx]["node_id"]
        target_node = self.route_waypoints[-1]["node_id"]

        # Release old preempted signals that are no longer part of the mission
        self._release_all_preemptions()

        # Recalculate route
        new_route = self.router.find_route(current_node, target_node, use_preemption=True, vehicle_type=self.vehicle.vehicle_type)
        self.current_route = new_route

        # Re-build waypoints
        self.route_waypoints = []
        for i, node_id in enumerate(new_route.path_nodes):
            nd = self.network.nodes_data[node_id]
            self.route_waypoints.append({
                "index": i,
                "node_id": node_id,
                "lat": nd["lat"],
                "lng": nd["lng"],
                "label": nd["label"],
                "has_signal": nd["has_signal"]
            })
        self.current_waypoint_idx = 0
        self.vehicle.status = "REROUTING"

        # Re-evaluate preemption on new path
        self._evaluate_preemption_lookahead()
        self.vehicle.status = "EN_ROUTE"

        return {
            "status": "REROUTED_SUCCESSFULLY",
            "blocked_corridor": f"{blocked_u}->{blocked_v}",
            "new_path_nodes": new_route.path_nodes,
            "new_eta_formatted": new_route.to_dict()["total_duration_formatted"]
        }

    def generate_full_simulation_trace(
        self,
        start_node: str,
        target_node: str,
        vehicle_type: str = "AMBULANCE",
        use_preemption: bool = True,
        tick_hz: float = 2.0
    ) -> Dict[str, Any]:
        """
        Pre-computes full high-resolution simulation frames for instantaneous playback,
        scrubbing, and side-by-side visualization.
        """
        # Save snapshot of network signal states
        saved_signal_states = {nid: (sig.state, sig.queue_count, sig.current_phase_time) for nid, sig in self.network.signals.items()}

        self.start_mission(start_node, target_node, vehicle_type=vehicle_type, use_preemption=use_preemption)
        frames = []
        dt = 1.0 / tick_hz
        max_steps = 1200  # Safeguard

        steps = 0
        while self.is_active and steps < max_steps:
            state = self.step(dt)
            frames.append({
                "time_s": round(state["sim_time_s"], 2),
                "lat": round(state["vehicle"]["lat"], 6),
                "lng": round(state["vehicle"]["lng"], 6),
                "speed_kmh": round(state["vehicle"]["speed_kmh"], 1),
                "heading_deg": round(state["vehicle"]["heading_deg"], 1),
                "status": state["vehicle"]["status"],
                "distance_traveled_m": round(state["vehicle"]["distance_traveled_m"], 1),
                "preempted_signals": list(state["vehicle"]["active_preempted_signals"]),
                "cleared_signals": list(self.cleared_signals),
                "time_saved_s": round(state["vehicle"]["time_saved_s"], 1)
            })
            steps += 1

        # Restore signal states
        for nid, (state, queue, phase) in saved_signal_states.items():
            sig = self.network.signals[nid]
            sig.state = state
            sig.queue_count = queue
            sig.current_phase_time = phase
            sig.preempted = False

        return {
            "mode": "CHRONOROUTE_EVP" if use_preemption else "STANDARD_GPS",
            "vehicle_type": vehicle_type,
            "total_frames": len(frames),
            "duration_s": frames[-1]["time_s"] if frames else 0.0,
            "frames": frames
        }

    def get_state(self) -> Dict[str, Any]:
        """Returns the current simulation snapshot."""
        signals_state = {nid: sig.to_dict() for nid, sig in self.network.signals.items()}
        vehicle_state = None
        if self.vehicle:
            vehicle_state = {
                "id": self.vehicle.vehicle_id,
                "type": self.vehicle.vehicle_type,
                "lat": self.vehicle.current_lat,
                "lng": self.vehicle.current_lng,
                "speed_kmh": round(self.vehicle.speed_kmh, 1),
                "heading_deg": round(self.vehicle.heading_deg, 1),
                "status": self.vehicle.status,
                "distance_traveled_m": round(self.vehicle.distance_traveled_m, 1),
                "preemption_radius_m": self.vehicle.preemption_radius_m,
                "active_preempted_signals": list(self.vehicle.active_preempted_signals),
                "time_saved_s": round(self.vehicle.total_time_saved_s, 1),
                "queue_cleared_cars": self.vehicle.total_queue_cleared
            }

        return {
            "sim_time_s": round(self.sim_time_s, 1),
            "is_active": self.is_active,
            "vehicle": vehicle_state,
            "signals": signals_state,
            "cleared_signals": list(self.cleared_signals),
            "current_waypoint_idx": self.current_waypoint_idx,
            "total_waypoints": len(self.route_waypoints)
        }
