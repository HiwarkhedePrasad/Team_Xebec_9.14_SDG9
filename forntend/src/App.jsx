import { useEffect, useState } from "react";
import MapCanvas from "./MapCanvas";
import "./App.css";

export default function App() {
  const [map, setMap] = useState(null);
  const [layers, setLayers] = useState({
    terrain: true,
    flood: true,
    earthquake: true,
    humans: true,
  });

  useEffect(() => {
    fetch("/map_data.json")
      .then((res) => res.json())
      .then(setMap)
      .catch((err) => console.error("Error loading map:", err));
  }, []);

  const toggleLayer = (name) => {
    setLayers((prev) => ({ ...prev, [name]: !prev[name] }));
  };

  if (!map) return <h3>Loading map data...</h3>;

  return (
    <div>
      <h2>🌍 Disaster Zone – 50km × 50km</h2>

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
              {layerName}
            </span>
          </label>
        ))}
      </div>

      <MapCanvas map={map} layers={layers} />
    </div>
  );
}
