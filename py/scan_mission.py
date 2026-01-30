import airsim
import time

# 1. CONNECT TO UNITY
# (This will wait until you press "Play" in the Unity Editor)
print("Waiting for Unity connection...")
client = airsim.MultirotorClient()
client.confirmConnection()
client.enableApiControl(True)
client.armDisarm(True)

print("Connected! Drone is taking off...")
client.takeoffAsync().join()

# 2. THE SCANNING MISSION
# We will fly in a "Z" pattern to scan the area
altitude = -10  # Negative is UP in AirSim
speed = 5       # m/s

waypoints = [
    airsim.Vector3r(0, 0, altitude),    # Hover at start
    airsim.Vector3r(20, 0, altitude),   # Fly North 20m
    airsim.Vector3r(20, 20, altitude),  # Fly East 20m
    airsim.Vector3r(0, 20, altitude),   # Fly South 20m
    airsim.Vector3r(0, 0, altitude)     # Return Home
]

for point in waypoints:
    print(f"Moving to: {point.x_val}, {point.y_val}")
    # movetoPositionAsync(x, y, z, velocity)
    client.moveToPositionAsync(point.x_val, point.y_val, point.z_val, speed).join()
    time.sleep(1)

# 3. MISSION COMPLETE
print("Mission complete. Landing...")
client.landAsync().join()
client.armDisarm(False)
client.enableApiControl(False)