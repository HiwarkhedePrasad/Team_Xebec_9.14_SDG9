import React, { useRef, useEffect, useCallback, useMemo, useState } from "react";

// Simple, lightweight map canvas - no fancy effects
const CANVAS_SIZE = 2000;
const GRID_SIZE = 30;

const MapCanvas = ({ 
  map, 
  layers, 
  liveDrones = [], 
  scannedCells = null, 
  survivors = [], 
  heatSignatures = [], // Received from parent
  onMapClick, 
  selectedDroneId,
  style = {}, // Allow custom styles
  className = "" 
}) => {
  const canvasRef = useRef(null);
  const containerRef = useRef(null); // Ref for the outer div
  const animationRef = useRef(null);
  const dronePositions = useRef({});
  const [viewOffset, setViewOffset] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(0.8);
  const isDragging = useRef(false);
  const lastMouse = useRef({ x: 0, y: 0 });

  // Memoize terrain colors
  const getTerrainColor = useCallback((elevation) => {
    if (elevation < 0.2) return "#7dd3fc";  // water
    if (elevation < 0.4) return "#86efac";  // grass
    if (elevation < 0.6) return "#4ade80";  // forest
    if (elevation < 0.8) return "#a3a3a3";  // rock
    return "#e5e5e5";  // snow
  }, []);

  // Handle click on map for manual waypoints
  const handleCanvasClick = (e) => {
    if (!onMapClick || isDragging.current) return;
    
    // Check if it was a drag (offset check)
    if (Math.abs(e.clientX - lastMouse.current.x) > 5 || 
        Math.abs(e.clientY - lastMouse.current.y) > 5) return;

    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    // Inverse transform
    // screen -> view -> world -> backend
    const viewX = (x - viewOffset.x) / zoom;
    const viewY = (y - viewOffset.y) / zoom;
    
    const backendScale = 15000 / CANVAS_SIZE;
    const backendX = viewX * backendScale;
    const backendY = viewY * backendScale;
    
    onMapClick(backendX, backendY);
  };

  // Single draw function
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d", { alpha: false });

    const draw = () => {
      ctx.save();
      ctx.fillStyle = "#f0fdf4";
      ctx.fillRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);

      // Apply view transform
      ctx.translate(viewOffset.x, viewOffset.y);
      ctx.scale(zoom, zoom);

      // Draw terrain (simple)
      if (map && layers.terrain) {
        const tileSize = CANVAS_SIZE / (map.length || 1);
        for (let r = 0; r < map.length; r += 2) {  // Skip every other row for speed
          for (let c = 0; c < (map[0]?.length || 0); c += 2) {
            ctx.fillStyle = getTerrainColor(map[r][c]);
            ctx.fillRect(c * tileSize, r * tileSize, tileSize * 2, tileSize * 2);
          }
        }
      }

      // Draw fog of war
      if (layers.fog && scannedCells) {
        ctx.fillStyle = "rgba(30, 40, 50, 0.7)";
        const cellSize = CANVAS_SIZE / GRID_SIZE;
        for (let y = 0; y < GRID_SIZE; y++) {
          for (let x = 0; x < GRID_SIZE; x++) {
            if (!scannedCells[y]?.[x]) {
              ctx.fillRect(x * cellSize, y * cellSize, cellSize, cellSize);
            }
          }
        }
      }

      // Draw drones (quadcopter shape)
      if (layers.drones) {
        const drones = liveDrones.length > 0 ? liveDrones : [];
        const mapScale = CANVAS_SIZE / 15000;
        
        // Render Heat Signatures (Persistent from Backend)
        // Only if layer is active and area is scanned
        if (layers.humans && heatSignatures) {
           heatSignatures.forEach(sig => {
             // Check visibility
             const sigGridX = Math.floor(sig.x / 500); // 500 is grid cell size
             const sigGridY = Math.floor(sig.y / 500);
             
             // Check if scanned (or if fog is off)
             const isVisible = !layers.fog || (scannedCells && scannedCells[sigGridY] && scannedCells[sigGridY][sigGridX]);
             
             if (isVisible) {
               const sx = sig.x * mapScale;
               const sy = sig.y * mapScale;
               const sSize = sig.size * mapScale;
               
               const gradient = ctx.createRadialGradient(sx, sy, 0, sx, sy, sSize);
               gradient.addColorStop(0, `rgba(255, 100, 50, ${sig.intensity * 0.8})`);
               gradient.addColorStop(1, "rgba(255, 0, 0, 0)");
               
               ctx.fillStyle = gradient;
               ctx.beginPath();
               ctx.arc(sx, sy, sSize, 0, Math.PI * 2);
               ctx.fill();
             }
           });
        }

        drones.forEach((drone) => {
          // Scale position
          const targetX = drone.x * mapScale;
          const targetY = drone.y * mapScale;
          
          // Smooth lerp
          const id = drone.id;
          const pos = dronePositions.current[id] || { x: targetX, y: targetY };
          pos.x += (targetX - pos.x) * 0.08;
          pos.y += (targetY - pos.y) * 0.08;
          dronePositions.current[id] = pos;

          // === Draw Path ===
          if (drone.waypoints && drone.waypoints.length > 0) {
            ctx.beginPath();
            ctx.moveTo(pos.x, pos.y);
            drone.waypoints.forEach(([wx, wy], i) => {
              if (i >= (drone.waypoint_index || 0)) {
                ctx.lineTo(wx * mapScale, wy * mapScale);
              }
            });
            ctx.strokeStyle = drone.id === selectedDroneId ? "#facc15" : "rgba(255, 255, 255, 0.4)";
            ctx.lineWidth = drone.id === selectedDroneId ? 3 : 1;
            ctx.setLineDash([5, 5]);
            ctx.stroke();
            ctx.setLineDash([]);
            
            // Draw waypoint dots
             drone.waypoints.forEach(([wx, wy], i) => {
              if (i >= (drone.waypoint_index || 0)) {
                ctx.beginPath();
                ctx.arc(wx * mapScale, wy * mapScale, 3, 0, Math.PI * 2);
                ctx.fillStyle = drone.id === selectedDroneId ? "#facc15" : "rgba(255, 255, 255, 0.6)";
                ctx.fill();
              }
            });
          }

          const x = pos.x;
          const y = pos.y;
          const size = 12;
          const isSelected = drone.id === selectedDroneId;

          // Status color
          const statusColor = drone.status === "scanning" ? "#3b82f6" : 
                             drone.status === "responding" ? "#22c55e" : "#6b7280";

          // Draw quadcopter body
          ctx.save();
          ctx.translate(x, y);
          
          // Selection Highlight
          if (isSelected) {
            ctx.beginPath();
            ctx.arc(0, 0, 30, 0, Math.PI * 2);
            ctx.strokeStyle = "#facc15";
            ctx.lineWidth = 2;
            ctx.stroke();
          }

          // Arms
          ctx.strokeStyle = "#374151";
          ctx.lineWidth = 3;
          ctx.beginPath();
          ctx.moveTo(-size, -size);
          ctx.lineTo(size, size);
          ctx.moveTo(size, -size);
          ctx.lineTo(-size, size);
          ctx.stroke();

          // Rotors
          const rotorSize = 5;
          ctx.fillStyle = "#1f2937";
          [[-size, -size], [size, -size], [-size, size], [size, size]].forEach(([rx, ry]) => {
            ctx.beginPath();
            ctx.arc(rx, ry, rotorSize, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = "#9ca3af";
            ctx.lineWidth = 1;
            ctx.stroke();
          });

          // Center body
          ctx.beginPath();
          ctx.arc(0, 0, 6, 0, Math.PI * 2);
          ctx.fillStyle = "#111827";
          ctx.fill();

          // Status LED
          ctx.beginPath();
          ctx.arc(0, 0, 3, 0, Math.PI * 2);
          ctx.fillStyle = statusColor;
          ctx.fill();

          ctx.restore();

          // Drone label
          ctx.fillStyle = "#000";
          ctx.font = isSelected ? "bold 11px sans-serif" : "bold 9px sans-serif";
          ctx.textAlign = "center";
          ctx.fillText(drone.name || "Drone", x, y + size + 12);
        });
      }

      // Draw survivors
      survivors.forEach((s) => {
        if (!s.rescued) {
          const scale = CANVAS_SIZE / 15000;
          ctx.beginPath();
          ctx.arc(s.x * scale, s.y * scale, 6, 0, Math.PI * 2);
          ctx.fillStyle = "#ef4444";
          ctx.fill();
        }
      });

      ctx.restore();
      animationRef.current = requestAnimationFrame(draw);
    };

    animationRef.current = requestAnimationFrame(draw);

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [map, layers, liveDrones, scannedCells, survivors, heatSignatures, viewOffset, zoom, getTerrainColor]);

  // Mouse handlers for pan
  const handleMouseDown = (e) => {
    isDragging.current = true;
    lastMouse.current = { x: e.clientX, y: e.clientY };
  };

  const handleMouseMove = (e) => {
    if (!isDragging.current) return;
    const dx = e.clientX - lastMouse.current.x;
    const dy = e.clientY - lastMouse.current.y;
    lastMouse.current = { x: e.clientX, y: e.clientY };
    setViewOffset(prev => ({ x: prev.x + dx, y: prev.y + dy }));
  };

  const handleMouseUp = () => {
    isDragging.current = false;
  };

  // Add non-passive event listener for wheel to prevent browser zoom
  useEffect(() => {
    const canvas = containerRef.current;
    if (!canvas) return;

    const onWheel = (e) => {
      // Prevent browser zoom (ctrl+wheel) and back/forward swipe
      e.preventDefault();
      
      const panSpeed = 1.0;
      setViewOffset(prev => ({ 
        x: prev.x - e.deltaX * panSpeed, 
        y: prev.y - e.deltaY * panSpeed 
      }));
    };

    // Use passive: false to allow preventDefault()
    canvas.addEventListener('wheel', onWheel, { passive: false });

    return () => {
      canvas.removeEventListener('wheel', onWheel);
    };
  }, []);

  return (
    <div 
      ref={containerRef}
      className={className}
      style={{ 
        width: "100%", 
        height: "100%", 
        overflow: "hidden",
        background: "#1e293b",
        position: "relative", // Default to relative to fill parent
        touchAction: "none", // Prevent touch gestures
        ...style 
      }}
    >
      <canvas
        ref={canvasRef}
        width={CANVAS_SIZE}
        height={CANVAS_SIZE}
        style={{
          cursor: isDragging.current ? "grabbing" : "grab",
          // Removed fixed marginTop
        }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onClick={handleCanvasClick}
      />
      
      {/* Simple zoom controls */}
      <div style={{
        position: "absolute",
        bottom: 20,
        right: 20,
        display: "flex",
        gap: 8,
        background: "white",
        padding: 8,
        borderRadius: 8,
        boxShadow: "0 2px 8px rgba(0,0,0,0.2)",
      }}>
        <button onClick={() => setZoom(z => Math.min(3, z * 1.2))}>+</button>
        <button onClick={() => setZoom(z => Math.max(0.3, z / 1.2))}>-</button>
        <button onClick={() => { setZoom(0.8); setViewOffset({ x: 0, y: 0 }); }}>Reset</button>
        <span style={{ fontSize: 12, padding: "4px 8px" }}>{Math.round(zoom * 100)}%</span>
      </div>
    </div>
  );
};

export default MapCanvas;