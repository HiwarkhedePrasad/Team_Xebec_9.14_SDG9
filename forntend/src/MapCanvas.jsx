import React, { useRef, useEffect } from "react";
import rough from "roughjs";
import { useGesture } from "@use-gesture/react";
import { animated, useSpring } from "@react-spring/web";

const MapCanvas = ({ map, layers }) => {
  const canvasRef = useRef(null);

  // Spring for smooth pan and zoom - Start more zoomed in and centered
  const [{ x, y, scale }, api] = useSpring(() => ({
    x: window.innerWidth / 2 - 17500, // Center the 35000px map
    y: window.innerHeight / 2 - 17500,
    scale: 0.2, // Start zoomed out to see more of the larger map
    config: { mass: 1, tension: 280, friction: 60 },
  }));

  // Excalidraw-style gesture handling
  const bind = useGesture(
    {
      onDrag: ({ offset: [dx, dy], movement: [mx, my], pinching, cancel }) => {
        if (pinching) return cancel();

        // Constrain panning to map boundaries
        const currentScale = scale.get();
        const maxX = 0;
        const minX = window.innerWidth - 35000 * currentScale;
        const maxY = 0;
        const minY = window.innerHeight - 35000 * currentScale;

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

        // Zoom towards cursor position
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
  const handleZoom = (direction) => {
    const currentScale = scale.get();
    const newScale =
      direction === "in"
        ? Math.min(5, currentScale * 1.3) // Allow up to 5x zoom
        : Math.max(0.3, currentScale / 1.3); // Minimum 0.3x zoom
    api.start({ scale: newScale });
  };

  const handleReset = () => {
    api.start({
      x: window.innerWidth / 2 - 17500,
      y: window.innerHeight / 2 - 17500,
      scale: 0.2,
    });
  };

  // Enhanced drawing with realistic terrain
  const draw = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rc = rough.canvas(canvas);
    const ctx = canvas.getContext("2d");

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const PIXELS_PER_KM = 700; // 7 blocks per kilometer
    const MAP_SIZE_KM = 50;
    const TOTAL_PIXELS = PIXELS_PER_KM * MAP_SIZE_KM; // 35000px

    // --- ENHANCED TERRAIN RENDERING ---
    if (layers.terrain && map && map.length > 0) {
      const scaleFactor = TOTAL_PIXELS / map.length;

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

          // Add subtle texture/noise
          if (Math.random() > 0.97) {
            ctx.fillStyle = `rgba(0, 0, 0, 0.05)`;
            ctx.fillRect(x, y, size, size);
          }
        });
      });
    }

    // --- GRID (drawn on top with subtle style) ---
    ctx.strokeStyle = "rgba(0, 0, 0, 0.08)";
    ctx.lineWidth = 0.5;
    ctx.beginPath();
    for (let i = 0; i <= TOTAL_PIXELS; i += PIXELS_PER_KM) {
      if (i % 500 === 0) {
        ctx.strokeStyle = "rgba(0, 0, 0, 0.15)";
        ctx.lineWidth = 1.5;
      } else {
        ctx.strokeStyle = "rgba(0, 0, 0, 0.06)";
        ctx.lineWidth = 0.5;
      }
      ctx.moveTo(i, 0);
      ctx.lineTo(i, TOTAL_PIXELS);
      ctx.moveTo(0, i);
      ctx.lineTo(TOTAL_PIXELS, i);
    }
    ctx.stroke();

    // Coordinate labels
    ctx.fillStyle = "rgba(0, 0, 0, 0.6)";
    ctx.font = "bold 22px sans-serif";
    for (let i = 0; i <= TOTAL_PIXELS; i += 500) {
      ctx.fillText(`${i / 100}km`, i + 10, 35);
      ctx.fillText(`${i / 100}km`, 10, i + 35);
    }

    // --- DISASTER LAYERS ---
    // Earthquake fault lines (rough, jagged)
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

      // Add danger zones around fault
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
      // Primary flood area
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

      // Secondary flood risk area
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
      // Major city
      rc.rectangle(2000, 1500, 400, 400, {
        fill: "rgba(75, 85, 99, 0.5)",
        fillStyle: "solid",
        stroke: "#1f2937",
        strokeWidth: 3,
        roughness: 0.5,
      });

      // Smaller towns
      const towns = [
        [1000, 3500, 200],
        [3800, 1200, 180],
        [4200, 2600, 150],
      ];
      towns.forEach(([tx, ty, size]) => {
        rc.rectangle(tx, ty, size, size, {
          fill: "rgba(107, 114, 128, 0.4)",
          stroke: "#374151",
          strokeWidth: 2,
          roughness: 0.8,
        });
      });
    }
  };

  useEffect(() => {
    draw();
  }, [map, layers]);

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
          <canvas ref={canvasRef} width={35000} height={35000} />
        </animated.div>
      </div>

      {/* Excalidraw-style controls */}
      <div className="map-controls">
        <button
          className="control-btn zoom-in"
          onClick={() => handleZoom("in")}
          title="Zoom in (Ctrl + Scroll)"
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
