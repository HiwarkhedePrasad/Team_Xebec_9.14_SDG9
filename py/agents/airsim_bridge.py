"""
AirSim bridge for connecting LangGraph agents to AirSim simulation.
Handles initialization and provides async wrappers for AirSim operations.
"""

import asyncio
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# AirSim client instance
_client = None
_connected = False


def try_connect_airsim() -> bool:
    """
    Attempt to connect to AirSim.
    Returns True if connected, False otherwise.
    """
    global _client, _connected
    
    try:
        import airsim
        _client = airsim.MultirotorClient()
        _client.confirmConnection()
        _connected = True
        logger.info("✓ Connected to AirSim successfully!")
        return True
    except ImportError:
        logger.warning("AirSim package not installed. Running in mock mode.")
        return False
    except Exception as e:
        logger.warning(f"Could not connect to AirSim: {e}. Running in mock mode.")
        return False


def get_client():
    """Get the AirSim client instance."""
    return _client


def is_connected() -> bool:
    """Check if connected to AirSim."""
    return _connected


async def initialize_drones(drone_names: list[str]) -> dict:
    """
    Initialize multiple drones for flight.
    
    Args:
        drone_names: List of drone vehicle names from settings.json
    
    Returns:
        Status of each drone initialization
    """
    if not _connected:
        return {"error": "Not connected to AirSim", "mock_mode": True}
    
    results = {}
    for name in drone_names:
        try:
            _client.enableApiControl(True, vehicle_name=name)
            _client.armDisarm(True, vehicle_name=name)
            await asyncio.to_thread(_client.takeoffAsync(vehicle_name=name).join)
            results[name] = "ready"
        except Exception as e:
            results[name] = f"error: {e}"
    
    return results


async def move_drone(drone_name: str, x: float, y: float, z: float, velocity: float = 5) -> bool:
    """
    Move a drone to a position asynchronously.
    
    Args:
        drone_name: Vehicle name
        x, y, z: Target position (NED coordinates)  
        velocity: Movement speed in m/s
    
    Returns:
        True if command sent successfully
    """
    if not _connected:
        return False
    
    try:
        await asyncio.to_thread(
            lambda: _client.moveToPositionAsync(x, y, z, velocity, vehicle_name=drone_name).join()
        )
        return True
    except Exception as e:
        logger.error(f"Failed to move drone {drone_name}: {e}")
        return False


async def get_drone_telemetry(drone_name: str) -> dict:
    """
    Get telemetry data from a drone.
    
    Args:
        drone_name: Vehicle name
    
    Returns:
        Dict with position, velocity, and state info
    """
    if not _connected:
        return {"error": "Not connected"}
    
    try:
        state = _client.getMultirotorState(vehicle_name=drone_name)
        pos = state.kinematics_estimated.position
        vel = state.kinematics_estimated.linear_velocity
        
        return {
            "position": {"x": pos.x_val, "y": pos.y_val, "z": pos.z_val},
            "velocity": {"x": vel.x_val, "y": vel.y_val, "z": vel.z_val},
            "landed": state.landed_state == 1,
            "timestamp": state.timestamp
        }
    except Exception as e:
        return {"error": str(e)}


async def get_thermal_image(drone_name: str) -> Optional[bytes]:
    """
    Capture a thermal/infrared image from drone camera.
    
    Args:
        drone_name: Vehicle name
    
    Returns:
        Image bytes or None if failed
    """
    if not _connected:
        return None
    
    try:
        import airsim
        responses = _client.simGetImages([
            airsim.ImageRequest("0", airsim.ImageType.Infrared, False, False)
        ], vehicle_name=drone_name)
        
        if responses and len(responses) > 0:
            return responses[0].image_data_uint8
        return None
    except Exception as e:
        logger.error(f"Failed to get thermal image: {e}")
        return None


async def land_drone(drone_name: str) -> bool:
    """Land a drone safely."""
    if not _connected:
        return False
    
    try:
        await asyncio.to_thread(
            lambda: _client.landAsync(vehicle_name=drone_name).join()
        )
        _client.armDisarm(False, vehicle_name=drone_name)
        return True
    except Exception as e:
        logger.error(f"Failed to land drone {drone_name}: {e}")
        return False
