"""
State definitions for the LangGraph Drone Fleet Agent.
Defines the typed state that flows through the agent graph.
"""

from typing import TypedDict, Literal, Annotated
from dataclasses import dataclass, field
from datetime import datetime
import operator


@dataclass
class DroneInfo:
    """Information about a single drone in the fleet."""
    id: str
    name: str
    x: float
    y: float
    z: float  # altitude (negative in NED coordinate system)
    status: Literal["idle", "scanning", "responding", "returning", "charging"]
    battery: float  # 0.0 to 1.0
    current_mission: str | None = None
    control_mode: Literal["auto", "manual"] = "auto"
    waypoints: list[tuple[float, float]] = field(default_factory=list)
    waypoint_index: int = 0
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "status": self.status,
            "battery": self.battery,
            "current_mission": self.current_mission,
            "control_mode": self.control_mode,
            "waypoints": self.waypoints,
        }


@dataclass
class SurvivorLocation:
    """Detected survivor/human heat signature."""
    id: str
    x: float
    y: float
    confidence: float  # 0.0 to 1.0
    detected_by: str  # drone ID
    timestamp: datetime = field(default_factory=datetime.now)
    rescued: bool = False
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "confidence": self.confidence,
            "detected_by": self.detected_by,
            "timestamp": self.timestamp.isoformat(),
            "rescued": self.rescued,
        }


@dataclass
class Mission:
    """A mission assigned to a drone."""
    id: str
    drone_id: str
    mission_type: Literal["scan", "investigate", "rescue", "return"]
    target_x: float
    target_y: float
    target_z: float
    status: Literal["pending", "active", "completed", "failed"]
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "drone_id": self.drone_id,
            "mission_type": self.mission_type,
            "target_x": self.target_x,
            "target_y": self.target_y,
            "target_z": self.target_z,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


@dataclass  
class Alert:
    """An alert to send to the frontend."""
    type: Literal["SURVIVOR_DETECTED", "DRONE_LOW_BATTERY", "MISSION_COMPLETE", "RESCUE_NEEDED"]
    message: str
    payload: dict
    timestamp: datetime = field(default_factory=datetime.now)


def merge_lists(a: list, b: list) -> list:
    """Merge two lists, used for accumulating state."""
    return a + b


@dataclass
class HeatSignature:
    """A thermal signature on the map (potential survivor)."""
    id: str
    x: float
    y: float
    intensity: float  # 0.0 to 1.0
    size: float
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "intensity": self.intensity,
            "size": self.size,
        }


class DroneFleetState(TypedDict):
    """
    The state of the entire drone fleet system.
    This is the state that flows through the LangGraph.
    """
    # Fleet information
    drones: list[DroneInfo]
    
    # Detections
    survivors: Annotated[list[SurvivorLocation], operator.add]
    
    # Active missions
    missions: list[Mission]
    
    # Alerts to emit
    alerts: Annotated[list[Alert], operator.add]
    
    # Scanned/explored cells (grid coordinates that drones have visited)
    # Each cell is a tuple (grid_x, grid_y) where grid is 30x30 (500 units per cell)
    scanned_cells: Annotated[list[tuple[int, int]], operator.add]
    
    # Current analysis from the AI
    situation_analysis: str
    
    # What action to take next
    next_action: Literal["scan", "respond", "coordinate", "idle", "end"]
    
    # Tick counter for simulation
    tick: int
    
    # Whether we're in mock mode (no AirSim)
    mock_mode: bool
