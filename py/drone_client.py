"""
🚁 DRONE SWARM CLIENT
---------------------
Run this script on your physical drone (Raspberry Pi/Jetson Nano).
It connects to the AI Commander and executes movement orders.

Usage:
    python drone_client.py --id "Drone-1" --server "http://localhost:8000"

Dependencies:
    pip install "python-socketio[client]"
"""

import sys
import time
import argparse
import socketio

# Configure Drone ID
parser = argparse.ArgumentParser()
parser.add_argument("--id", default="Drone-1", help="ID of this drone in the swarm")
parser.add_argument("--server", default="http://localhost:8000", help="URL of AI Commander")
args = parser.parse_args()

DRONE_ID = args.id
SERVER_URL = args.server

# Initialize Socket Client
sio = socketio.Client()

@sio.event
def connect():
    print(f"✅ CONNECTED to Swarm Commander at {SERVER_URL}")
    print(f"waiting for orders for {DRONE_ID}...")

@sio.event
def connect_error(data):
    print(f"❌ Connection failed: {data}")

@sio.event
def disconnect():
    print("⚠️ Disconnected from Commander")

@sio.on("drone_update")
def on_drone_update(data):
    """Receive telemetry updates from the Hive Mind."""
    # The server sends the state of ALL drones. We filter for ours.
    my_drone = next((d for d in data if d["id"] == DRONE_ID), None)
    
    if my_drone:
        status = my_drone["status"]
        battery = my_drone["battery"] * 100
        x, y = my_drone["x"], my_drone["y"]
        
        # Print 'Hardware Execution' logs
        if status == "scanning":
            print(f"🚁 [{DRONE_ID}] MOVING -> Target: ({x:.1f}, {y:.1f}) | Batt: {battery:.0f}%")
        elif status == "responding":
            print(f"🚑 [{DRONE_ID}] RESCUE MISSION! ->  Target: ({x:.1f}, {y:.1f})")
        elif status == "returning":
            print(f"🔋 [{DRONE_ID}] LOW BATTERY - RTH (Return to Home)")
        else:
            print(f"💤 [{DRONE_ID}] Idle...")
    else:
        # If we aren't in the list, maybe the sim hasn't spawned us yet?
        pass

if __name__ == "__main__":
    print(f"🔌 Connecting {DRONE_ID} to Hive Mind...")
    try:
        sio.connect(SERVER_URL)
        sio.wait()
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(1)
