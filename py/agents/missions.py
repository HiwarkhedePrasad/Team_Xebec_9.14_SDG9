
import logging
import random
import math
import uuid
from typing import List, Dict, Any, Set

from .state import DroneFleetState, DroneInfo, Mission, Alert, CommRelay
from .pathfinding import a_star_search

logger = logging.getLogger(__name__)

# Constants (duplicated for now or need a config file. Ideally from a config module)
GRID_CELL_SIZE = 500
GRID_SIZE = 30

def dispatch_relay_missions(state: DroneFleetState) -> dict:
    """Dispatch drones to deploy network relays at edge of coverage."""
    drones = list(state["drones"])
    missions = list(state["missions"])
    comm_relays = state.get("comm_relays", [])
    alerts = []
    
    # 1. Identify Network Gaps
    # We want to place relays that overlap with at least one existing relay but extend range.
    # Simple heuristic: Find "frontier" - scanned areas not covered by any relay.
    
    # Current Coverage Map (simplified check)
    def is_covered(x, y):
        for r in comm_relays:
            if r.status == "active":
                dist = math.sqrt((x - r.x)**2 + (y - r.y)**2)
                if dist < r.radius * 0.9: # 90% radius effectively covered
                    return True
        return False
        
    candidates = []
    scanned_grid = state.get("scanned_cells")
    
    # Check every 4th cell to save perf (2000px step?)
    # Ideally we find a point ~radius away from existing relay
    
    # Better approach: For each existing relay, check 4 points at distance R in cardinal directions
    # If point is VALID (in map) and SCANNED and NOT COVERED, it's a candidate.
    
    expansion_distance = 2000 # 4 grid cells
    
    potential_points = []
    for r in comm_relays:
        if r.status == "active":
            # Check N, S, E, W
            offsets = [(0, expansion_distance), (0, -expansion_distance), 
                       (expansion_distance, 0), (-expansion_distance, 0)]
            
            for dx, dy in offsets:
                tx, ty = r.x + dx, r.y + dy
                
                # Check bounds
                if 0 <= tx < GRID_SIZE * GRID_CELL_SIZE and 0 <= ty < GRID_SIZE * GRID_CELL_SIZE:
                    potential_points.append((tx, ty))
                    
    # Filter candidates
    valid_candidates = []
    for px, py in potential_points:
        # Must NOT be covered already
        if is_covered(px, py):
            continue
            
        # Must be SCANNED (drones don't fly into unknown to deploy blindly - safely)
        # Or maybe they DO? Let's say they must have visited (Level > 0)
        cx, cy = int(px // GRID_CELL_SIZE), int(py // GRID_CELL_SIZE)
        if 0 <= cx < GRID_SIZE and 0 <= cy < GRID_SIZE and len(scanned_grid[cy][cx]) > 0:
             # Check if we already have a mission for this area
             has_mission = False
             for m in missions:
                 if m.status == "active" and m.mission_type == "deploy_relay":
                     mdist = math.sqrt((m.target_x - px)**2 + (m.target_y - py)**2)
                     if mdist < 1000: # Don't duplicate missions close by
                         has_mission = True
                         break
             
             if not has_mission:
                 valid_candidates.append((px, py))
    
    # Assign logic
    # Only HEAVY drones can deploy relays
    available_drones = [d for d in drones if d.status == "idle" and d.control_mode == "auto" and d.battery > 0.4 and d.type == "heavy"]
    
    updated_drones = []
    assigned_ids = set()
    
    for candidate in valid_candidates:
        if not available_drones:
            break
            
        drone = available_drones.pop(0)
        
        mission = Mission(
            id=f"deploy_{uuid.uuid4().hex[:6]}",
            drone_id=drone.id,
            mission_type="deploy_relay",
            target_x=candidate[0],
            target_y=candidate[1],
            target_z=-20,
            status="active"
        )
        missions.append(mission)
        
        # Update drone state immediately to prevent re-assignment in scan loop
        drone = DroneInfo(
            id=drone.id, name=drone.name,
            x=drone.x, y=drone.y, z=drone.z,
            status="deploying", # Special status? Or just "scanning" with mission type?
            # Let's keep status "scanning" or "working" to block other tasks
            battery=drone.battery,
            current_mission=mission.id,
            control_mode=drone.control_mode,
            waypoints=[], # Will be calc'd in update_positions or here?
            waypoint_index=0,
            type=drone.type
        )
        # Generate path now
        path = a_star_search((drone.x, drone.y), (candidate[0], candidate[1]), GRID_SIZE, GRID_CELL_SIZE)
        drone.waypoints = path
        # Safety: start from index 1 if path has 2+ waypoints, else 0
        drone.waypoint_index = 1 if len(path) > 1 else 0
        
        updated_drones.append(drone)
        assigned_ids.add(drone.id)
        
        logger.info(f"📶 {drone.name} → deploy relay at ({candidate[0]}, {candidate[1]})")

    # Pass through other drones unaffected
    for d in drones:
        if d.id not in assigned_ids:
            updated_drones.append(d)
            
    return {"drones": updated_drones, "missions": missions}

def dispatch_scan_missions(state: DroneFleetState) -> dict:
    """Assign scanning missions to idle drones - target unexplored areas."""
    drones = list(state["drones"])
    missions = list(state["missions"])
    alerts = []
    # Calculate available cells to scan from GRID
    scanned_grid = state.get("scanned_cells")
    if not scanned_grid or isinstance(scanned_grid, list) and not isinstance(scanned_grid[0], list):
         # Legacy or empty fallback
         scanned_grid = [[[] for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]

    level0_unexplored = [] # Never visited (0)
    level1_partial = []    # Visited once (1)
    level2_almost = []     # Visited twice (2)
    # Level 3 is fully cleared, we only patrol those if everything else is done.
    
    all_scanned_coords = []

    for cx in range(GRID_SIZE):
        for cy in range(GRID_SIZE):
            val = len(scanned_grid[cy][cx]) # Value is number of unique visits
            
            # Common coordinate calc
            world_x = cx * GRID_CELL_SIZE + GRID_CELL_SIZE // 2
            world_y = cy * GRID_CELL_SIZE + GRID_CELL_SIZE // 2
            coord = (world_x, world_y)
            
            if val == 0:
                level0_unexplored.append(coord)
            elif val == 1:
                level1_partial.append(coord)
            elif val == 2:
                level2_almost.append(coord)
            else:
                pass # Level 3+ (Fully Cleared)
            
            if val > 0:
                all_scanned_coords.append((cx, cy))

    # Priority Targeting System
    targets = []
    
    if level0_unexplored:
        # Priority 1: Explore the unknown
        targets = level0_unexplored
    elif level1_partial:
        # Priority 2: Improve visibility (Level 1 -> 2)
        targets = level1_partial
    elif level2_almost:
        # Priority 3: Clear the map (Level 2 -> 3)
        targets = level2_almost
    else:
        # Priority 4: Patrol fully cleared map (Random 15%)
        # Convert (cx, cy) back to world for patrol
        if all_scanned_coords:
             num_rescan = max(1, int(len(all_scanned_coords) * 0.15))
             rescan_grid = random.sample(all_scanned_coords, num_rescan)
             targets = []
             for cx, cy in rescan_grid:
                 wx = cx * GRID_CELL_SIZE + GRID_CELL_SIZE // 2
                 wy = cy * GRID_CELL_SIZE + GRID_CELL_SIZE // 2
                 targets.append((wx, wy))

    # Renaming for compatibility with rest of function
    unexplored = targets

    if not unexplored:
        # Should rarely happen with re-scan logic
        return {"drones": drones, "missions": missions, "alerts": alerts}
    
    # Shuffle unexplored to distribute drones
    random.shuffle(unexplored)
    
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
                    waypoints=drone.waypoints, waypoint_index=drone.waypoint_index,
                    type=drone.type
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
                waypoints=drone.waypoints, waypoint_index=drone.waypoint_index,
                type=drone.type
            )
        
        # Assign idle drones to unexplored areas
        if drone.status == "idle" and drone.control_mode == "auto" and unexplored and drone.battery > 0.20 and drone.type == "scout":
            
            # --- Dispersion Logic ---
            # Calculate cost for each target: Distance + Clustering Penalty
            # Drones will prefer targets that are close to them BUT far from other drones/missions.
            
            # Gather targets of current active missions to avoid clumping
            active_targets = []
            for m in missions:
                if m.status == "active" and m.mission_type == "scan":
                    active_targets.append((m.target_x, m.target_y))
            
            # Add targets assigned IN THIS TICK
            active_targets.extend(assigned_this_tick)
            
            def calculate_score(target_pos):
                tx, ty = target_pos
                
                # 1. Base Cost: Distance to drone (Greedy)
                dist = math.sqrt((tx - drone.x)**2 + (ty - drone.y)**2)
                
                # 2. Penalty: Proximity to OTHER active targets
                penalty = 0
                for ax, ay in active_targets:
                    d_sq = (tx - ax)**2 + (ty - ay)**2
                    if d_sq < 1: d_sq = 1
                    # Inverse square law repulsion: Strong push if very close
                    # Heuristic: 5000^2 / d_sq
                    # If dist is 0 (same cell) -> Huge penalty
                    # If dist is 500 (1 cell) -> Moderate penalty
                    # If dist is 5000 (10 cells) -> Tiny penalty
                    penalty += (20000000 / d_sq) 

                return dist + penalty

            # Find target with lowest score
            # Optimization: Only check a random subset if unexplored is huge (>100)
            candidate_pool = unexplored
            if len(unexplored) > 50:
                 # Check nearest 20 + random 30?
                 # Simple random sample to keep speed up
                 candidate_pool = random.sample(unexplored, 50)

            nearest = min(candidate_pool, key=calculate_score)
            
            unexplored.remove(nearest)
            assigned_this_tick.add(nearest)
            
            # Generate A* path
            path = a_star_search(
                start=(drone.x, drone.y),
                goal=(nearest[0], nearest[1]),
                grid_size=GRID_SIZE,
                cell_size=GRID_CELL_SIZE
            )
            
            # Safety check: ensure we have a valid waypoint index
            # If path has 2+ waypoints, start from index 1 (skip start pos)
            # If path has only 1 waypoint, start from index 0
            start_waypoint_idx = 1 if len(path) > 1 else 0
            
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
                waypoints=path, waypoint_index=start_waypoint_idx,
                type=drone.type
            )
            
            logger.info(f"📡 {drone.name} → explore ({nearest[0]}, {nearest[1]}) via A* (Path len: {len(path)})")
        
        updated_drones.append(drone)
    
    # Log exploration progress
    explored_count = len(all_scanned_coords)
    total_cells = GRID_SIZE * GRID_SIZE
    progress = (explored_count / total_cells) * 100
    if random.random() < 0.1: # Reduce logs
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
        # Generate A* path to survivor
        path = a_star_search(
            start=(nearest.x, nearest.y),
            goal=(survivor.x, survivor.y),
            grid_size=GRID_SIZE,
            cell_size=GRID_CELL_SIZE
        )
        
        # Safety: start from index 1 if path has 2+ waypoints, else 0
        start_waypoint_idx = 1 if len(path) > 1 else 0

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
            waypoint_index=start_waypoint_idx,
            type=nearest.type
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
            
            # Generate A* path to base (500, 500)
            path = a_star_search(
                start=(drone.x, drone.y),
                goal=(500, 500),
                grid_size=GRID_SIZE,
                cell_size=GRID_CELL_SIZE
            )
            
            # Safety: start from index 1 if path has 2+ waypoints, else 0
            start_waypoint_idx = 1 if len(path) > 1 else 0

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
                waypoint_index=start_waypoint_idx,
                type=drone.type
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
