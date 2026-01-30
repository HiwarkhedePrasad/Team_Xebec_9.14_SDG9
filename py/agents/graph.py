"""
LangGraph state machine for drone fleet coordination.
Simplified for 2D terrain simulation (no AirSim).
"""

import asyncio
import logging
import random
import math
import uuid
from typing import Literal
from datetime import datetime

from langgraph.graph import StateGraph, END

from .state import DroneFleetState, DroneInfo, SurvivorLocation, Mission, Alert, HeatSignature

logger = logging.getLogger(__name__)

# Global queue for manual commands from socket/API
# Structure: { drone_id: { "command": str, "mode": "manual"|"auto", "waypoints": [...] } }
MANUAL_COMMANDS = {}


# ============================================
# Initial State
# ============================================

# Grid constants for fog of war
GRID_CELL_SIZE = 500  # Each cell is 500x500 units
GRID_SIZE = 30  # 30x30 grid = 15000x15000 map
SCAN_RADIUS = 2  # Drones scan 2 cells around them


def create_initial_state() -> DroneFleetState:
    """Create the initial state for the drone fleet with 10 drones."""
    
    # Initialize 10 drones starting from top-left corner (base station)
    base_x, base_y = 500, 500
    drone_names = [
        "Alpha", "Beta", "Gamma", "Delta", "Epsilon",
        "Zeta", "Eta", "Theta", "Iota", "Kappa"
    ]
    
    drones = []
    for i, name in enumerate(drone_names):
        # Spread drones in a small grid pattern at starting corner
        row = i // 5  # 2 rows
        col = i % 5   # 5 columns
        offset_x = col * 100
        offset_y = row * 100
        
        drones.append(DroneInfo(
            id=f"drone_{name.lower()}",
            name=f"D-{name}",
            x=base_x + offset_x,
            y=base_y + offset_y,
            z=-20,  # Flying at 20m height
            status="idle",
            battery=1.0,  # Full battery
            control_mode="auto",
            waypoints=[],
        ))
    
    # Heat Signatures (Persistent)
    heat_signatures = []
    for _ in range(15):
        # Distribute mostly away from start corner
        padding = 1000
        heat_signatures.append(HeatSignature(
            id=f"heat_{uuid.uuid4().hex[:6]}",
            x=random.uniform(padding, 15000 - padding),
            y=random.uniform(padding, 15000 - padding),
            intensity=random.uniform(0.5, 1.0),
            size=random.uniform(300, 800),  # Large area size
        ))
    
    # Initialize with starting corner area already scanned
    scanned = []
    for x in range(5):
        for y in range(5):
             scanned.append((x, y))

    return {
        "drones": drones,
        "missions": [],
        "survivors": [],
        "alerts": [],
        "tick": 0,
        "scanned_cells": scanned,
        "heat_signatures": heat_signatures,
        "next_action": "analyze",
    }


# ============================================
# Graph Nodes
# ============================================

def analyze_situation(state: DroneFleetState) -> dict:
    """Analyze current situation and decide on next action."""
    drones = state["drones"]
    survivors = state["survivors_detected"]
    
    idle_drones = [d for d in drones if d.status == "idle"]
    scanning_drones = [d for d in drones if d.status == "scanning"]
    low_battery_drones = [d for d in drones if d.battery < 0.25]
    unrescued = [s for s in survivors if not s.rescued]
    high_confidence = [s for s in unrescued if s.confidence > 0.8]
    
    # Determine next action
    if low_battery_drones:
        next_action = "coordinate"
        analysis = f"⚠️ {len(low_battery_drones)} drone(s) low battery"
    elif high_confidence:
        next_action = "respond"
        analysis = f"🚨 {len(high_confidence)} survivor(s) need rescue!"
    elif idle_drones:
        next_action = "scan"
        analysis = f"📡 {len(idle_drones)} drone(s) ready to scan"
    else:
        next_action = "idle"
        analysis = f"✓ {len(scanning_drones)} drone(s) scanning"
    
    logger.info(f"[Tick {state['tick']}] {analysis}")
    
    return {
        "situation_analysis": analysis,
        "next_action": next_action,
        "tick": state["tick"] + 1,
    }


def dispatch_scan_missions(state: DroneFleetState) -> dict:
    """Assign scanning missions to idle drones - target unexplored areas."""
    drones = list(state["drones"])
    missions = list(state["missions"])
    scanned = set(state.get("scanned_cells", []))
    alerts = []
    
    # Find unexplored cells (not in scanned set)
    unexplored = []
    for cx in range(GRID_SIZE):
        for cy in range(GRID_SIZE):
            if (cx, cy) not in scanned:
                # Convert grid cell to world coordinates (center of cell)
                world_x = cx * GRID_CELL_SIZE + GRID_CELL_SIZE // 2
                world_y = cy * GRID_CELL_SIZE + GRID_CELL_SIZE // 2
                unexplored.append((world_x, world_y))
    
    # If all explored, we're done!
    if not unexplored:
        logger.info("🎉 Map fully explored!")
        return {"drones": drones, "missions": missions, "alerts": alerts}
    
    # Shuffle unexplored to distribute drones
    random.shuffle(unexplored)
    
    # Find drones that can be assigned (idle or scanning without mission)
    # Filter out MANUAL drones
    updated_drones = []
    assigned_this_tick = set()
    
    # Collect truly idle auto drones
    idle_auto_drones = [d for d in drones if d.status == "idle" and d.control_mode == "auto"]

    if not idle_auto_drones:
        # If no idle auto drones, just update existing drones and return
        for drone in drones:
            if drone.control_mode == "manual":
                updated_drones.append(drone)
                continue
            # Reset scanning drones to idle if they don't have an active mission
            if drone.status == "scanning" and not drone.current_mission:
                drone = DroneInfo(
                    id=drone.id, name=drone.name,
                    x=drone.x, y=drone.y, z=drone.z,
                    status="idle", battery=drone.battery,
                    current_mission=None, control_mode=drone.control_mode,
                    waypoints=drone.waypoints, waypoint_index=drone.waypoint_index
                )
            updated_drones.append(drone)
        return {"drones": updated_drones, "missions": missions, "alerts": alerts}

    for drone in drones:
        if drone.control_mode == "manual":
            updated_drones.append(drone)
            continue
            
        # Reset scanning drones to idle if they don't have an active mission
        if drone.status == "scanning" and not drone.current_mission:
            drone = DroneInfo(
                id=drone.id, name=drone.name,
                x=drone.x, y=drone.y, z=drone.z,
                status="idle", battery=drone.battery,
                current_mission=None, control_mode=drone.control_mode,
                waypoints=drone.waypoints, waypoint_index=drone.waypoint_index
            )
        
        # Assign idle drones to unexplored areas
        if drone.status == "idle" and drone.control_mode == "auto" and unexplored and drone.battery > 0.20:
            # Find nearest unexplored cell to this drone
            nearest = min(unexplored, key=lambda p: math.sqrt(
                (p[0] - drone.x)**2 + (p[1] - drone.y)**2
            ))
            unexplored.remove(nearest)
            
            mission = Mission(
                id=f"explore_{drone.id}_{state['tick']}",
                drone_id=drone.id,
                mission_type="scan",
                target_x=nearest[0],
                target_y=nearest[1],
                target_z=-50,
                status="active",
            )
            missions.append(mission)
            
            drone = DroneInfo(
                id=drone.id, name=drone.name,
                x=drone.x, y=drone.y, z=drone.z,
                status="scanning", battery=drone.battery,
                current_mission=mission.id, control_mode=drone.control_mode,
                waypoints=drone.waypoints, waypoint_index=drone.waypoint_index
            )
            
            logger.info(f"📡 {drone.name} → explore ({nearest[0]}, {nearest[1]})")
        
        updated_drones.append(drone)
    
    # Log exploration progress
    explored_count = len(scanned)
    total_cells = GRID_SIZE * GRID_SIZE
    progress = (explored_count / total_cells) * 100
    logger.info(f"🗺️ Exploration: {progress:.1f}% ({explored_count}/{total_cells} cells)")
    
    return {
        "drones": updated_drones,
        "missions": missions,
        "alerts": alerts,
    }


def respond_to_survivors(state: DroneFleetState) -> dict:
    """Dispatch drones to rescue detected survivors."""
    drones = list(state["drones"])
    survivors = state["survivors_detected"]
    missions = list(state["missions"])
    alerts = []
    
    unrescued = [s for s in survivors if not s.rescued and s.confidence > 0.8]
    available = [d for d in drones if d.status in ["idle", "scanning"] and d.battery > 0.3 and d.control_mode == "auto"]
    
    updated_drones = []
    updated_survivors = list(survivors)
    
    for survivor in unrescued[:len(available)]:
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
            target_z=-20,
            status="active",
        )
        missions.append(mission)
        
        # Update drone
        idx = next(i for i, d in enumerate(drones) if d.id == nearest.id)
        drones[idx] = DroneInfo(
            id=nearest.id,
            name=nearest.name,
            x=nearest.x,
            y=nearest.y,
            z=nearest.z,
            status="responding",
            battery=nearest.battery,
            current_mission=mission.id,
            control_mode=nearest.control_mode,
            waypoints=nearest.waypoints,
            waypoint_index=nearest.waypoint_index,
        )
        
        # Mark survivor as being rescued
        for i, s in enumerate(updated_survivors):
            if s.id == survivor.id:
                updated_survivors[i].rescued = True
        
        alerts.append(Alert(
            type="RESCUE_NEEDED",
            message=f"🚁 {nearest.name} responding to survivor!",
            payload={
                "survivor_id": survivor.id,
                "drone_id": nearest.id,
                "location": {"x": survivor.x, "y": survivor.y},
            }
        ))
        
        logger.info(f"🚁 {nearest.name} → rescue at ({survivor.x:.0f}, {survivor.y:.0f})")
    
    return {
        "drones": drones,
        "survivors_detected": updated_survivors,
        "missions": missions,
        "alerts": alerts,
    }


def coordinate_fleet(state: DroneFleetState) -> dict:
    """Handle low battery and return drones."""
    drones = list(state["drones"])
    missions = list(state["missions"])
    alerts = []
    updated_drones = []
    
    for drone in drones:
        if drone.battery < 0.25 and drone.status != "returning" and drone.control_mode == "auto":
            mission = Mission(
                id=f"return_{drone.id}_{state['tick']}",
                drone_id=drone.id,
                mission_type="return",
                target_x=7500,
                target_y=7500,
                target_z=-10,
                status="active",
            )
            missions.append(mission)
            
            drone = DroneInfo(
                id=drone.id,
                name=drone.name,
                x=drone.x,
                y=drone.y,
                z=drone.z,
                status="returning",
                battery=drone.battery,
                current_mission=mission.id,
                control_mode=drone.control_mode,
                waypoints=drone.waypoints,
                waypoint_index=drone.waypoint_index,
            )
            
            alerts.append(Alert(
                type="DRONE_LOW_BATTERY",
                message=f"⚠️ {drone.name} returning ({drone.battery:.0%} battery)",
                payload={"drone_id": drone.id, "battery": drone.battery}
            ))
            
            logger.warning(f"⚠️ {drone.name} low battery, returning")
        
        updated_drones.append(drone)
    
    return {
        "drones": updated_drones,
        "missions": missions,
        "alerts": alerts,
    }


def update_positions(state: DroneFleetState) -> dict:
    """Simulate drone movement based on missions or manual waypoints."""
    drones = list(state["drones"])
    missions = list(state["missions"])
    new_scanned_cells = []
    updated_drones = []
    
    SPEED = 200  # Units per tick (approx 66 m/s)
    
    for drone in drones:
        new_x, new_y = drone.x, drone.y
        new_status = drone.status
        new_battery = drone.battery
        current_mission = drone.current_mission
        control_mode = drone.control_mode
        waypoints = list(drone.waypoints)
        waypoint_index = drone.waypoint_index
        
        # 1. Apply any pending manual commands
        if drone.id in MANUAL_COMMANDS:
            cmd = MANUAL_COMMANDS.pop(drone.id)
            if "mode" in cmd:
                control_mode = cmd["mode"]
            if "waypoints" in cmd:
                waypoints = cmd["waypoints"]
                waypoint_index = 0
                new_status = "active" if waypoints else "idle"
            # Clear mission if switching to manual
            if control_mode == "manual":
                current_mission = None
        
        # 2. Movement Logic
        if control_mode == "manual":
            # Manual Control: Follow waypoints
            if waypoints and waypoint_index < len(waypoints):
                target_x, target_y = waypoints[waypoint_index]
                
                dx = target_x - drone.x
                dy = target_y - drone.y
                dist = math.sqrt(dx*dx + dy*dy)
                
                if dist < SPEED:
                    # Arrived at waypoint
                    new_x, new_y = target_x, target_y
                    waypoint_index += 1
                    
                    if waypoint_index >= len(waypoints):
                        # End of path
                        new_status = "idle"
                else:
                    # Move towards waypoint
                    new_status = "active"
                    new_x = drone.x + (dx / dist) * SPEED
                    new_y = drone.y + (dy / dist) * SPEED
            else:
                new_status = "idle"
                
        else:
            # Auto Logic: Follow Missions
            if drone.current_mission:
                # Find the mission
                mission = next((m for m in missions if m.id == drone.current_mission), None)
                if mission and mission.status == "active":
                    # Calculate direction
                    dx = mission.target_x - drone.x
                    dy = mission.target_y - drone.y
                    dist = math.sqrt(dx*dx + dy*dy)
                    
                    if dist < SPEED:
                        # Arrived at destination
                        new_x, new_y = mission.target_x, mission.target_y
                        mission.status = "completed"
                        
                        # Reset to idle (or scanning at destination)
                        new_status = "scanning" if mission.mission_type == "scan" else "idle"
                        if mission.mission_type == "return":
                            new_status = "charging"
                            new_battery = min(1.0, new_battery + 0.1)  # Recharge
                        current_mission = None
                    else:
                        # Move towards target
                        new_x = drone.x + (dx / dist) * SPEED
                        new_y = drone.y + (dy / dist) * SPEED
                    
                    # Drain battery slightly
                    new_battery = max(0, new_battery - 0.003)
        
        # Track cells scanned by this drone (fog of war reveal)
        cell_x = int(new_x // GRID_CELL_SIZE)
        cell_y = int(new_y // GRID_CELL_SIZE)
        
        # Scan cells in radius around drone
        for dx in range(-SCAN_RADIUS, SCAN_RADIUS + 1):
            for dy in range(-SCAN_RADIUS, SCAN_RADIUS + 1):
                cx, cy = cell_x + dx, cell_y + dy
                if 0 <= cx < GRID_SIZE and 0 <= cy < GRID_SIZE:
                    new_scanned_cells.append((cx, cy))
        
        updated_drones.append(DroneInfo(
            id=drone.id,
            name=drone.name,
            x=new_x,
            y=new_y,
            z=drone.z,
            status=new_status,
            battery=new_battery,
            current_mission=current_mission,
            control_mode=control_mode,
            waypoints=waypoints,
            waypoint_index=waypoint_index,
        ))
    
    return {
        "drones": updated_drones,
        "scanned_cells": new_scanned_cells,
    }


def simulate_detections(state: DroneFleetState) -> dict:
    """Simulate thermal detections from scanning drones."""
    drones = state["drones"]
    new_survivors = []
    alerts = []
    
    for drone in drones:
        if drone.status == "scanning":
            # 12% chance of detection per tick
            if random.random() < 0.12:
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
                    message=f"🔥 {drone.name} detected heat signature!",
                    payload=survivor.to_dict()
                ))
                
                logger.info(f"🔥 {drone.name} found survivor at ({survivor.x:.0f}, {survivor.y:.0f})")
    
    return {
        "survivors_detected": new_survivors,
        "alerts": alerts,
    }


def should_continue(state: DroneFleetState) -> Literal["continue", "end"]:
    """Check if we should continue the simulation."""
    if state["tick"] >= 1000:  # Limit for safety
        return "end"
    return "continue"


def route_action(state: DroneFleetState) -> str:
    """Route to appropriate action based on analysis."""
    action = state["next_action"]
    if action == "scan":
        return "dispatch_scan"
    elif action == "respond":
        return "respond_survivors"
    elif action == "coordinate":
        return "coordinate_fleet"
    return "update_positions"


# ============================================
# Build Graph
# ============================================

def create_drone_fleet_agent():
    """Create the LangGraph for drone fleet coordination."""
    graph = StateGraph(DroneFleetState)
    
    # Add nodes
    graph.add_node("analyze", analyze_situation)
    graph.add_node("dispatch_scan", dispatch_scan_missions)
    graph.add_node("respond_survivors", respond_to_survivors)
    graph.add_node("coordinate_fleet", coordinate_fleet)
    graph.add_node("update_positions", update_drone_positions)
    graph.add_node("simulate", simulate_detections)
    
    # Entry point
    graph.set_entry_point("analyze")
    
    # Routing from analyze
    graph.add_conditional_edges(
        "analyze",
        route_action,
        {
            "dispatch_scan": "dispatch_scan",
            "respond_survivors": "respond_survivors",
            "coordinate_fleet": "coordinate_fleet",
            "update_positions": "update_positions",
        }
    )
    
    # All actions -> update positions -> simulate -> check continue
    graph.add_edge("dispatch_scan", "update_positions")
    graph.add_edge("respond_survivors", "update_positions")
    graph.add_edge("coordinate_fleet", "update_positions")
    graph.add_edge("update_positions", "simulate")
    
    graph.add_conditional_edges(
        "simulate",
        should_continue,
        {
            "continue": "analyze",
            "end": END,
        }
    )
    
    return graph.compile()


async def run_agent_loop(
    emit_callback=None,
    tick_interval: float = 3.0,
):
    """
    Run the drone fleet agent in a continuous loop.
    
    Args:
        emit_callback: Async function to emit Socket.IO events
        tick_interval: Seconds between agent ticks
    """
    agent = create_drone_fleet_agent()
    state = create_initial_state()
    
    logger.info("🚀 Drone Fleet Coordinator started (2D simulation mode)")
    
    try:
        async for event in agent.astream(state):
            for node_name, node_output in event.items():
                logger.debug(f"[{node_name}] {node_output}")
                
                if emit_callback:
                    # Emit drone positions
                    if "drones" in node_output:
                        drones_data = [
                            d.to_dict() if hasattr(d, 'to_dict') else d 
                            for d in node_output["drones"]
                        ]
                        await emit_callback("drone_update", {"drones": drones_data})
                    
                    # Emit scanned cells for fog of war
                    if "scanned_cells" in node_output and node_output["scanned_cells"]:
                        await emit_callback("scan_update", {
                            "cells": node_output["scanned_cells"]
                        })
                    
                    # Emit alerts
                    if "alerts" in node_output:
                        for alert in node_output["alerts"]:
                            await emit_callback("alert", {
                                "type": alert.type,
                                "message": alert.message,
                                "payload": alert.payload,
                            })
            
            await asyncio.sleep(tick_interval)
            
    except asyncio.CancelledError:
        logger.info("Agent loop cancelled")
        raise
    except Exception as e:
        logger.error(f"Agent error: {e}")
        raise
    
    logger.info("Agent loop completed")
