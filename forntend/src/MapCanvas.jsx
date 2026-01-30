import React, { useRef, useEffect, useCallback, useMemo } from "react";
import rough from "roughjs";
import { useGesture } from "@use-gesture/react";
import { animated, useSpring } from "@react-spring/web";

const MapCanvas = ({ map, layers }) => {
  const canvasRef = useRef(null);
  const roughCanvasRef = useRef(null);
  const animationFrameRef = useRef(null);

  // Spring for smooth pan and zoom - Start more zoomed in and centered
  const [{ x, y, scale }, api] = useSpring(() => ({
    x: window.innerWidth / 2 - (15000 * 0.2) / 2,
    y: window.innerHeight / 2 - (15000 * 0.2) / 2,
    scale: 0.2,
    config: { mass: 1, tension: 280, friction: 60 },
  }));

  // Memoize constants
  const PIXELS_PER_KM = useMemo(() => 3000, []);
  const MAP_SIZE_KM = useMemo(() => 5, []);
  const TOTAL_PIXELS = useMemo(() => PIXELS_PER_KM * MAP_SIZE_KM, [PIXELS_PER_KM, MAP_SIZE_KM]);

  // Memoize drone data
  const drones = useMemo(() => [
    { x: 3000, y: 3000, status: "scanning", label: "D-Alpha" },
    { x: 4500, y: 3500, status: "active", label: "D-Beta" },
    { x: 1500, y: 2000, status: "returning", label: "D-Gamma" },
  ], []);

  // Memoize town data
  const towns = useMemo(() => [
    [1000, 3500, 200],
    [3800, 1200, 180],
    [4200, 2600, 150],
  ], []);

  // Memoize random heat signatures - generated once and persisted until refresh
  const heatSignatures = useMemo(() => {
    const signatures = [];
    const count = 15 + Math.floor(Math.random() * 10); // 15-25 survivors
    for (let i = 0; i < count; i++) {
      signatures.push({
        x: Math.floor(Math.random() * 14000) + 500,
        y: Math.floor(Math.random() * 14000) + 500,
        intensity: 0.6 + Math.random() * 0.4, // 0.6-1.0 intensity
        size: 40 + Math.random() * 60, // 40-100px radius
      });
    }
    return signatures;
  }, []);

  // Excalidraw-style gesture handling
  const bind = useGesture(
    {
      onDrag: ({ offset: [dx, dy], pinching, cancel }) => {
        if (pinching) return cancel();

        // Constrain panning to map boundaries
        const currentScale = scale.get();
        const maxX = 0;
        const minX = window.innerWidth - 15000 * currentScale;
        const maxY = 0;
        const minY = window.innerHeight - 15000 * currentScale;

        const constrainedX = Math.min(maxX, Math.max(minX, dx));
        const constrainedY = Math.min(maxY, Math.max(minY, dy));

        api.start({ x: constrainedX, y: constrainedY, immediate: false });
      },
      onPinch: ({ offset: [d] }) => {
        const newScale = Math.max(0.3, Math.min(5, d));
        api.start({ scale: newScale });
      },
      onWheel: ({ event, delta: [, dy] }) => {
        event.preventDefault();
        const currentScale = scale.get();
        const zoomFactor = dy > 0 ? 0.95 : 1.05;
        const newScale = Math.max(0.3, Math.min(5, currentScale * zoomFactor));

        api.start({ scale: newScale });
      },
    },
    {
      drag: {
        from: () => [x.get(), y.get()],
        pointer: { touch: true },
      },
      pinch: {
        from: () => [scale.get()],
        scaleBounds: { min: 0.3, max: 5 },
        rubberband: true,
      },
      wheel: {
        eventOptions: { passive: false },
      },
    },
  );

  // Control functions
  const handleZoom = useCallback((direction) => {
    const currentScale = scale.get();
    const newScale =
      direction === "in"
        ? Math.min(5, currentScale * 1.3)
        : Math.max(0.3, currentScale / 1.3);
    api.start({ scale: newScale });
  }, [scale, api]);

  const handleReset = useCallback(() => {
    api.start({
      x: window.innerWidth / 2 - (15000 * 0.2) / 2,
      y: window.innerHeight / 2 - (15000 * 0.2) / 2,
      scale: 0.2,
    });
  }, [api]);

  // Optimized terrain drawing function
  const drawTerrain = useCallback((ctx, scaleFactor) => {
    if (!map || map.length === 0) return;

    // Use off-screen canvas for terrain if needed (for very large maps)
    map.forEach((row, r) => {
      row.forEach((val, c) => {
        const x = c * scaleFactor;
        const y = r * scaleFactor;
        const size = scaleFactor + 1;

        // Water (low elevation)
        if (val <= 0.35) {
          const blue = Math.floor(150 + val * 150);
          ctx.fillStyle = `rgb(65, 105, ${blue})`;
          ctx.fillRect(x, y, size, size);
        }
        // Beach/Coast
        else if (val <= 0.42) {
          ctx.fillStyle = `rgb(238, 214, 175)`;
          ctx.fillRect(x, y, size, size);
        }
        // Lowlands (green)
        else if (val <= 0.55) {
          const green = Math.floor(160 + (val - 0.42) * 150);
          ctx.fillStyle = `rgb(85, ${green}, 85)`;
          ctx.fillRect(x, y, size, size);
        }
        // Hills
        else if (val <= 0.7) {
          const earthy = Math.floor(100 + (val - 0.55) * 200);
          ctx.fillStyle = `rgb(${earthy}, ${earthy - 20}, 70)`;
          ctx.fillRect(x, y, size, size);
        }
        // Mountains
        else if (val <= 0.85) {
          const gray = Math.floor(180 - (val - 0.7) * 300);
          ctx.fillStyle = `rgb(${gray}, ${gray}, ${gray + 10})`;
          ctx.fillRect(x, y, size, size);
        }
        // Snow peaks
        else {
          const white = Math.floor(235 + val * 20);
          ctx.fillStyle = `rgb(${white}, ${white}, 255)`;
          ctx.fillRect(x, y, size, size);
        }

        // Add subtle texture/noise (optimized - less frequent)
        if (Math.random() > 0.98) {
          ctx.fillStyle = `rgba(0, 0, 0, 0.05)`;
          ctx.fillRect(x, y, size, size);
        }
      });
    });
  }, [map]);

  // Optimized grid drawing
  const drawGrid = useCallback((ctx) => {
    ctx.beginPath();
    for (let i = 0; i <= TOTAL_PIXELS; i += PIXELS_PER_KM / 5) {
      if (i % PIXELS_PER_KM === 0) {
        ctx.strokeStyle = "rgba(0, 0, 0, 0.2)";
        ctx.lineWidth = 2;
      } else {
        ctx.strokeStyle = "rgba(0, 0, 0, 0.08)";
        ctx.lineWidth = 1;
      }
      ctx.moveTo(i, 0);
      ctx.lineTo(i, TOTAL_PIXELS);
      ctx.moveTo(0, i);
      ctx.lineTo(TOTAL_PIXELS, i);
    }
    ctx.stroke();

    // Coordinate labels
    ctx.fillStyle = "rgba(0, 0, 0, 0.7)";
    ctx.font = "bold 32px sans-serif";
    for (let i = 0; i <= TOTAL_PIXELS; i += PIXELS_PER_KM) {
      if (i > 0) {
        ctx.fillText(`${i / PIXELS_PER_KM}km`, i + 10, 50);
        ctx.fillText(`${i / PIXELS_PER_KM}km`, 10, i + 50);
      }
    }
  }, [TOTAL_PIXELS, PIXELS_PER_KM]);

  // Optimized drawing function with requestAnimationFrame
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    // Initialize rough canvas once
    if (!roughCanvasRef.current) {
      roughCanvasRef.current = rough.canvas(canvas);
    }
    const rc = roughCanvasRef.current;
    const ctx = canvas.getContext("2d", { alpha: false }); // Disable alpha for performance

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw terrain
    if (layers.terrain && map && map.length > 0) {
      const scaleFactor = TOTAL_PIXELS / map.length;
      drawTerrain(ctx, scaleFactor);
    }

    // Draw grid
    drawGrid(ctx);

    // Earthquake layer
    if (layers.earthquake) {
      rc.linearPath(
        [
          [800, 900],
          [1200, 1400],
          [1100, 1900],
          [1600, 2400],
          [1300, 3000],
        ],
        {
          stroke: "#dc2626",
          strokeWidth: 10,
          roughness: 2.5,
        },
      );

      rc.circle(1200, 1400, 300, {
        stroke: "#dc2626",
        strokeWidth: 3,
        roughness: 1.5,
        fill: "rgba(220, 38, 38, 0.1)",
        fillStyle: "cross-hatch",
        hachureGap: 8,
      });
    }

    // Flood zones
    if (layers.flood) {
      rc.polygon(
        [
          [3200, 3300],
          [4600, 3100],
          [4900, 4300],
          [4700, 4900],
          [3100, 4500],
        ],
        {
          fill: "rgba(59, 130, 246, 0.35)",
          fillStyle: "zigzag-line",
          hachureGap: 12,
          roughness: 1.8,
          stroke: "#1e40af",
          strokeWidth: 4,
        },
      );

      rc.polygon(
        [
          [2800, 2900],
          [3300, 2800],
          [3400, 3400],
          [2900, 3500],
        ],
        {
          fill: "rgba(147, 197, 253, 0.25)",
          fillStyle: "hachure",
          hachureGap: 10,
          roughness: 1.5,
          stroke: "#3b82f6",
          strokeWidth: 2,
        },
      );
    }

    // Human settlements
    if (layers.humans) {
      rc.rectangle(2000, 1500, 400, 400, {
        fill: "rgba(75, 85, 99, 0.5)",
        fillStyle: "solid",
        stroke: "#1f2937",
        strokeWidth: 3,
        roughness: 0.5,
      });

      towns.forEach(([tx, ty, size]) => {
        rc.rectangle(tx, ty, size, size, {
          fill: "rgba(107, 114, 128, 0.4)",
          stroke: "#374151",
          strokeWidth: 2,
          roughness: 0.8,
        });
      });

      // Draw heat signatures (survivors)
      heatSignatures.forEach(({ x: hx, y: hy, intensity, size: radius }) => {
        // Thermal bloom effect
        const gradient = ctx.createRadialGradient(hx, hy, 5, hx, hy, radius);
        gradient.addColorStop(0, `rgba(255, 50, 50, ${intensity})`);
        gradient.addColorStop(0.3, `rgba(255, 120, 0, ${intensity * 0.5})`);
        gradient.addColorStop(1, "rgba(255, 100, 0, 0)");

        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(hx, hy, radius, 0, Math.PI * 2);
        ctx.fill();

        // Center point indicator
        ctx.fillStyle = "#ef4444";
        ctx.beginPath();
        ctx.arc(hx, hy, 8, 0, Math.PI * 2);
        ctx.fill();
      });
    }

    // Drones layer
    if (layers.drones) {
      const droneScale = 1;

      drones.forEach((drone) => {
        rc.circle(drone.x, drone.y, 80 * droneScale, {
          fill: "rgba(0, 0, 0, 0.8)",
          stroke: "#000",
          strokeWidth: 2,
          fillStyle: "solid",
        });

        const offset = 60 * droneScale;
        const rotorSizeX = 60 * droneScale;
        const rotorSizeY = 20 * droneScale;
        
        [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(([ox, oy]) => {
          rc.ellipse(
            drone.x + ox * offset,
            drone.y + oy * offset,
            rotorSizeX,
            rotorSizeY,
            { stroke: "#444", strokeWidth: 1 }
          );
        });

        const color =
          drone.status === "active" ? "#22c55e" : 
          drone.status === "scanning" ? "#3b82f6" : "#eab308";
        
        ctx.beginPath();
        ctx.arc(drone.x, drone.y, 15 * droneScale, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();

        if (drone.status === "scanning") {
          rc.circle(drone.x, drone.y, 500 * droneScale, {
            stroke: "rgba(59, 130, 246, 0.6)",
            strokeWidth: 2,
            roughness: 0.5,
            strokeLineDash: [15, 15]
          });
        }
      });
    }
  }, [map, layers, TOTAL_PIXELS, drawTerrain, drawGrid, drones, towns, heatSignatures]);

  // Use requestAnimationFrame for smooth rendering
  useEffect(() => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }
    
    animationFrameRef.current = requestAnimationFrame(() => {
      draw();
    });

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [draw]);

  return (
    <>
      <div
        className="canvas-wrapper"
        {...bind()}
        style={{ touchAction: "none" }}
      >
        <animated.div
          style={{
            transform: "translate3d(0,0,0)",
            x,
            y,
            scale,
            transformOrigin: "0 0",
            willChange: "transform",
          }}
        >
          <canvas ref={canvasRef} width={15000} height={15000} />
        </animated.div>
      </div>

      {/* Excalidraw-style controls */}
      <div className="map-controls">
        <button
          className="control-btn zoom-in"
          onClick={() => handleZoom("in")}
          title="Zoom in (Ctrl + Scroll)"
          aria-label="Zoom in"
        >
          <svg viewBox="0 0 24 24" width="20" height="20">
            <path
              d="M12 5v14M5 12h14"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        </button>

        <button
          className="control-btn zoom-out"
          onClick={() => handleZoom("out")}
          title="Zoom out (Ctrl + Scroll)"
          aria-label="Zoom out"
        >
          <svg viewBox="0 0 24 24" width="20" height="20">
            <path
              d="M5 12h14"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        </button>

        <div className="control-divider"></div>

        <button
          className="control-btn reset"
          onClick={handleReset}
          title="Reset view (Ctrl + 0)"
          aria-label="Reset view"
        >
          <svg viewBox="0 0 24 24" width="20" height="20">
            <path
              d="M12 5v6l4-4-4-4M12 19v-6l-4 4 4 4"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              fill="none"
            />
          </svg>
        </button>

        <div className="zoom-indicator">{Math.round(scale.get() * 100)}%</div>
      </div>
    </>
  );
};

export default MapCanvas;