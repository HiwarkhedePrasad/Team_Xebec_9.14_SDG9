import airsim
import time
import numpy as np

# -----------------------------
# 1. CONNECT TO AIRSIM
# -----------------------------
client = airsim.MultirotorClient()
client.confirmConnection()
client.enableApiControl(True)
client.armDisarm(True)

print("[INFO] Connected to AirSim")

# -----------------------------
# 2. TAKEOFF
# -----------------------------
client.takeoffAsync().join()
client.moveToZAsync(-10, 2).join()  # fly to 10m altitude
print("[INFO] Takeoff complete")

# -----------------------------
# 3. AI POLICY (REPLACE THIS)
# -----------------------------
def ai_policy(state):
    """
    AI decision function.
    Input: state (dict)
    Output: vx, vy, vz, yaw_rate
    """

    # Example: simple patrol logic
    vx = 2.0      # forward
    vy = 0.0      # sideways
    vz = 0.0      # vertical
    yaw_rate = 10 # degrees/sec

    return vx, vy, vz, yaw_rate


# -----------------------------
# 4. CONTROL LOOP
# -----------------------------
try:
    while True:
        # Get drone state
        kinematics = client.getMultirotorState().kinematics_estimated
        position = kinematics.position
        velocity = kinematics.linear_velocity

        state = {
            "position": np.array([position.x_val, position.y_val, position.z_val]),
            "velocity": np.array([velocity.x_val, velocity.y_val, velocity.z_val])
        }

        # AI decision
        vx, vy, vz, yaw_rate = ai_policy(state)

        # Send control command
        client.moveByVelocityAsync(
            vx,
            vy,
            vz,
            duration=0.2,
            yaw_mode=airsim.YawMode(is_rate=True, yaw_or_rate=yaw_rate)
        )

        time.sleep(0.2)

except KeyboardInterrupt:
    print("[INFO] Landing...")

finally:
    # -----------------------------
    # 5. SAFE SHUTDOWN
    # -----------------------------
    client.hoverAsync().join()
    client.landAsync().join()
    client.armDisarm(False)
    client.enableApiControl(False)
    print("[INFO] Disconnected safely")
