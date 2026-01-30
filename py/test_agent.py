"""Quick test of the drone fleet agent graph."""
from agents.graph import create_drone_fleet_agent, create_initial_state

def test_agent():
    agent = create_drone_fleet_agent()
    state = create_initial_state()
    
    print("Testing agent graph...")
    count = 0
    
    for event in agent.stream(state):
        for node, output in event.items():
            print(f"[{node}] Output keys: {list(output.keys())}")
            
            if "drones" in output:
                drones = output["drones"]
                print(f"  -> {len(drones)} drones")
                
            if "alerts" in output and output["alerts"]:
                for alert in output["alerts"]:
                    print(f"  -> ALERT: {alert.message}")
                    
        count += 1
        if count >= 8:
            print("\n✓ Agent graph working correctly!")
            break

if __name__ == "__main__":
    test_agent()
