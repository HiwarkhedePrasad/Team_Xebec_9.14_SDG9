import logging
import random
import math
from typing import List, Dict, Any

from .state import DroneFleetState, DroneInfo, Alert, Mission

logger = logging.getLogger(__name__)

# Constants
GRID_CELL_SIZE = 500
GRID_SIZE = 30
SCAN_RADIUS = 2 

# Global queue for manual commands from socket/API
# Structure: { drone_id: { "command": str, "mode": "manual"|"auto", "waypoints": [...] } }
MANUAL_COMMANDS = {}

def update_positions(state: DroneFleetState) -> dict:
    """Simulate drone movement based on missions or manual waypoints."""
    drones = list(state["drones"])
    missions = list(state["missions"])
    survivors = state.get("survivors_detected", [])
    alerts = [] # Capture new alerts (like Mission Complete)
    
    # DEBUG: Log drone states at start of tick
    if state["tick"] % 20 == 0:
        for d in drones[:3]:  # Log first 3 drones
            logger.info(f"🔍 DEBUG [{state['tick']}] {d.name}: Pos({d.x:.0f},{d.y:.0f}) Status={d.status} WP_len={len(d.waypoints)} WP_idx={d.waypoint_index}")
    
    # Get current grid or init if missing
    # Each cell is now a dict: {"count": 0-3, "drone_ids": []} for 3-layer redundant scanning
    current_grid = state.get("scanned_cells")
    if not current_grid or not isinstance(current_grid[0][0], dict):
        # Initialize grid with dict per cell for 3-layer tracking
        current_grid = [[{"count": 0, "drone_ids": []} for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
    
    # Deep copy grid to modify it
    updated_grid = [[{"count": cell["count"], "drone_ids": cell["drone_ids"][:]} for cell in row] for row in current_grid]
    
    updated_drones = []
    
    SPEED = 500  # Units per tick (Faster movement for better coverage)
    
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
        # 2. Movement Logic - Unified (Auto + Manual both follow waypoints if available)
        
        # Separation Force - Keep drones from clustering (RE-ENABLED with better tuning)
        sep_x, sep_y = 0.0, 0.0
        MIN_DIST = 800.0  # Minimum safe distance between drones (reduced from 1500)
        
        for other in drones:
            if other.id != drone.id:
                dx_sep = drone.x - other.x
                dy_sep = drone.y - other.y
                dist_sq = dx_sep**2 + dy_sep**2
                
                if dist_sq < MIN_DIST**2 and dist_sq > 0:
                    dist = math.sqrt(dist_sq)
                    # Gentler repulsion force (reduced from 1.5x to 0.5x)
                    strength = (MIN_DIST - dist) / MIN_DIST
                    sep_x += (dx_sep / dist) * strength * (SPEED * 0.5)
                    sep_y += (dy_sep / dist) * strength * (SPEED * 0.5)
                elif dist_sq == 0:
                    # If exactly overlapping, push in random direction
                    sep_x += random.uniform(-1, 1) * SPEED * 0.3
                    sep_y += random.uniform(-1, 1) * SPEED * 0.3

        if waypoints and waypoint_index < len(waypoints):
            # Follow the path (A* or Manual)
            target_x, target_y = waypoints[waypoint_index]
            
            # Debug Log for one drone
            if drone.name == "D-Alpha" and state["tick"] % 10 == 0:
                 logger.debug(f"🐛 {drone.name}: Pos({drone.x:.0f}, {drone.y:.0f}) -> Target({target_x}, {target_y}) Idx:{waypoint_index}/{len(waypoints)}")
            
            dx = target_x - drone.x
            dy = target_y - drone.y
            dist = math.sqrt(dx*dx + dy*dy)
            
            # Check if reached waypoint - use smaller threshold
            if dist < 50:
                waypoint_index += 1
                # Get next waypoint if available
                if waypoint_index < len(waypoints):
                    target_x, target_y = waypoints[waypoint_index]
                    dx = target_x - drone.x
                    dy = target_y - drone.y
                    dist = math.sqrt(dx*dx + dy*dy)
            
            # Move towards waypoint (if we still have one)
            if waypoint_index < len(waypoints) and dist > 0:
                # CLAMP movement to not overshoot - this prevents oscillation!
                move_speed = min(SPEED, dist)
                
                goal_x = (dx / dist) * move_speed
                goal_y = (dy / dist) * move_speed
                
                # LIMIT separation force to prevent it overpowering the goal
                sep_limit = SPEED * 0.3  # Max 30% of movement speed
                sep_mag = math.sqrt(sep_x**2 + sep_y**2)
                if sep_mag > sep_limit:
                    scale = sep_limit / sep_mag
                    sep_x *= scale
                    sep_y *= scale
                
                new_x = drone.x + goal_x + sep_x
                new_y = drone.y + goal_y + sep_y
                
                # DEBUG: Log movement every 10 ticks for D-Alpha
                if drone.name == "D-Alpha" and state["tick"] % 10 == 0:
                    logger.info(f"✈️ MOVE {drone.name}: ({drone.x:.0f},{drone.y:.0f}) → ({new_x:.0f},{new_y:.0f}) | Target: ({target_x:.0f},{target_y:.0f})")
            
            # Mission Completion Checks
            # Check if near mission target (regardless of waypoints, for safety)
            if current_mission:
                mission = next((m for m in missions if m.id == current_mission), None)
                if mission:
                    dist_to_target = math.sqrt((drone.x - mission.target_x)**2 + (drone.y - mission.target_y)**2)
                    
                    # Scan Logic / Rescue / Deploy
                    if dist_to_target < 100:
                        
                        if mission.mission_type == "scan":
                             mission.status = "completed"
                             current_mission = None
                             new_status = "idle"
                             waypoints = []
                        
                        elif mission.mission_type == "rescue":
                             mission.status = "completed"
                             current_mission = None
                             new_status = "idle"
                             waypoints = []
                             # Mark survivor rescued
                             for s in survivors:
                                 if s.x == mission.target_x and s.y == mission.target_y:
                                     s.rescued = True
                                     alerts.append(Alert(
                                         type="MISSION_COMPLETE",
                                         message=f"✅ {drone.name} rescued survivor!",
                                         payload={"drone_id": drone.id, "survivor_id": s.id}
                                     ))
                                     


            # Keep within bounds
            new_x = max(0, min(15000, new_x))
            new_y = max(0, min(15000, new_y))
            
            # Drain battery
            new_battery = max(0, new_battery - 0.0005)
            
        elif control_mode == "auto" and current_mission:
             # Fallback for Auto without waypoints (shouldn't happen with A*)
             # But keeping purely for safety
            mission = next((m for m in missions if m.id == drone.current_mission), None)
            if mission and mission.status == "active":
                dx = mission.target_x - drone.x
                dy = mission.target_y - drone.y
                dist = math.sqrt(dx*dx + dy*dy)
                
                if dist < SPEED:
                    new_x, new_y = mission.target_x, mission.target_y
                    mission.status = "completed"
                    current_mission = None
                    new_status = "idle"
                    if mission.mission_type == "return":
                            new_status = "idle" 
                            new_battery = 1.0   
                            logger.info(f"🔋 {drone.name} recharged at base")
                else:
                    new_x = drone.x + (dx / dist) * SPEED + sep_x
                    new_y = drone.y + (dy / dist) * SPEED + sep_y
                
                # Keep within bounds
                new_x = max(0, min(15000, new_x))
                new_y = max(0, min(15000, new_y))
                
                new_battery = max(0, new_battery - 0.0005)
        
        # Deadlock Fix: If scanning and no mission, switch to idle so we can get a new mission
        # This handles the transition from "arrived" -> "ready for next"
        if new_status == "scanning" and not current_mission and control_mode == "auto":
             new_status = "idle"

        updated_drones.append(DroneInfo(
            id=drone.id, name=drone.name,
            x=new_x,
            y=new_y,
            z=drone.z,
            status=new_status,
            battery=new_battery,
            current_mission=current_mission,
            control_mode=control_mode,
            waypoints=waypoints,
            waypoint_index=waypoint_index,
            type=drone.type
        ))
        
        # Update Scan Grid (3-Layer Redundant Scanning)
        # Each cell tracks how many unique drones have scanned it (up to 3)
        cx = int(new_x // GRID_CELL_SIZE)
        cy = int(new_y // GRID_CELL_SIZE)
         
        for dy in range(-SCAN_RADIUS, SCAN_RADIUS + 1):
             for dx in range(-SCAN_RADIUS, SCAN_RADIUS + 1):
                 nx, ny = cx + dx, cy + dy
                 if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE:
                     cell = updated_grid[ny][nx]
                     # Add drone ID if not already visited by this drone (max 3 layers)
                     if drone.id not in cell["drone_ids"] and cell["count"] < 3:
                         cell["drone_ids"].append(drone.id)
                         cell["count"] += 1
    
    return {
        "drones": updated_drones,
        "scanned_cells": updated_grid,
        "survivors_detected": survivors, # Needed to return rescued status updates
        "alerts": alerts,  # Only return new alerts from this tick (not accumulated)
    }