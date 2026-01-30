"""
LangGraph-compatible tools for drone fleet control.
Simplified for 2D terrain simulation (no AirSim).
"""

import uuid
from datetime import datetime
from langchain_core.tools import tool

from .state import DroneInfo, SurvivorLocation


# ============================================
# Drone Status Tools
# ============================================

@tool
def get_fleet_status(drones: list[dict]) -> list[dict]:
    """
    Get the current status of all drones in the fleet.
    
    Args:
        drones: Current drone state from the graph
    
    Returns:
        List of drone information
    """
    return drones


@tool
def get_idle_drones(drones: list[dict]) -> list[dict]:
    """
    Get all idle drones available for assignment.
    
    Args:
        drones: Current drone state
    
    Returns:
        List of idle drones
    """
    return [d for d in drones if d.get("status") == "idle"]


# ============================================
# Drone Command Tools  
# ============================================

@tool
def dispatch_drone_to_location(drone_id: str, target_x: float, target_y: float, mission_type: str = "investigate") -> dict:
    """
    Dispatch a drone to a specific location on the 2D map.
    
    Args:
        drone_id: The ID of the drone to dispatch
        target_x: Target X coordinate (0-15000)
        target_y: Target Y coordinate (0-15000)
        mission_type: Type of mission - 'scan', 'investigate', or 'rescue'
    
    Returns:
        Mission assignment confirmation
    """
    mission_id = f"mission_{uuid.uuid4().hex[:8]}"
    
    return {
        "success": True,
        "mission_id": mission_id,
        "drone_id": drone_id,
        "target": {"x": target_x, "y": target_y},
        "mission_type": mission_type,
    }


@tool
def create_scan_mission(drone_id: str, sector_x: float, sector_y: float) -> dict:
    """
    Create a scanning mission for a drone in a specific sector.
    
    Args:
        drone_id: Drone to assign
        sector_x: Sector center X
        sector_y: Sector center Y
    
    Returns:
        Mission details
    """
    return {
        "mission_id": f"scan_{uuid.uuid4().hex[:8]}",
        "drone_id": drone_id,
        "type": "scan",
        "sector": {"x": sector_x, "y": sector_y},
    }


# ============================================
# Detection Tools
# ============================================

@tool
def simulate_thermal_detection(drone_x: float, drone_y: float, drone_id: str) -> list[dict]:
    """
    Simulate thermal detection from a scanning drone.
    In a real system, this would process camera feeds.
    
    Args:
        drone_x: Drone's current X position
        drone_y: Drone's current Y position
        drone_id: ID of the scanning drone
    
    Returns:
        List of detected heat signatures (may be empty)
    """
    import random
    
    detections = []
    
    # 20% chance of detecting a survivor
    if random.random() < 0.20:
        survivor = {
            "id": f"survivor_{uuid.uuid4().hex[:6]}",
            "x": drone_x + random.uniform(-250, 250),
            "y": drone_y + random.uniform(-250, 250),
            "confidence": random.uniform(0.70, 0.98),
            "detected_by": drone_id,
            "timestamp": datetime.now().isoformat(),
        }
        detections.append(survivor)
    
    return detections


@tool
def prioritize_survivors(survivors: list[dict]) -> list[dict]:
    """
    Prioritize survivors for rescue based on confidence and location.
    
    Args:
        survivors: List of detected survivors
    
    Returns:
        Sorted list with highest priority first
    """
    # Sort by confidence (highest first)
    return sorted(survivors, key=lambda s: s.get("confidence", 0), reverse=True)


# Export all tools
drone_tools = [
    get_fleet_status,
    get_idle_drones,
    dispatch_drone_to_location,
    create_scan_mission,
    simulate_thermal_detection,
    prioritize_survivors,
]
