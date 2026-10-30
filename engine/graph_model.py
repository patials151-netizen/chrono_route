"""
ChronoRoute - City Graph Model & Network Topology
Generates and manages an advanced emergency response urban network with
intersections, multi-phase traffic signals, road geometry (lanes, widths),
traffic queues, and historic bottleneck variance.
"""

import math
import random
from typing import Dict, List, Tuple, Any, Optional

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False


class TrafficSignal:
    """
    Represents an intelligent traffic signal at an intersection with
    Emergency Vehicle Preemption (EVP) capabilities.
    """
    STATE_RED = "RED"
    STATE_YELLOW = "YELLOW"
    STATE_GREEN = "GREEN"
    STATE_PREEMPTED = "PREEMPTED_GREEN"
    STATE_RECOVERY = "RECOVERY"

    def __init__(self, node_id: str, cycle_length: float = 60.0):
        self.node_id = node_id
        self.cycle_length = cycle_length
        self.current_phase_time = random.uniform(0, cycle_length)
        self.state = self.STATE_GREEN if self.current_phase_time < 25.0 else self.STATE_RED
        self.preempted = False
        self.preempt_lock_expiry = 0.0
        self.queue_count = random.randint(3, 14)  # Queued vehicles on major approach
        self.original_queue = self.queue_count
        self.time_saved_by_preemption = 0.0

    def update_tick(self, dt: float, sim_time: float):
        """Simulate signal cycle progress or maintain preemption."""
        if self.preempted:
            if sim_time >= self.preempt_lock_expiry:
                self.preempted = False
                self.state = self.STATE_RECOVERY
                self.current_phase_time = 0.0
            else:
                self.state = self.STATE_PREEMPTED
                # Flush the queue rapidly during EVP green
                flush_rate = 1.2 * dt  # 1.2 cars per second cleared
                self.queue_count = max(0.0, self.queue_count - flush_rate)
                return

        # Normal cycle: 28s Green, 4s Yellow, 28s Red
        self.current_phase_time = (self.current_phase_time + dt) % self.cycle_length
        if self.current_phase_time < 28.0:
            self.state = self.STATE_GREEN
            self.queue_count = max(0.0, self.queue_count - 0.7 * dt)
        elif self.current_phase_time < 32.0:
            self.state = self.STATE_YELLOW
        else:
            self.state = self.STATE_RED
            # Queue grows during red light
            self.queue_count = min(22.0, self.queue_count + 0.3 * dt)

    def trigger_preemption(self, duration_s: float, current_time: float) -> float:
        """
        Force signal to turn green immediately for approaching emergency vehicle.
        Returns estimated delay saved (in seconds).
        """
        was_red = (self.state == self.STATE_RED)
        estimated_red_wait = (self.cycle_length - self.current_phase_time) if was_red else 0.0
        queue_wait = self.queue_count * 2.5  # 2.5s delay per car in queue

        savings = estimated_red_wait + queue_wait
        self.time_saved_by_preemption += savings

        self.preempted = True
        self.preempt_lock_expiry = current_time + duration_s
        self.state = self.STATE_PREEMPTED
        return savings

    def release_preemption(self):
        """Emergency vehicle passed intersection, release back to cycle."""
        self.preempted = False
        self.state = self.STATE_RECOVERY
        self.current_phase_time = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "state": self.state,
            "preempted": self.preempted,
            "queue_count": round(self.queue_count, 1),
            "time_saved_s": round(self.time_saved_by_preemption, 1)
        }


class UrbanNetwork:
    """
    Realistic Metropolitan Emergency Network topology.
    Contains nodes (intersections, stations, hospitals) and directed edges (streets, bridges, boulevards).
    """

    def __init__(self):
        if HAS_NX:
            self.graph = nx.DiGraph()
        else:
            self.graph = None  # Fallback handled in router

        self.nodes_data: Dict[str, Dict[str, Any]] = {}
        self.edges_data: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self.signals: Dict[str, TrafficSignal] = {}
        self.facilities: Dict[str, Dict[str, Any]] = {
            "hospitals": [],
            "fire_stations": [],
            "ems_depots": []
        }
        self.weather_condition = "CLEAR"  # CLEAR, RAIN, FOG, BLIZZARD
        self.time_of_day = "RUSH_EVENING"  # OFF_PEAK, RUSH_MORNING, RUSH_EVENING, NIGHT

        self._build_metropolitan_grid()

    def _build_metropolitan_grid(self):
        """
        Constructs a high-fidelity city network modeled on a metropolitan downtown & waterfront:
        - Grid coordinates mapped to realistic lat/lng near downtown (e.g., lat ~ 40.7128, lng ~ -74.0060)
        - Major Arterial Boulevards (wide 4 lanes, 22m width)
        - Dense Downtown Avenues (medium 3 lanes, 14m width)
        - Historic Quarter (narrow 1 lane, 6.5m width - high entrapment risk)
        - Riverfront Expressway & Bridges (high-speed, but bottleneck prone)
        """
        # Base anchor: Metro City center (40.7150, -74.0050)
        base_lat = 40.7150
        base_lng = -74.0050

        # We construct a 6x6 arterial & avenue grid + diagonal express bypass + 2 river bridge crossings
        rows = 6
        cols = 6
        d_lat = 0.0035  # ~390m spacing
        d_lng = 0.0048  # ~410m spacing

        # Create Nodes
        for r in range(rows):
            for c in range(cols):
                node_id = f"N_{r}_{c}"
                lat = base_lat + (r - (rows - 1) / 2.0) * d_lat
                lng = base_lng + (c - (cols - 1) / 2.0) * d_lng

                district = "Downtown Core"
                if r <= 1:
                    district = "Historic Quarter"
                elif r >= 4:
                    district = "Uptown Medical District"
                elif c >= 4:
                    district = "Waterfront Harbor"

                node_type = "INTERSECTION"
                label = f"{district} Jct {r+1}-{c+1}"

                self.nodes_data[node_id] = {
                    "id": node_id,
                    "lat": lat,
                    "lng": lng,
                    "row": r,
                    "col": c,
                    "district": district,
                    "label": label,
                    "type": node_type,
                    "has_signal": True
                }
                # Initialize traffic signal at every intersection
                self.signals[node_id] = TrafficSignal(node_id, cycle_length=random.uniform(55.0, 75.0))

        # Designate Emergency Facilities
        # Hospital 1: St. Jude Trauma Center in Uptown
        h1_id = "N_5_2"
        self.nodes_data[h1_id]["type"] = "HOSPITAL"
        self.nodes_data[h1_id]["label"] = "Metro General Level-1 Trauma Center"
        self.facilities["hospitals"].append({
            "id": h1_id,
            "name": "Metro General Level-1 Trauma",
            "type": "HOSPITAL",
            "lat": self.nodes_data[h1_id]["lat"],
            "lng": self.nodes_data[h1_id]["lng"],
            "capacity": 24,
            "specialty": "Severe Trauma, Cardiac ICU, Burn Unit"
        })

        # Hospital 2: Harborview Mercy Hospital
        h2_id = "N_2_5"
        self.nodes_data[h2_id]["type"] = "HOSPITAL"
        self.nodes_data[h2_id]["label"] = "Harborview Mercy Emergency Center"
        self.facilities["hospitals"].append({
            "id": h2_id,
            "name": "Harborview Mercy ER",
            "type": "HOSPITAL",
            "lat": self.nodes_data[h2_id]["lat"],
            "lng": self.nodes_data[h2_id]["lng"],
            "capacity": 18,
            "specialty": "Stroke Center & Cardiac Cath Lab"
        })

        # Fire Station 4: Downtown Central Fire & Rescue
        fs1_id = "N_1_1"
        self.nodes_data[fs1_id]["type"] = "FIRE_STATION"
        self.nodes_data[fs1_id]["label"] = "Central Station Engine Co. 4"
        self.facilities["fire_stations"].append({
            "id": fs1_id,
            "name": "Central Station Co. 4",
            "type": "FIRE_STATION",
            "lat": self.nodes_data[fs1_id]["lat"],
            "lng": self.nodes_data[fs1_id]["lng"],
            "vehicles": ["Engine 4", "Ladder 2", "Heavy Rescue 1"]
        })

        # EMS Station 12: Westside Paramedic Depot
        ems1_id = "N_0_3"
        self.nodes_data[ems1_id]["type"] = "EMS_DEPOT"
        self.nodes_data[ems1_id]["label"] = "Westside EMS Depot 12"
        self.facilities["ems_depots"].append({
            "id": ems1_id,
            "name": "EMS Unit 12 (Medic Alpha)",
            "type": "EMS_DEPOT",
            "lat": self.nodes_data[ems1_id]["lat"],
            "lng": self.nodes_data[ems1_id]["lng"],
            "vehicles": ["Medic 12-A (ALS)", "Medic 12-B (BLS)"]
        })

        # EMS Station 8: Eastside Waterfront Medic Depot
        ems2_id = "N_4_4"
        self.nodes_data[ems2_id]["type"] = "EMS_DEPOT"
        self.nodes_data[ems2_id]["label"] = "Waterfront EMS Squad 8"
        self.facilities["ems_depots"].append({
            "id": ems2_id,
            "name": "Waterfront EMS Squad 8 (Medic Bravo)",
            "type": "EMS_DEPOT",
            "lat": self.nodes_data[ems2_id]["lat"],
            "lng": self.nodes_data[ems2_id]["lng"],
            "vehicles": ["Medic 8-A (ALS)", "Rapid Rescue 8"]
        })

        # Create Edges (bidirectional road network with realistic attributes)
        for r in range(rows):
            for c in range(cols):
                u = f"N_{r}_{c}"
                # Connect to East neighbor
                if c < cols - 1:
                    v = f"N_{r}_{c+1}"
                    self._create_road_pair(u, v, r, c, orientation="HORIZONTAL")
                # Connect to North neighbor
                if r < rows - 1:
                    v = f"N_{r+1}_{c}"
                    self._create_road_pair(u, v, r, c, orientation="VERTICAL")

        # Add Express Arterial Cross-Link / Bridge Bypass: (N_1_0 -> N_3_3 -> N_5_5)
        # Simulates a central Metropolitan Parkway flyover
        self._add_express_corridor("N_1_0", "N_2_2", "Grand Metro Parkway (West Link)")
        self._add_express_corridor("N_2_2", "N_3_3", "Grand Metro Parkway (Core Flyover)")
        self._add_express_corridor("N_3_3", "N_4_4", "Grand Metro Parkway (East Overpass)")

        # Populate networkx graph if available
        if HAS_NX:
            for node_id, data in self.nodes_data.items():
                self.graph.add_node(node_id, **data)
            for (u, v), edge in self.edges_data.items():
                self.graph.add_edge(u, v, **edge)

    def _create_road_pair(self, u: str, v: str, r: int, c: int, orientation: str):
        """Creates bidirectional road segments with characteristic geometry and traffic behavior."""
        node_u = self.nodes_data[u]
        node_v = self.nodes_data[v]
        length_m = self._haversine_distance_m(node_u["lat"], node_u["lng"], node_v["lat"], node_v["lng"])

        # Determine road hierarchy
        if r in (2, 3) and orientation == "HORIZONTAL":
            # Central Metropolitan Boulevard
            road_name = f"Central Metro Blvd (Ave {r+1})"
            lanes = 4
            width_m = 22.0
            speed_limit = 60.0  # km/h
            base_congestion = 0.45
            historic_risk = 0.35
            road_class = "ARTERIAL_BOULEVARD"
        elif r <= 1:
            # Historic Quarter: Narrow streets, parked cars, no shoulder to yield!
            road_name = f"Old Quarter Lane {r+1}-{c+1}"
            lanes = 1
            width_m = 6.8  # Very narrow! Ambulances can get stuck!
            speed_limit = 35.0
            base_congestion = 0.65
            historic_risk = 0.78  # High bottleneck risk!
            road_class = "HISTORIC_NARROW"
        elif c in (1, 4) and orientation == "VERTICAL":
            # North-South Avenue Corridor
            road_name = f"Liberty Transit Corridor {c+1}"
            lanes = 3
            width_m = 16.0
            speed_limit = 50.0
            base_congestion = 0.38
            historic_risk = 0.40
            road_class = "TRANSIT_AVENUE"
        elif c >= 4 and orientation == "VERTICAL":
            # Waterfront Causeway / River Bridge zone: High choke point risk
            road_name = f"Harbor River Crossing {c+1}"
            lanes = 2
            width_m = 11.5
            speed_limit = 55.0
            base_congestion = 0.55
            historic_risk = 0.82  # Heavy bottleneck when congested
            road_class = "RIVER_CROSSING"
        else:
            road_name = f"Metro St {r+1}-{c+1}"
            lanes = 2
            width_m = 12.0
            speed_limit = 45.0
            base_congestion = 0.30
            historic_risk = 0.25
            road_class = "LOCAL_STREET"

        # Edge u -> v
        self.edges_data[(u, v)] = {
            "from_node": u,
            "to_node": v,
            "name": road_name,
            "length_m": round(length_m, 1),
            "lanes": lanes,
            "width_m": width_m,
            "speed_limit_kmh": speed_limit,
            "base_congestion": base_congestion,
            "current_congestion": base_congestion,
            "historic_risk_index": historic_risk,
            "road_class": road_class,
            "has_signal": True,
            "target_signal_id": v
        }

        # Edge v -> u (reverse direction)
        self.edges_data[(v, u)] = {
            "from_node": v,
            "to_node": u,
            "name": f"{road_name} (Rev)",
            "length_m": round(length_m, 1),
            "lanes": lanes,
            "width_m": width_m,
            "speed_limit_kmh": speed_limit,
            "base_congestion": base_congestion,
            "current_congestion": base_congestion,
            "historic_risk_index": historic_risk,
            "road_class": road_class,
            "has_signal": True,
            "target_signal_id": u
        }

    def _add_express_corridor(self, u: str, v: str, name: str):
        """Adds a high-speed express arterial bypass link."""
        node_u = self.nodes_data[u]
        node_v = self.nodes_data[v]
        length_m = self._haversine_distance_m(node_u["lat"], node_u["lng"], node_v["lat"], node_v["lng"])

        data_fwd = {
            "from_node": u,
            "to_node": v,
            "name": name,
            "length_m": round(length_m, 1),
            "lanes": 4,
            "width_m": 24.0,
            "speed_limit_kmh": 75.0,
            "base_congestion": 0.25,
            "current_congestion": 0.25,
            "historic_risk_index": 0.20,
            "road_class": "EXPRESSWAY",
            "has_signal": True,
            "target_signal_id": v
        }
        data_rev = dict(data_fwd)
        data_rev["from_node"] = v
        data_rev["to_node"] = u
        data_rev["target_signal_id"] = u

        self.edges_data[(u, v)] = data_fwd
        self.edges_data[(v, u)] = data_rev

    @staticmethod
    def _haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Computes accurate geodesic distance between coordinates in meters."""
        R = 6371000.0  # Earth radius in meters
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0)**2
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return R * c

    def set_weather(self, weather: str):
        """Updates weather condition: CLEAR, RAIN, FOG, BLIZZARD."""
        self.weather_condition = weather.upper()

    def set_time_of_day(self, tod: str):
        """Updates traffic load by time of day."""
        self.time_of_day = tod.upper()
        congestion_multiplier = {
            "OFF_PEAK": 0.7,
            "RUSH_MORNING": 1.45,
            "RUSH_EVENING": 1.60,
            "NIGHT": 0.4
        }.get(self.time_of_day, 1.0)

        for edge in self.edges_data.values():
            base = edge["base_congestion"]
            edge["current_congestion"] = min(0.95, base * congestion_multiplier)

    def set_incident_blockage(self, u: str, v: str, blocked: bool = True):
        """Simulate real-time road closure or multi-car accident."""
        if (u, v) in self.edges_data:
            self.edges_data[(u, v)]["blocked"] = blocked
            self.edges_data[(u, v)]["current_congestion"] = 0.99 if blocked else self.edges_data[(u, v)]["base_congestion"]
        if (v, u) in self.edges_data:
            self.edges_data[(v, u)]["blocked"] = blocked
            self.edges_data[(v, u)]["current_congestion"] = 0.99 if blocked else self.edges_data[(v, u)]["base_congestion"]

    def to_geojson(self) -> Dict[str, Any]:
        """Exports the network as GeoJSON for frontend Leaflet/Mapbox rendering."""
        features = []

        # Edges as LineStrings
        for (u, v), edge in self.edges_data.items():
            u_node = self.nodes_data[u]
            v_node = self.nodes_data[v]
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [u_node["lng"], u_node["lat"]],
                        [v_node["lng"], v_node["lat"]]
                    ]
                },
                "properties": {
                    "edge_id": f"{u}->{v}",
                    "u": u,
                    "v": v,
                    "name": edge["name"],
                    "length_m": edge["length_m"],
                    "lanes": edge["lanes"],
                    "width_m": edge["width_m"],
                    "speed_limit_kmh": edge["speed_limit_kmh"],
                    "congestion": round(edge["current_congestion"], 2),
                    "historic_risk": round(edge["historic_risk_index"], 2),
                    "road_class": edge["road_class"],
                    "blocked": edge.get("blocked", False)
                }
            })

        # Nodes as Points
        for node_id, node in self.nodes_data.items():
            sig = self.signals.get(node_id)
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [node["lng"], node["lat"]]
                },
                "properties": {
                    "node_id": node_id,
                    "label": node["label"],
                    "type": node["type"],
                    "district": node["district"],
                    "has_signal": node["has_signal"],
                    "signal_state": sig.state if sig else None,
                    "preempted": sig.preempted if sig else False,
                    "queue_count": round(sig.queue_count, 1) if sig else 0
                }
            })

        return {
            "type": "FeatureCollection",
            "features": features
        }
