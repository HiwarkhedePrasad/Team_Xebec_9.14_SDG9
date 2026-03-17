# 🚁 Drone Fleet Coordinator - AI-Powered Disaster Response System

**Team Xebec 9.14 | SDG9 Innovation Project**

---

## 📋 Project Overview

The Drone Fleet Coordinator is an advanced AI-powered disaster response system designed to autonomously coordinate a swarm of drones for search and rescue operations in disaster-affected areas. This system addresses United Nations Sustainable Development Goal 9 (SDG9) by demonstrating innovative infrastructure for resilient disaster response.

### Mission Statement

To provide rapid, intelligent, and coordinated aerial reconnaissance during disaster scenarios, enabling efficient detection of survivors through thermal imaging and autonomous fleet management, ultimately reducing response times and saving lives in crisis situations.

---

## 🎯 Key Features

### Intelligent Fleet Coordination
- **Autonomous Swarm Intelligence**: Ten drones operate as a coordinated swarm using LangGraph-based AI agents for intelligent decision-making and mission assignment
- **Dynamic Task Allocation**: Real-time assignment of scanning, investigation, and rescue missions based on drone proximity, battery levels, and current operational status
- **Collision Avoidance**: Built-in separation force algorithms ensure safe inter-drone distances during operations

### Advanced Mapping & Navigation
- **A* Pathfinding**: Efficient pathfinding algorithm enables optimal route planning across the disaster zone
- **3-Layer Redundant Scanning**: The map is divided into a 30×30 grid where each cell is scanned by up to three different drones, ensuring comprehensive coverage and verification
- **Fog of War Visualization**: Real-time visualization of explored vs. unexplored territories with progressive reveal as drones scan new areas

### Survivor Detection System
- **Thermal Signature Detection**: Simulated thermal imaging detects heat signatures representing potential survivors
- **Confidence-Based Priority**: Detection confidence scores help prioritize rescue operations for high-probability survivors
- **Automated Rescue Dispatch**: When high-confidence survivors are detected, the nearest available drone is automatically dispatched for rescue

### Command & Control Interface
- **Real-Time Dashboard**: Professional command center interface showing fleet status, survivor locations, and operational alerts
- **Manual Override Capability**: Operators can take manual control of any drone and set custom waypoints
- **Multi-View Interface**: Three integrated views - Live Map, Rescue Dashboard, and Command Center

### Fleet Management
- **Battery Monitoring**: Real-time battery tracking with automatic Return-to-Home (RTH) when levels fall below 25%
- **Auto-Recharge Simulation**: Drones return to base station for instant battery swap and return to operations
- **Status Tracking**: Live status indicators (idle, scanning, responding, returning) for situational awareness

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND LAYER                            │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  React + Vite Application (Command Center Interface)        │ │
│  │  ├── MapCanvas - Interactive terrain visualization          │ │
│  │  ├── RescueDashboard - Survivor tracking & fleet status     │ │
│  │  └── CommandCenter - Manual drone control interface         │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                           ↕ Socket.IO                            │
├─────────────────────────────────────────────────────────────────┤
│                        BACKEND LAYER                             │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  FastAPI + Socket.IO Server                                 │ │
│  │  ├── REST API endpoints for map data & health checks        │ │
│  │  └── WebSocket real-time communication layer                │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                           ↕ State                                │
├─────────────────────────────────────────────────────────────────┤
│                         AI LAYER                                 │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  LangGraph Agent System                                     │ │
│  │  ├── analyze_situation - Situation assessment node          │ │
│  │  ├── dispatch_scan_missions - Mission assignment node       │ │
│  │  ├── respond_to_survivors - Rescue coordination node        │ │
│  │  ├── coordinate_fleet - Battery management node             │ │
│  │  ├── update_positions - Movement simulation node            │ │
│  │  └── simulate_detections - Detection simulation node        │ │
│  └─────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                      FIRMWARE LAYER                              │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Arduino/ESP32 Drone Firmware                               │ │
│  │  ├── WiFi connectivity to base station                      │ │
│  │  ├── Socket.IO client for command reception                 │ │
│  │  └── Quad-X motor control with PWM mixing                   │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
hiwarkhedeprasad-team_xebec_9.14_sdg9/
│
├── firmware/
│   └── drone_firmware.ino      # Arduino firmware for physical drones
│
├── forntend/                    # React frontend application
│   ├── src/
│   │   ├── App.jsx             # Main application with state management
│   │   ├── MapCanvas.jsx       # Canvas-based map visualization
│   │   ├── RescueDashboard.jsx # Survivor tracking interface
│   │   ├── CommandCenter.jsx   # Manual drone control panel
│   │   └── App.css             # Professional styling
│   ├── package.json            # Dependencies configuration
│   └── vite.config.js          # Build configuration
│
└── py/                          # Python backend
    ├── main.py                 # FastAPI + Socket.IO server
    ├── drone_client.py         # Physical drone client script
    ├── mapgeneration.py        # Procedural terrain generation
    ├── rgb_server.py           # Camera feed receiver
    ├── scan_mission.py         # AirSim integration
    ├── requirements.txt        # Python dependencies
    └── agents/
        ├── __init__.py         # Module exports
        ├── graph.py            # LangGraph agent definition
        ├── state.py            # TypedDict state definitions
        ├── tools.py            # LangChain tools
        ├── pathfinding.py      # A* pathfinding algorithm
        ├── missions.py         # Mission dispatch logic
        ├── movement.py         # Position update logic
        └── simulation.py       # Detection simulation
```

---

## 🔧 Technology Stack

### Frontend Technologies
| Technology | Purpose |
|------------|---------|
| React 19.2 | UI framework for component-based interface |
| Vite 7.2 | Fast build tool and development server |
| Socket.IO Client 4.8 | Real-time bidirectional communication |
| RoughJS 4.6 | Sketch-style graphics rendering |
| React Spring 10.0 | Animation library for smooth transitions |

### Backend Technologies
| Technology | Purpose |
|------------|---------|
| Python 3.x | Core programming language |
| FastAPI | High-performance async web framework |
| Socket.IO (python-socketio) | WebSocket server implementation |
| LangGraph | State machine for AI agent orchestration |
| LangChain Core | Tool definitions and agent primitives |
| NumPy | Numerical computations for map generation |
| Noise | Perlin noise for procedural terrain |

### Firmware Technologies
| Technology | Purpose |
|------------|---------|
| Arduino ESP32 | Microcontroller platform |
| Socket.IO Client | Real-time command reception |
| ArduinoJson | JSON parsing for commands |

---

## 🧠 AI Agent Architecture

The LangGraph-based AI agent operates as a state machine with the following workflow:

### Agent Nodes

1. **Analyze Situation Node**
   - Evaluates current fleet status
   - Identifies idle drones ready for assignment
   - Detects low-battery conditions
   - Determines next action priority

2. **Dispatch Scan Missions Node**
   - Identifies unexplored or under-scanned grid cells
   - Implements 3-layer priority: Level 0 (unexplored) → Level 1 → Level 2
   - Calculates optimal target assignments using distance and clustering penalties
   - Generates A* paths to targets

3. **Respond to Survivors Node**
   - Filters high-confidence survivor detections (>80%)
   - Finds nearest available drone
   - Creates rescue mission with path planning
   - Updates survivor status to "being rescued"

4. **Coordinate Fleet Node**
   - Monitors battery levels across all drones
   - Triggers Return-to-Home for drones below 25% battery
   - Generates return paths to base station
   - Manages auto-recharge cycle

5. **Update Positions Node**
   - Simulates drone movement along waypoints
   - Applies collision avoidance separation forces
   - Updates scanned cell coverage grid
   - Manages mission completion detection

6. **Simulate Detections Node**
   - Generates random thermal detections during scanning
   - Creates survivor location data with confidence scores
   - Emits real-time alerts to frontend

### State Flow Diagram

```
┌─────────────┐
│   analyze   │ ◄─────────────────────────┐
└──────┬──────┘                           │
       │                                  │
       ▼                                  │
┌──────────────┐                          │
│ route_action │                          │
└──────┬───────┘                          │
       │                                  │
       ├──► dispatch_scan ────┐           │
       │                      │           │
       ├──► respond_survivors ┼──► update │
       │                      │   positions│
       └──► coordinate_fleet ─┘      │    │
                                      │    │
                                      ▼    │
                               ┌──────────┐│
                               │ simulate ││
                               └────┬─────┘│
                                    │      │
                                    └──────┘
```

---

## 🗺️ Map & Grid System

### Grid Specifications
- **Grid Size**: 30 × 30 cells
- **Cell Size**: 500 × 500 world units
- **Total Map Area**: 15,000 × 15,000 units
- **Scan Radius**: 2 cells around drone position

### Terrain Types
The procedural terrain generation creates realistic disaster zone topography:
- **Water** (elevation < 0.2): Light blue areas representing flooded zones
- **Grass** (elevation 0.2-0.4): Light green open areas
- **Forest** (elevation 0.4-0.6): Dense green vegetation zones
- **Rock** (elevation 0.6-0.8): Gray mountainous terrain
- **Snow** (elevation > 0.8): White peak areas

### 3-Layer Scanning System
Each cell tracks scanning progress through three layers:
- **Layer 0**: Unexplored (no drones have visited)
- **Layer 1**: Partially scanned (1 drone visited)
- **Layer 2**: Mostly scanned (2 drones visited)
- **Layer 3**: Fully verified (3 unique drones scanned)

This redundancy ensures:
- Verification of detections across multiple passes
- Resilience against sensor noise or false positives
- Comprehensive coverage even with drone failures

---

## 🚨 Alert System

The system generates real-time alerts for critical events:

| Alert Type | Description | Priority |
|------------|-------------|----------|
| SURVIVOR_DETECTED | Thermal signature detected by scanning drone | High |
| RESCUE_NEEDED | Drone dispatched to survivor location | High |
| DRONE_LOW_BATTERY | Drone battery below 25%, returning to base | Medium |
| MISSION_COMPLETE | Rescue operation completed successfully | Low |
| SYSTEM | General system notifications | Info |

---

## 🎮 User Interface

### Map View
- **Interactive Terrain Canvas**: Pan and zoom across the disaster zone
- **Layer Toggles**: Show/hide terrain, flood zones, earthquake damage, drones, and fog of war
- **Real-Time Drone Positions**: Animated quadcopter icons with status indicators
- **Heat Signature Visualization**: Red gradient markers for potential survivors
- **Waypoint Path Display**: Dotted lines showing planned routes

### Rescue Dashboard
- **Survivor Cards**: Location, confidence score, and rescue status for each detected survivor
- **Priority Badges**: High/Medium priority indicators based on detection confidence
- **Fleet Status Panel**: Battery levels and operational status for all drones
- **Live Alert Feed**: Real-time stream of system events

### Command Center
- **Drone Selection Grid**: Visual cards for selecting individual drones
- **Mode Toggle**: Switch between autonomous and manual control
- **Waypoint Setting**: Click on map to set custom navigation points
- **Emergency Controls**: Stop/clear path functionality for immediate intervention

---

## 🔌 API Reference

### REST Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service status check |
| `/map` | GET | Retrieve disaster map data |
| `/health` | GET | Health check with agent status |

### Socket.IO Events

#### Client → Server
| Event | Payload | Description |
|-------|---------|-------------|
| `connect` | - | Client connection |
| `reset_simulation` | - | Reset to initial state |
| `manual_command` | `{drone_id, command, mode, waypoints}` | Manual drone control |
| `request_scan` | `{x, y}` | Request area scan |

#### Server → Client
| Event | Payload | Description |
|-------|---------|-------------|
| `map_data` | `[[elevation]]` | Initial terrain data |
| `drone_update` | `{drones, heat_signatures}` | Real-time positions |
| `scan_update` | `{grid}` | Updated fog of war |
| `alert` | `{type, message, payload}` | System alerts |

---

## 🔋 Power Management

### Battery Simulation
- **Initial Charge**: 100% at deployment
- **Drain Rate**: 0.05% per movement tick
- **Critical Threshold**: 25% triggers Return-to-Home
- **Recharge Time**: Instant (simulated battery swap)

### Fleet Efficiency
The coordination algorithm optimizes battery usage by:
- Assigning nearest drone to targets
- Balancing workload across the fleet
- Preventing redundant scanning of completed areas
- Managing return-to-base timing to minimize downtime

---

## 🛡️ Safety Features

### Failsafe Mechanisms
- **Connection Loss Protocol**: Drones land safely if communication is lost
- **Boundary Enforcement**: All positions clamped within map boundaries
- **Collision Prevention**: Separation forces maintain safe inter-drone distances
- **Battery RTH**: Automatic return before critical battery depletion

### Manual Override
Human operators can intervene at any time:
- Take manual control of any drone
- Set custom waypoints for specific routes
- Clear existing paths for immediate stop
- Reset simulation for fresh deployment

---

## 🌐 SDG9 Alignment

This project directly supports United Nations Sustainable Development Goal 9: **Industry, Innovation, and Infrastructure** through:

1. **Resilient Infrastructure**: Developing robust disaster response systems that can operate in challenging environments
2. **Innovation in Emergency Response**: Applying AI and autonomous systems to improve search and rescue operations
3. **Technology Transfer**: Creating open-source solutions adaptable for various disaster scenarios globally
4. **Capacity Building**: Demonstrating how emerging technologies can enhance emergency management capabilities

---

## 👥 Team Information

**Team Xebec 9.14**

A dedicated team of engineers and developers working on innovative solutions for disaster response and humanitarian aid through advanced technology.

---

## 📄 License

This project is developed as part of the SDG9 innovation initiative and is intended for educational and humanitarian purposes.

---

*Built with ❤️ for a more resilient world*
