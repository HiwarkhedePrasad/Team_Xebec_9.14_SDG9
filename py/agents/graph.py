"""
LangGraph state machine for the drone fleet coordinator agent.
Orchestrates multi-drone operations for disaster response.
"""

import asyncio
import logging
from typing import Literal
from datetime import datetime

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from .state import DroneFleetState, DroneInfo, SurvivorLocation, Mission, Alert
from .tools import drone_tools, set_airsim_client
from . import airsim_bridge

logger = logging.getLogger(__name__)

# System prompt for the fleet coordinator
FLEET_COORDINATOR_PROMPT = """You are the Fleet Coordinator AI for a disaster response drone system.

Your mission: Coordinate a fleet of drones to efficiently search for survivors in a disaster zone and coordinate rescue operations.

Current capabilities:
- Monitor drone positions and battery levels
- Dispatch drones to scan specific areas  
- Detect survivors using thermal imaging
- Coordinate rescue responses when survivors are found
- Return low-battery drones to base

Decision framework:
1. SCAN: If drones are idle and areas remain unsearched, assign scan patterns
2. RESPOND: If survivors are detected with high confidence, dispatch rescue
3. COORDINATE: If multiple survivors detected, prioritize by confidence and accessibility
4. RETURN: If drone battery < 25%, return it to base immediately

Map info:
- 15000x15000 unit map (5km x 5km real scale)
- Known flood zones, earthquake faults, and settlements
- Base station at (7500, 7500)

Always prioritize survivor safety. Be efficient but thorough."""


def create_initial_state(mock_mode: bool = True) -> DroneFleetState:
    """Create the initial state for the drone fleet."""
    
    # Initialize drones
    drones = [
        DroneInfo(
            id="drone_alpha",
            name="D-Alpha", 
            x=3000, y=3000, z=-50,
            status="idle",
            battery=0.85,
        ),
        DroneInfo(
            id="drone_beta",
            name="D-Beta",
            x=4500, y=3500, z=-50, 
            status="idle",
            battery=0.92,
        ),
        DroneInfo(
            id="drone_gamma",
            name="D-Gamma",
            x=1500, y=2000, z=-50,
            status="idle", 
            battery=0.78,
        ),
    ]
    
    return {
        "drones": drones,
        "survivors_detected": [],
        "missions": [],
        "alerts": [],
        "situation_analysis": "",
        "next_action": "scan",
        "tick": 0,
        "mock_mode": mock_mode,
    }


# ============================================
# Graph Nodes
# ============================================

def analyze_situation(state: DroneFleetState) -> dict:
    """
    Analyze the current situation and decide on next actions.
    This is the "brain" of the coordinator.
    """
    drones = state["drones"]
    survivors = state["survivors_detected"]
    missions = state["missions"]
    
    # Count drone states
    idle_drones = [d for d in drones if d.status == "idle"]
    scanning_drones = [d for d in drones if d.status == "scanning"]
    low_battery_drones = [d for d in drones if d.battery < 0.25]
    
    # Count unrescued survivors
    unrescued = [s for s in survivors if not s.rescued]
    high_confidence = [s for s in unrescued if s.confidence > 0.8]
    
    # Determine next action
    if low_battery_drones:
        next_action = "coordinate"  # Return low battery drones
        analysis = f"⚠️ {len(low_battery_drones)} drone(s) have low battery. Returning to base."
    elif high_confidence:
        next_action = "respond"
        analysis = f"🚨 {len(high_confidence)} high-confidence survivor(s) detected! Initiating rescue."
    elif idle_drones:
        next_action = "scan"
        analysis = f"📡 {len(idle_drones)} drone(s) available for scanning. Assigning search patterns."
    else:
        next_action = "idle"
        analysis = f"✓ All drones active. {len(scanning_drones)} scanning, monitoring for detections."
    
    logger.info(f"Situation analysis: {analysis}")
    
    return {
        "situation_analysis": analysis,
        "next_action": next_action,
        "tick": state["tick"] + 1,
    }


def dispatch_scan_missions(state: DroneFleetState) -> dict:
    """
    Assign scanning missions to idle drones.
    Divides the map into sectors and assigns drones to unsearched areas.
    """
    import random
    
    drones = state["drones"]
    missions = state["missions"]
    new_missions = []
    updated_drones = []
    alerts = []
    
    # Define scan sectors (divide map into grid)
    sectors = [
        (2000, 2000), (5000, 2000), (8000, 2000), (11000, 2000),
        (2000, 5000), (5000, 5000), (8000, 5000), (11000, 5000),
        (2000, 8000), (5000, 8000), (8000, 8000), (11000, 8000),
        (2000, 11000), (5000, 11000), (8000, 11000), (11000, 11000),
    ]
    
    # Find already-assigned sectors
    assigned_sectors = {(m.target_x, m.target_y) for m in missions if m.status == "active"}
    available_sectors = [s for s in sectors if s not in assigned_sectors]
    
    for drone in drones:
        if drone.status == "idle" and available_sectors:
            # Assign a random available sector
            sector = random.choice(available_sectors)
            available_sectors.remove(sector)
            
            mission = Mission(
                id=f"scan_{drone.id}_{state['tick']}",
                drone_id=drone.id,
                mission_type="scan",
                target_x=sector[0],
                target_y=sector[1],
                target_z=-50,
                status="active",
            )
            new_missions.append(mission)
            
            # Update drone status
            drone.status = "scanning"
            drone.current_mission = mission.id
            
            logger.info(f"Assigned {drone.name} to scan sector ({sector[0]}, {sector[1]})")
        
        updated_drones.append(drone)
    
    if new_missions:
        alerts.append(Alert(
            type="MISSION_COMPLETE",
            message=f"Dispatched {len(new_missions)} drone(s) for scanning",
            payload={"missions": [m.id for m in new_missions]}
        ))
    
    return {
        "drones": updated_drones,
        "missions": missions + new_missions,
        "alerts": alerts,
    }


def respond_to_survivors(state: DroneFleetState) -> dict:
    """
    Coordinate response to detected survivors.
    Dispatch nearest available drone for rescue assistance.
    """
    import math
    
    drones = state["drones"]
    survivors = state["survivors_detected"]
    missions = state["missions"]
    alerts = []
    updated_drones = []
    new_missions = []
    
    # Get unrescued high-confidence survivors
    unrescued = [s for s in survivors if not s.rescued and s.confidence > 0.8]
    
    # Get available drones (idle or scanning with good battery)
    available = [d for d in drones if d.status in ["idle", "scanning"] and d.battery > 0.3]
    
    for survivor in unrescued[:len(available)]:  # Match survivors to available drones
        if not available:
            break
            
        # Find nearest drone
        nearest = min(available, key=lambda d: math.sqrt(
            (d.x - survivor.x)**2 + (d.y - survivor.y)**2
        ))
        available.remove(nearest)
        
        # Create rescue mission
        mission = Mission(
            id=f"rescue_{survivor.id}",
            drone_id=nearest.id,
            mission_type="rescue",
            target_x=survivor.x,
            target_y=survivor.y,
            target_z=-20,  # Lower altitude for rescue
            status="active",
        )
        new_missions.append(mission)
        
        # Update drone
        nearest.status = "responding"
        nearest.current_mission = mission.id
        
        # Create alert
        alerts.append(Alert(
            type="RESCUE_NEEDED",
            message=f"Survivor detected! {nearest.name} responding to ({survivor.x:.0f}, {survivor.y:.0f})",
            payload={
                "survivor_id": survivor.id,
                "drone_id": nearest.id,
                "location": {"x": survivor.x, "y": survivor.y},
                "confidence": survivor.confidence,
            }
        ))
        
        logger.info(f"🚨 Dispatched {nearest.name} to rescue survivor at ({survivor.x:.0f}, {survivor.y:.0f})")
    
    # Compile updated drones list
    drone_dict = {d.id: d for d in drones}
    for d in updated_drones:
        drone_dict[d.id] = d
    
    return {
        "drones": list(drone_dict.values()),
        "missions": missions + new_missions,
        "alerts": alerts,
    }


def coordinate_fleet(state: DroneFleetState) -> dict:
    """
    General fleet coordination - handle low battery, return drones, etc.
    """
    drones = state["drones"]
    missions = state["missions"]
    alerts = []
    updated_drones = []
    new_missions = []
    
    for drone in drones:
        if drone.battery < 0.25 and drone.status != "returning":
            # Create return mission
            mission = Mission(
                id=f"return_{drone.id}_{state['tick']}",
                drone_id=drone.id,
                mission_type="return",
                target_x=7500,  # Base
                target_y=7500,
                target_z=-10,
                status="active",
            )
            new_missions.append(mission)
            
            drone.status = "returning"
            drone.current_mission = mission.id
            
            alerts.append(Alert(
                type="DRONE_LOW_BATTERY",
                message=f"{drone.name} returning to base (battery: {drone.battery:.0%})",
                payload={"drone_id": drone.id, "battery": drone.battery}
            ))
            
            logger.warning(f"⚠️ {drone.name} low battery ({drone.battery:.0%}), returning to base")
        
        updated_drones.append(drone)
    
    return {
        "drones": updated_drones,
        "missions": missions + new_missions,
        "alerts": alerts,
    }


def simulate_detections(state: DroneFleetState) -> dict:
    """
    Simulate thermal detections from scanning drones (mock mode).
    In real mode, this would process actual camera feeds.
    """
    import random
    import uuid
    
    if not state["mock_mode"]:
        return {}  # No simulation in real mode
    
    drones = state["drones"]
    new_survivors = []
    alerts = []
    
    for drone in drones:
        if drone.status == "scanning":
            # 15% chance of detecting a survivor each tick
            if random.random() < 0.15:
                survivor = SurvivorLocation(
                    id=f"survivor_{uuid.uuid4().hex[:6]}",
                    x=drone.x + random.uniform(-300, 300),
                    y=drone.y + random.uniform(-300, 300),
                    confidence=random.uniform(0.65, 0.98),
                    detected_by=drone.id,
                )
                new_survivors.append(survivor)
                
                alerts.append(Alert(
                    type="SURVIVOR_DETECTED",
                    message=f"🔥 Heat signature detected by {drone.name}!",
                    payload=survivor.to_dict()
                ))
                
                logger.info(f"🔥 {drone.name} detected survivor at ({survivor.x:.0f}, {survivor.y:.0f})")
    
    return {
        "survivors_detected": new_survivors,
        "alerts": alerts,
    }


def should_continue(state: DroneFleetState) -> Literal["analyze", "end"]:
    """Determine if we should continue the loop or end."""
    # End after a certain number of ticks (for demo purposes)
    if state["tick"] >= 100:
        return "end"
    return "analyze"


def route_action(state: DroneFleetState) -> str:
    """Route to the appropriate action node based on analysis."""
    action = state["next_action"]
    if action == "scan":
        return "dispatch_scan"
    elif action == "respond":
        return "respond_survivors"
    elif action == "coordinate":
        return "coordinate_fleet"
    else:
        return "simulate"  # Idle, just simulate


# ============================================
# Build the Graph
# ============================================

def create_drone_fleet_agent():
    """
    Create and compile the LangGraph for drone fleet coordination.
    """
    # Create the graph with our state type
    graph = StateGraph(DroneFleetState)
    
    # Add nodes
    graph.add_node("analyze", analyze_situation)
    graph.add_node("dispatch_scan", dispatch_scan_missions)
    graph.add_node("respond_survivors", respond_to_survivors)
    graph.add_node("coordinate_fleet", coordinate_fleet)
    graph.add_node("simulate", simulate_detections)
    
    # Set entry point
    graph.set_entry_point("analyze")
    
    # Add conditional edges from analyze
    graph.add_conditional_edges(
        "analyze",
        route_action,
        {
            "dispatch_scan": "dispatch_scan",
            "respond_survivors": "respond_survivors",
            "coordinate_fleet": "coordinate_fleet",
            "simulate": "simulate",
        }
    )
    
    # All action nodes go to simulate, then back to analyze (or end)
    graph.add_edge("dispatch_scan", "simulate")
    graph.add_edge("respond_survivors", "simulate")
    graph.add_edge("coordinate_fleet", "simulate")
    
    # Simulate goes back to analyze or ends
    graph.add_conditional_edges(
        "simulate",
        should_continue,
        {
            "analyze": "analyze",
            "end": END,
        }
    )
    
    # Compile the graph
    return graph.compile()


async def run_agent_loop(
    emit_callback=None,
    tick_interval: float = 2.0,
    mock_mode: bool = True
):
    """
    Run the drone fleet agent in a loop.
    
    Args:
        emit_callback: Async function to emit updates (e.g., Socket.IO emit)
        tick_interval: Seconds between agent ticks
        mock_mode: If True, use simulated data; if False, connect to AirSim
    """
    # Try to connect to AirSim
    if not mock_mode:
        connected = airsim_bridge.try_connect_airsim()
        if connected:
            set_airsim_client(airsim_bridge.get_client(), mock=False)
        else:
            logger.warning("Falling back to mock mode")
            mock_mode = True
    
    set_airsim_client(None, mock=mock_mode)
    
    # Create the agent graph
    agent = create_drone_fleet_agent()
    
    # Initialize state
    state = create_initial_state(mock_mode=mock_mode)
    
    logger.info(f"🚀 Starting Drone Fleet Coordinator (mock_mode={mock_mode})")
    
    # Run the agent loop
    async for event in agent.astream(state):
        # Get the latest state from the event
        for node_name, node_output in event.items():
            logger.debug(f"Node '{node_name}' output: {node_output}")
            
            # Emit updates via callback
            if emit_callback:
                # Emit drone positions
                if "drones" in node_output:
                    await emit_callback("drone_update", {
                        "drones": [d.to_dict() if hasattr(d, 'to_dict') else d for d in node_output["drones"]]
                    })
                
                # Emit alerts
                if "alerts" in node_output:
                    for alert in node_output["alerts"]:
                        await emit_callback("alert", {
                            "type": alert.type,
                            "message": alert.message,
                            "payload": alert.payload,
                        })
        
        # Wait before next tick
        await asyncio.sleep(tick_interval)
    
    logger.info("Agent loop completed")
