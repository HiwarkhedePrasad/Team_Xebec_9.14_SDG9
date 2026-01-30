import airsim
import time

print("Attempting connection...")
client = airsim.MultirotorClient()

# Add timeout and better error handling
try:
    client.confirmConnection()
    print("✓ Connected successfully!")
    print(f"Drone state: {client.getMultirotorState()}")
except Exception as e:
    print(f"✗ Connection failed: {e}")
    print("\nTroubleshooting:")
    print("1. Is Unity running and in Play mode?")
    print("2. Check Unity Console for AirSim API messages")
    print("3. Verify settings.json exists in Documents/AirSim/")