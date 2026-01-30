import { useEffect, useState, useCallback, useRef } from "react";
import { io } from "socket.io-client";
import MapCanvas from "./MapCanvas";
import RescueDashboard from "./RescueDashboard";
import CommandCenter from "./CommandCenter";
import "./App.css";

// Backend URL - update this if backend is on different port
const BACKEND_URL = "http://localhost:8000";

// Grid constants (must match backend)
const GRID_SIZE = 30;

// Throttle utility for socket updates
function throttle(fn, delay) {
  let last = 0;
  return (...args) => {
    const now = Date.now();
    if (now - last > delay) {
      last = now;
      fn(...args);
    }
  };
}

export default function App() {
  const [map, setMap] = useState(null);
  const [drones, setDrones] = useState([]);
  const [survivors, setSurvivors] = useState([]);
  const [heatSignatures, setHeatSignatures] = useState([]);  // Persistent heat signatures
  const [alerts, setAlerts] = useState([]);
  const [connected, setConnected] = useState(false);
  const [activeTab, setActiveTab] = useState("map");
  const [selectedDroneId, setSelectedDroneId] = useState(null);
  
  // Socket ref
  const socketRef = useRef(null);
  const throttledDroneUpdate = useRef(null);
  
  // Fog of war - track which cells have been scanned
  const [scannedCells, setScannedCells] = useState(() => {
    const grid = Array(GRID_SIZE).fill(null).map(() => Array(GRID_SIZE).fill(false));
    return grid;
  });

  const [layers, setLayers] = useState({
    terrain: true,
    flood: true,
    earthquake: true,
    humans: true,
    drones: true,
    fog: false,  // OFF by default so terrain is visible
  });

  // Socket.IO connection with throttling
  useEffect(() => {
    socketRef.current = io(BACKEND_URL, {
      transports: ["websocket", "polling"],
    });
    const socket = socketRef.current;

    // Create throttled handler (100ms minimum between updates)
    throttledDroneUpdate.current = throttle((data) => {
      if (data.drones) {
        setDrones(data.drones);
      }
      if (data.heat_signatures) {
        setHeatSignatures(data.heat_signatures);
      }
    }, 100);

    socket.on("connect", () => {
      console.log("✓ Connected to Drone Fleet Coordinator");
      setConnected(true);
      
      // Clear all state for fresh start
      setDrones([]);
      setSurvivors([]);
      setAlerts([]);
      setHeatSignatures([]);
      setScannedCells(
        Array(GRID_SIZE).fill(null).map(() => Array(GRID_SIZE).fill(false))
      );
    });

    socket.on("disconnect", () => {
      console.log("✗ Disconnected from server");
      setConnected(false);
    });

    // Receive drone position updates (throttled)
    socket.on("drone_update", (data) => {
      if (throttledDroneUpdate.current) {
        throttledDroneUpdate.current(data);
      }
    });

    // Receive scanned cells for fog of war
    socket.on("scan_update", (data) => {
      if (data.cells && data.cells.length > 0) {
        setScannedCells((prev) => {
          const newGrid = prev.map(row => [...row]);
          for (const [x, y] of data.cells) {
            if (x >= 0 && x < GRID_SIZE && y >= 0 && y < GRID_SIZE) {
              newGrid[y][x] = true;
            }
          }
          return newGrid;
        });
      }
    });

    // Receive alerts (survivor detected, rescue, etc.)
    socket.on("alert", (data) => {
      console.log("🚨 Alert:", data);
      setAlerts((prev) => [...prev.slice(-19), data]); // Keep last 20 alerts
      
      // If survivor detected, add to survivors list
      if (data.type === "SURVIVOR_DETECTED" && data.payload) {
        setSurvivors((prev) => {
          // Check if already exists
          if (prev.find(s => s.id === data.payload.id)) return prev;
          return [...prev, data.payload];
        });
      }
      
      // If rescue dispatched, update survivor status
      if (data.type === "RESCUE_NEEDED" && data.payload?.survivor_id) {
        setSurvivors((prev) => prev.map(s => 
          s.id === data.payload.survivor_id 
            ? { ...s, rescued: true, rescue_drone: data.payload.drone_id }
            : s
        ));
      }
    });

    // Receive initial map data
    socket.on("map_data", (data) => {
      console.log("🗺️ Map data received");
      if (data && data.length > 0) {
        setMap(data);
      }
    });

    return () => {
      socket.disconnect();
    };
  }, []);

  // Command Center Handlers
  const handleSelectDrone = (id) => {
    setSelectedDroneId(id);
  };

  const handleSetMode = (droneId, mode) => {
    if (socketRef.current) {
      socketRef.current.emit("manual_command", {
        drone_id: droneId,
        command: "set_mode",
        mode: mode
      });
      console.log(`Sent command: Set ${droneId} to ${mode}`);
    }
  };

  const handleClearPath = (droneId) => {
    if (socketRef.current) {
      socketRef.current.emit("manual_command", {
        drone_id: droneId,
        command: "set_waypoints",
        waypoints: [] // Empty waypoints clears path
      });
    }
  };

  const handleMapClick = (x, y) => {
    if (activeTab === "command" && selectedDroneId) {
      const drone = drones.find(d => d.id === selectedDroneId);
      if (drone && (drone.control_mode === 'manual' || !drone.control_mode)) { // Default to auto, but if setting path implies manual intent? Backend handles mode switch if waypoints sent.
        // But backend expects "set_mode" or "set_waypoints". If we send waypoints, backend forces manual.
        
        const currentWaypoints = drone.waypoints || [];
        // MapCanvas returns scaled coordinates (0-15000), backend expects same.
        // No need to scale here if MapCanvas handles it. MapCanvas will return raw map coords.
        const newWaypoints = [...currentWaypoints, [x, y]];
        
        if (socketRef.current) {
          socketRef.current.emit("manual_command", {
            drone_id: selectedDroneId,
            command: "set_waypoints",
            waypoints: newWaypoints
          });
        }
      }
    }
  };

  // Load static map data as fallback
  useEffect(() => {
    if (!map) {
      fetch("/map_data.json")
        .then((res) => res.json())
        .then(setMap)
        .catch((err) => console.error("Error loading map:", err));
    }
  }, [map]);

  const toggleLayer = (name) => {
    setLayers((prev) => ({ ...prev, [name]: !prev[name] }));
  };

  const dismissAlert = useCallback((index) => {
    setAlerts((prev) => prev.filter((_, i) => i !== index));
  }, []);

  // Calculate scan progress
  const totalCells = GRID_SIZE * GRID_SIZE;
  const exploredCells = scannedCells.flat().filter(Boolean).length;
  const scanProgress = Math.round((exploredCells / totalCells) * 100);

  // Count awaiting rescue
  const awaitingRescue = survivors.filter(s => !s.rescued).length;

  if (!map) return <h3>Loading map data...</h3>;

  return (
    <div>
      {/* Header with tabs */}
      <div className="app-header">
        <h2>
          🌍 Team Xebec - Disaster Response
          <span
            style={{
              marginLeft: "1rem",
              fontSize: "0.8rem",
              color: connected ? "#22c55e" : "#ef4444",
            }}
          >
            {connected ? "● Connected" : "○ Disconnected"}
          </span>
        </h2>
        
        {/* Tab Navigation */}
        <div className="tab-buttons">
          <button 
            className={`tab-btn ${activeTab === "map" ? "active" : ""}`}
            onClick={() => setActiveTab("map")}
          >
            🗺️ Map View
          </button>
          <button 
            className={`tab-btn ${activeTab === "dashboard" ? "active" : ""}`}
            onClick={() => setActiveTab("dashboard")}
          >
            🚨 Dashboard
          </button>
          <button 
            className={`tab-btn ${activeTab === "command" ? "active" : ""}`}
            onClick={() => setActiveTab("command")}
          >
            🎮 Command
          </button>
        </div>
      </div>

      {/* Map View Tab */}
      {activeTab === "map" && (
        <>
          <div className="controls">
            {Object.keys(layers).map((layerName) => (
              <label key={layerName}>
                <input
                  type="checkbox"
                  checked={layers[layerName]}
                  onChange={() => toggleLayer(layerName)}
                />
                <span style={{ textTransform: "capitalize" }}>
                  {layerName === "humans" ? "🏘️ " : ""}
                  {layerName === "terrain" ? "🗺️ " : ""}
                  {layerName === "flood" ? "🌊 " : ""}
                  {layerName === "earthquake" ? "⚡ " : ""}
                  {layerName === "drones" ? "🚁 " : ""}
                  {layerName === "fog" ? "🌫️ " : ""}
                  {layerName}
                </span>
              </label>
            ))}
          </div>

          {/* Alert panel */}
          {alerts.length > 0 && (
            <div className="alerts-panel">
              {alerts.slice(-5).map((alert, i) => (
                <div
                  key={i}
                  className={`alert alert-${alert.type?.toLowerCase() || "info"}`}
                  onClick={() => dismissAlert(i)}
                >
                  <span className="alert-icon">
                    {alert.type === "SURVIVOR_DETECTED" && "🔥"}
                    {alert.type === "RESCUE_NEEDED" && "🚁"}
                    {alert.type === "DRONE_LOW_BATTERY" && "⚠️"}
                    {alert.type === "SYSTEM" && "ℹ️"}
                  </span>
                  <span className="alert-message">{alert.message}</span>
                </div>
              ))}
            </div>
          )}

          <MapCanvas 
            map={map} 
            layers={layers} 
            liveDrones={drones}
            scannedCells={scannedCells}
            survivors={survivors}
            heatSignatures={heatSignatures}
            className="full-screen-map"
          />
        </>
      )}

      {/* Rescue Dashboard Tab */}
      {activeTab === "dashboard" && (
        <RescueDashboard 
          survivors={survivors} 
          drones={drones} 
          alerts={alerts}
        />
      )}

      {activeTab === "command" && (
        <div className="command-layout">
          <div className="command-map">
            <MapCanvas 
              map={map} 
              layers={layers} 
              liveDrones={drones}
              scannedCells={scannedCells}
              survivors={survivors}
              onMapClick={handleMapClick}
              selectedDroneId={selectedDroneId}
            />
          </div>
          <CommandCenter 
            drones={drones}
            selectedDroneId={selectedDroneId}
            onSelectDrone={handleSelectDrone}
            onSetMode={handleSetMode}
            onClearPath={handleClearPath}
          />
        </div>
      )}
    </div>
  );
}
