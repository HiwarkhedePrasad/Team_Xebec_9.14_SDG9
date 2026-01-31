
import logging
import random
import uuid
from .state import DroneFleetState, Alert, SurvivorLocation

logger = logging.getLogger(__name__)

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
    
    # Memory cleanup: Keep unrescued + limit rescued survivors to last 20
    unrescued = [s for s in all_survivors if not s.rescued]
    rescued = [s for s in all_survivors if s.rescued]
    all_survivors = unrescued + rescued[-20:]  # Keep all unrescued, limit rescued
    
    return {
        "survivors_detected": all_survivors,
        "alerts": alerts,
    }
