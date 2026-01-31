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
from .pathfinding import a_star_search

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
        "survivors_detected": [],
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
        "alerts": [],  # Clear alerts from previous tick
    }


def dispatch_scan_missions(state: DroneFleetState) -> dict:
    """Assign scanning missions to idle drones - target unexplored or under-scanned areas."""
    drones = list(state["drones"])
    missions = list(state["missions"])
    alerts = []
    
    # Get scanned_cells grid (new 3-layer format)
    scanned_grid = state.get("scanned_cells", [])
    
    # Build set of fully scanned cells (count >= 3) for backward compatibility
    fully_scanned = set()
    needs_more_scans = []  # Cells with count < 3
    
    if isinstance(scanned_grid, list) and len(scanned_grid) == GRID_SIZE:
        # New format: 2D grid where each cell is {"count": 0-3, "drone_ids": []}
        for cy in range(GRID_SIZE):
            for cx in range(GRID_SIZE):
                cell = scanned_grid[cy][cx] if isinstance(scanned_grid[cy], list) else {}
                count = cell.get("count", 0) if isinstance(cell, dict) else (3 if cell else 0)
                if count >= 3:
                    fully_scanned.add((cx, cy))
                else:
                    # This cell needs more scans (0, 1, or 2 drones have scanned it)
                    needs_more_scans.append((cx, cy, count))
    else:
        # Old format: list of (x,y) tuples
        if isinstance(scanned_grid, list):
            for cell in scanned_grid:
                if isinstance(cell, (tuple, list)) and len(cell) == 2:
                    fully_scanned.add((cell[0], cell[1]))
        # Build needs_more_scans for cells not in fully_scanned
        for cx in range(GRID_SIZE):
            for cy in range(GRID_SIZE):
                if (cx, cy) not in fully_scanned:
                    needs_more_scans.append((cx, cy, 0))
    
    # Find cells that need scanning (prioritize by count - lower count = higher priority)
    unexplored = []
    needs_more_scans.sort(key=lambda x: x[2])  # Sort by count ascending
    
    for cx, cy, count in needs_more_scans:
        # Convert grid cell to world coordinates (center of cell)
        world_x = cx * GRID_CELL_SIZE + GRID_CELL_SIZE // 2
        world_y = cy * GRID_CELL_SIZE + GRID_CELL_SIZE // 2
        unexplored.append((world_x, world_y))

    # Log unexplored count to debug "stopping halfway" issue
    if state['tick'] % 20 == 0:
        logger.info(f"📊 Unexplored targets: {len(unexplored)} | Needs more scans: {len(needs_more_scans)}")

    # Check for 100% full coverage (all 3 layers) for logging
    total_cells = GRID_SIZE * GRID_SIZE
    if len(fully_scanned) == total_cells and not getattr(dispatch_scan_missions, "logged_complete", False):
        logger.info("🎉 Map fully explored with 3-layer redundancy!")
        dispatch_scan_missions.logged_complete = True
    
    # If all cells are fully scanned, add some random rescan targets for continued coverage
    if not unexplored and fully_scanned:
        # Convert fully scanned set back to world coordinates for random patrol
        scanned_list = list(fully_scanned)
        num_rescan = min(len(scanned_list), max(5, int(len(scanned_list) * 0.1)))
        rescan_cells = random.sample(scanned_list, num_rescan)
        
        for cx, cy in rescan_cells:
            world_x = cx * GRID_CELL_SIZE + GRID_CELL_SIZE // 2
            world_y = cy * GRID_CELL_SIZE + GRID_CELL_SIZE // 2
            unexplored.append((world_x, world_y))

    if not unexplored:
        # Should rarely happen with re-scan logic
        return {"drones": drones, "missions": missions, "alerts": alerts}
    
    # Shuffle unexplored to distribute drones (but keep general prioritization)
    # random.shuffle(unexplored) # Don't shuffle strictly, we want low counts first?
    # Actually, shuffling within "same count" groups would be better, but simple shuffle is fine if we have enough targets
    


    # Memory Cleanup: Remove completed missions older than 100 ticks
    # Or just keep active ones + last 10 completed?
    # Simple cleanup: keep only active missions
    active_missions = [m for m in missions if m.status != "completed"]
    # If we want to keep some history, ok, but for now strict cleanup to prevent leak
    missions = active_missions
    
    # Find drones that can be assigned (idle or scanning without mission)
    
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
        
        # Assign idle drones to unexplored areas - spread them out and PRIORITY BY SCAN COUNT
        if drone.status == "idle" and drone.control_mode == "auto" and drone.battery > 0.20:
            # 3-Layer Priority Logic: always prefer lower scan count (0 > 1 > 2)
            # Group available targets by priority
            level0_unexplored = []
            level1_partial = []
            level2_almost = []
            
            # We need to rebuild priority lists from current 'unexplored' (which is just coords)
            # But 'unexplored' doesn't store count. So we need to look back at 'needs_more_scans'.
            # Better approach: Filter 'unexplored' based on where they came from?
            # Actually, 'unexplored' was built from 'needs_more_scans' sorted by count.
            # So the first N elements are count 0, then count 1...
            # But calculating split points is hard.
            # Let's just use 'needs_more_scans' directly?
            # No, 'unexplored' tracks which ones are ALREADY taken by other drones in *this* loop? 
            # Wait, 'unexplored' is modified by .remove(nearest).
            
            # Let's iterate 'unexplored' and re-check their count from state grid?
            # Grid access is available via 'state.get("scanned_cells")'. Is it efficient? YES.
            
            # Filter targets by priority level
            # Optimize: We trust 'needs_more_scans' order if we re-used it, but 'unexplored' is just list of tuples.
            # Let's just iterate 'unexplored' and pick the BEST candidate.
            
            # Collect positions of other active drones to avoid clustering
            other_drone_targets = set()
            for other in drones:
                if other.id != drone.id and other.waypoints and len(other.waypoints) > 0:
                    final_wp = other.waypoints[-1]
                    target_cx = int(final_wp[0] // GRID_CELL_SIZE)
                    target_cy = int(final_wp[1] // GRID_CELL_SIZE)
                    for dx in range(-1, 2):  # 1-cell radius
                        for dy in range(-1, 2):
                            other_drone_targets.add((target_cx + dx, target_cy + dy))
            
            # Find available targets not blocked by others
            available_targets = []
            for p in unexplored:
                cx = int(p[0] // GRID_CELL_SIZE)
                cy = int(p[1] // GRID_CELL_SIZE)
                if (cx, cy) not in other_drone_targets:
                    # Find original count from 'needs_more_scans' or grid?
                    # Grid is safer (real-time)
                    # Assume state grid is passed? No, 'scanned_grid' var exists in scope?
                    # Yes, 'scanned_grid' is available from earlier in function.
                    
                    # Get Count
                    count = 0 
                    if isinstance(scanned_grid, list) and len(scanned_grid) > cy and isinstance(scanned_grid[cy], list) and len(scanned_grid[cy]) > cx:
                            cell = scanned_grid[cy][cx]
                            count = cell.get("count", 0) if isinstance(cell, dict) else (3 if cell else 0)
                    
                    available_targets.append((p, count))
            
            # Fallback if all blocked or no targets found in priority filter
            if not available_targets:
                 # DEMO MODE FALLBACK: Just pick ANY unexplored cell
                 if unexplored:
                     # Pick random to look active
                     import random
                     random_target = random.choice(unexplored)
                     available_targets = [(random_target, 99)]
                 else:
                     # Map fully explored? Pick ANY random cell on map to keep moving
                     rx = random.randint(0, GRID_SIZE-1) * GRID_CELL_SIZE + GRID_CELL_SIZE // 2
                     ry = random.randint(0, GRID_SIZE-1) * GRID_CELL_SIZE + GRID_CELL_SIZE // 2
                     available_targets = [((rx, ry), 99)]
            
            if available_targets:
                # Sort candidates: First by Count (ascending), THEN by Distance (ascending)
                # This ensures strict priority: Closest Count-0 > furthest Count-0 > Closest Count-1
                best_target_tuple = min(available_targets, key=lambda item: (
                    item[1], # Primary sort: Count (0 then 1 then 2)
                    math.sqrt((item[0][0] - drone.x)**2 + (item[0][1] - drone.y)**2) # Secondary: Distance
                ))
                
                nearest = best_target_tuple[0]
                if nearest in unexplored:
                    unexplored.remove(nearest)
                
                # Generate A* path
                path = a_star_search(
                    start=(drone.x, drone.y),
                    goal=(nearest[0], nearest[1]),
                    grid_size=GRID_SIZE,
                    cell_size=GRID_CELL_SIZE
                )
                
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
                    waypoints=path, waypoint_index=1 
                )
                
                updated_drones.append(drone)
                continue
        
        updated_drones.append(drone)
    
    # Log exploration progress
    explored_count = len(fully_scanned)
    total_cells = GRID_SIZE * GRID_SIZE
    progress = (explored_count / total_cells) * 100
    logger.info(f"🗺️ Exploration (3-layer): {progress:.1f}% ({explored_count}/{total_cells} cells fully scanned)")
    
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
        # Generate A* path to survivor
        path = a_star_search(
            start=(nearest.x, nearest.y),
            goal=(survivor.x, survivor.y),
            grid_size=GRID_SIZE,
            cell_size=GRID_CELL_SIZE
        )

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
            waypoints=path,
            waypoint_index=1,
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
                target_x=500,
                target_y=500,
                target_z=-10,
                status="active",
            )
            missions.append(mission)
            
            # Generate A* path to base (7500, 7500)
            # Or arguably base is at 500, 500? In create_initial_state base is 500,500.
            # But here target was 7500,7500? That's the center.
            # Let's trust the existing target_x/y (7500,7500) or change to base?
            # Existing code said target_x=7500... maybe it meant center?
            # Let's stick to the target defined in mission.
            
            # Generate A* path to base (500, 500)
            path = a_star_search(
                start=(drone.x, drone.y),
                goal=(500, 500),
                grid_size=GRID_SIZE,
                cell_size=GRID_CELL_SIZE
            )

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
                waypoints=path,
                waypoint_index=1,
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
        
        # Separation Force (Collision Avoidance)
        sep_x, sep_y = 0.0, 0.0
        MIN_DIST = 1500.0  # Safe distance between drones (3 grid cells)
        
        for other in drones:
            if other.id != drone.id:
                dist_sq = (drone.x - other.x)**2 + (drone.y - other.y)**2
                if dist_sq < MIN_DIST**2:
                    if dist_sq == 0:
                        # Perfect overlap! Random repulsion
                        sep_x += random.uniform(-1, 1) * SPEED
                        sep_y += random.uniform(-1, 1) * SPEED
                    else:
                        dist = math.sqrt(dist_sq)
                        # Repulsion vector component
                        # Force is inversely proportional to distance (closer = stronger)
                        strength = (MIN_DIST - dist) / MIN_DIST
                        # Stronger repulsion: 1.5x SPEED at max strength
                        sep_x += ((drone.x - other.x) / dist) * strength * (SPEED * 1.5)
                        sep_y += ((drone.y - other.y) / dist) * strength * (SPEED * 1.5)

        # Check if we have a valid path to follow
        if waypoints and waypoint_index < len(waypoints):
            # Follow the path (A* or Manual)
            target_x, target_y = waypoints[waypoint_index]
            
            dx = target_x - drone.x
            dy = target_y - drone.y
            dist = math.sqrt(dx*dx + dy*dy)
            
            if dist < SPEED:
                # Arrived at waypoint
                new_x, new_y = target_x, target_y
                waypoint_index += 1
                
                # If we reached the end of the path
                if waypoint_index >= len(waypoints):
                    if control_mode == "manual":
                        new_status = "idle"
                    elif current_mission:
                        # Mission complete logic
                        mission = next((m for m in missions if m.id == current_mission), None)
                        if mission:
                            mission.status = "completed"
                            new_status = "scanning" if mission.mission_type == "scan" else "idle"
                            if mission.mission_type == "return":
                                new_status = "idle" # Back to action!
                                new_battery = 1.0   # Instant swap/recharge
                                logger.info(f"🔋 {drone.name} recharged at base")
                            
                            current_mission = None
            else:
                # Move towards waypoint
                new_status = "active" if control_mode == "manual" else drone.status # Keep status if auto (e.g. scanning/returning)
                new_x = drone.x + (dx / dist) * SPEED + sep_x
                new_y = drone.y + (dy / dist) * SPEED + sep_y
             
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
                    new_status = "scanning" if mission.mission_type == "scan" else "idle"
                    if mission.mission_type == "return":
                            new_status = "idle" # Back to action!
                            new_battery = 1.0   # Instant swap/recharge
                            logger.info(f"🔋 {drone.name} recharged at base")
                    current_mission = None
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
    
    # Deduplicate scanned cells
    # Now using 3-layer tracking: each cell stores count of unique drones that scanned it
    # Format: 2D grid where each cell is {"count": 0-3, "drone_ids": []}
    existing_grid = state.get("scanned_cells", [])
    
    # Initialize or get existing grid
    if not existing_grid or not isinstance(existing_grid, list) or len(existing_grid) != GRID_SIZE:
        grid = [[{"count": 0, "drone_ids": []} for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
    elif isinstance(existing_grid[0], tuple) or (isinstance(existing_grid[0], list) and len(existing_grid[0]) == 2 and isinstance(existing_grid[0][0], int)):
        # Old format: list of (x,y) tuples - migrate to new format
        grid = [[{"count": 0, "drone_ids": []} for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        for cell in existing_grid:
            if isinstance(cell, (tuple, list)) and len(cell) == 2:
                cx, cy = cell
                if 0 <= cx < GRID_SIZE and 0 <= cy < GRID_SIZE:
                    grid[cy][cx]["count"] = 3  # Mark as fully scanned if already visited
    else:
        # Already in new format - deep copy
        grid = [[{"count": cell.get("count", 0), "drone_ids": list(cell.get("drone_ids", []))} 
                 for cell in row] for row in existing_grid]
    
    # Update grid with new scanned cells (track unique drone IDs, max 3 layers)
    for drone in updated_drones:
        cell_x = int(drone.x // GRID_CELL_SIZE)
        cell_y = int(drone.y // GRID_CELL_SIZE)
        
        for dx in range(-SCAN_RADIUS, SCAN_RADIUS + 1):
            for dy in range(-SCAN_RADIUS, SCAN_RADIUS + 1):
                cx, cy = cell_x + dx, cell_y + dy
                if 0 <= cx < GRID_SIZE and 0 <= cy < GRID_SIZE:
                    cell = grid[cy][cx]
                    # Only add if this drone hasn't scanned this cell and count < 3
                    if drone.id not in cell["drone_ids"] and cell["count"] < 3:
                        cell["drone_ids"].append(drone.id)
                        cell["count"] += 1
    
    return {
        "drones": updated_drones,
        "scanned_cells": grid,
    }


def simulate_detections(state: DroneFleetState) -> dict:
    """Simulate thermal detections from scanning drones."""
    drones = state["drones"]
    new_survivors = []
    alerts = []
    
    for drone in drones:
        if drone.status == "scanning":

            # 0.5% chance of detection per tick (reduced from 12% to prevent overflow)
            if random.random() < 0.005:
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
    
    # Merge with existing survivors
    all_survivors = list(state["survivors_detected"])
    all_survivors.extend(new_survivors)
    
    # MEMORY CLEANUP: Remove rescued survivors to prevent memory leak
    # Keep only: unrescued survivors + last 10 rescued (for UI display)
    unrescued = [s for s in all_survivors if not s.rescued]
    rescued = [s for s in all_survivors if s.rescued]
    all_survivors = unrescued + rescued[-10:]  # Keep only last 10 rescued
    
    # Also limit total survivors to prevent runaway growth
    if len(all_survivors) > 50:
        all_survivors = all_survivors[-50:]  # Keep most recent 50
    
    return {
        "survivors_detected": all_survivors,
        "alerts": alerts,
    }


def should_continue(state: DroneFleetState) -> Literal["continue", "end"]:
    """Check if we should continue the simulation."""
    # Run forever (no tick limit)
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
    graph.add_node("update_positions", update_positions)
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

    # Emit initial state (drones + heat signatures)
    await emit_callback("drone_update", {
        "drones": [d.to_dict() for d in state["drones"]],
        "heat_signatures": [h.to_dict() for h in state["heat_signatures"]]
    })
    
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
                    
                    # Emit scanned cells for fog of war (3-layer grid)
                    if "scanned_cells" in node_output and node_output["scanned_cells"]:
                        # Send full grid with count per cell for 3-layer visualization
                        await emit_callback("scan_update", {
                            "grid": node_output["scanned_cells"]
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
