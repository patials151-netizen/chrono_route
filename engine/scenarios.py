"""
ChronoRoute - Preconfigured High-Stakes Emergency Scenarios
Offers dramatic algorithmic comparison demonstrations of real-world crises.
"""

from typing import Dict, List, Any


SCENARIOS: Dict[str, Dict[str, Any]] = {
    "cardiac_arrest_historic": {
        "id": "cardiac_arrest_historic",
        "title": "Code Red: Sudden Cardiac Arrest (Historic Quarter)",
        "priority": "ALPHA_1_CRITICAL",
        "emergency_type": "CARDIAC_ARREST",
        "vehicle_type": "AMBULANCE",
        "start_node": "N_0_3",  # Westside EMS Depot 12
        "target_node": "N_1_1",  # Downtown Historic Center
        "weather": "CLEAR",
        "time_of_day": "RUSH_EVENING",
        "patient_status": "V-Fib Arrest; Bystander CPR in progress. Every 60s delay reduces survival by 10%.",
        "description": "Ambulance must traverse downtown rush hour into the narrow Historic Quarter. Standard GPS routes through trapped 1-lane alleys with red lights. ChronoRoute detours via wide Boulevard with automated EVP green wave.",
        "incident_blockage": None
    },
    "waterfront_highrise_fire": {
        "id": "waterfront_highrise_fire",
        "title": "4-Alarm Structural High-Rise Fire (Waterfront Complex)",
        "priority": "STRUCTURAL_FIRE_4_ALARM",
        "emergency_type": "STRUCTURE_FIRE",
        "vehicle_type": "FIRE_ENGINE",
        "start_node": "N_1_1",  # Central Fire Station Co. 4
        "target_node": "N_4_5",  # Waterfront Commercial Tower
        "weather": "RAIN",
        "time_of_day": "RUSH_EVENING",
        "patient_status": "Occupants trapped on 18th floor; flashover imminent within 6 minutes.",
        "description": "Heavy 18-ton Ladder Truck must cross the congested River Causeway in rain conditions. ChronoRoute preemptively flushes the bridge approach queue 35 seconds prior to arrival.",
        "incident_blockage": None
    },
    "dynamic_freeway_collision": {
        "id": "dynamic_freeway_collision",
        "title": "Mass Casualty Pileup with Dynamic Mid-Route Road Blockage",
        "priority": "TRAUMA_CODE_1",
        "emergency_type": "MULTI_VEHICLE_TRAUMA",
        "vehicle_type": "AMBULANCE",
        "start_node": "N_4_4",  # Waterfront EMS Squad 8
        "target_node": "N_5_2",  # Metro General Trauma Hospital
        "weather": "FOG",
        "time_of_day": "RUSH_MORNING",
        "patient_status": "Critical polytrauma patient needing immediate emergency thoracotomy.",
        "description": "En route, a sudden secondary crash completely blocks the primary intersection corridor (N_3_3 -> N_4_3). ChronoRoute dynamically detects the impasse, computes a detour in milliseconds, and re-programs upcoming green waves.",
        "incident_blockage": ("N_3_3", "N_4_3")
    },
    "blizzard_stroke_evacuation": {
        "id": "blizzard_stroke_evacuation",
        "title": "Code Stroke: Neurovascular Emergency in Blizzard",
        "priority": "STROKE_WINDOW_CRITICAL",
        "emergency_type": "ISCHEMIC_STROKE",
        "vehicle_type": "AMBULANCE",
        "start_node": "N_0_1",  # Outer District
        "target_node": "N_2_5",  # Harborview Stroke Center
        "weather": "BLIZZARD",
        "time_of_day": "OFF_PEAK",
        "patient_status": "Acute LVO stroke, tPA thrombolytic window closing fast.",
        "description": "Freezing roadway and extreme braking distances. ChronoRoute avoids treacherous narrow roads, utilizing wide express arterials where EVP prevents hazardous emergency stops on ice.",
        "incident_blockage": None
    }
}


def get_scenario(scenario_id: str) -> Dict[str, Any]:
    return SCENARIOS.get(scenario_id, SCENARIOS["cardiac_arrest_historic"])


def list_scenarios() -> List[Dict[str, Any]]:
    return list(SCENARIOS.values())
