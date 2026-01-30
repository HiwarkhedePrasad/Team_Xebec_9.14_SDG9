import React from "react";

/**
 * Rescue Team Dashboard
 * Shows detected survivors, their locations, and rescue status
 */
export default function RescueDashboard({ survivors, drones, alerts }) {
  // Sort survivors - unrescued first, then by confidence
  const sortedSurvivors = [...survivors].sort((a, b) => {
    if (a.rescued !== b.rescued) return a.rescued ? 1 : -1;
    return b.confidence - a.confidence;
  });

  // Find responding drones
  const respondingDrones = drones.filter(d => d.status === "responding");

  return (
    <div className="rescue-dashboard">
      <div className="dashboard-header">
        <h2>🚨 Rescue Team Command Center</h2>
        <div className="stats-bar">
          <div className="stat">
            <span className="stat-value">{survivors.filter(s => !s.rescued).length}</span>
            <span className="stat-label">Awaiting Rescue</span>
          </div>
          <div className="stat">
            <span className="stat-value">{respondingDrones.length}</span>
            <span className="stat-label">Drones Responding</span>
          </div>
          <div className="stat">
            <span className="stat-value">{survivors.filter(s => s.rescued).length}</span>
            <span className="stat-label">Rescued</span>
          </div>
        </div>
      </div>

      <div className="dashboard-content">
        {/* Survivor List */}
        <div className="survivor-list">
          <h3>📍 Detected Survivors</h3>
          {sortedSurvivors.length === 0 ? (
            <div className="empty-state">
              <span>🔍</span>
              <p>No survivors detected yet. Drones are scanning...</p>
            </div>
          ) : (
            <div className="survivor-cards">
              {sortedSurvivors.map((survivor, index) => (
                <SurvivorCard 
                  key={survivor.id || index} 
                  survivor={survivor}
                  drone={drones.find(d => d.id === survivor.detected_by)}
                  respondingDrone={respondingDrones.find(d => 
                    d.current_mission?.includes(survivor.id)
                  )}
                />
              ))}
            </div>
          )}
        </div>
        
        {/* Drone Fleet Status */}
        <div className="drone-fleet-status">
          <h3>🚁 Drone Fleet</h3>
          <div className="drone-list">
            {drones.map(drone => (
              <div key={drone.id} className="drone-item">
                <div className="drone-info">
                  <span className="drone-name">{drone.name}</span>
                  <span className={`drone-status status-${drone.status}`}>{drone.status}</span>
                </div>
                <div className="battery-container">
                  <div 
                    className={`battery-bar ${drone.battery < 0.2 ? 'low' : drone.battery < 0.5 ? 'medium' : 'high'}`}
                    style={{ width: `${Math.round(drone.battery * 100)}%` }}
                  />
                  <span className="battery-text">{Math.round(drone.battery * 100)}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>


        {/* Recent Alerts */}
        <div className="alert-feed">
          <h3>📢 Live Feed</h3>
          <div className="alert-items">
            {alerts.slice(-10).reverse().map((alert, i) => (
              <div key={i} className={`alert-item alert-${alert.type?.toLowerCase()}`}>
                <span className="alert-time">
                  {new Date().toLocaleTimeString()}
                </span>
                <span className="alert-text">{alert.message}</span>
                {alert.payload?.x && (
                  <span className="alert-coords">
                    ({Math.round(alert.payload.x)}, {Math.round(alert.payload.y)})
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function SurvivorCard({ survivor, drone, respondingDrone }) {
  const confidence = Math.round((survivor.confidence || 0.8) * 100);
  const isHighPriority = confidence > 85;
  
  return (
    <div className={`survivor-card ${survivor.rescued ? 'rescued' : ''} ${isHighPriority ? 'high-priority' : ''}`}>
      <div className="card-header">
        <span className={`priority-badge ${isHighPriority ? 'high' : 'medium'}`}>
          {isHighPriority ? '🔴 HIGH' : '🟡 MEDIUM'}
        </span>
        {survivor.rescued && <span className="rescued-badge">✓ RESCUED</span>}
      </div>
      
      <div className="card-body">
        <div className="location-info">
          <h4>📍 Location</h4>
          <div className="coordinates">
            <span>X: {Math.round(survivor.x)}</span>
            <span>Y: {Math.round(survivor.y)}</span>
          </div>
          <div className="grid-cell">
            Grid: ({Math.floor(survivor.x / 500)}, {Math.floor(survivor.y / 500)})
          </div>
        </div>
        
        <div className="detection-info">
          <div className="confidence-bar">
            <div 
              className="confidence-fill" 
              style={{ width: `${confidence}%` }}
            />
            <span>{confidence}% confidence</span>
          </div>
          
          <div className="detected-by">
            Detected by: <strong>{drone?.name || survivor.detected_by}</strong>
          </div>
        </div>
      </div>
      
      <div className="card-footer">
        {!survivor.rescued ? (
          respondingDrone ? (
            <div className="status responding">
              🚁 {respondingDrone.name} en route
            </div>
          ) : (
            <div className="status awaiting">
              ⏳ Awaiting rescue drone
            </div>
          )
        ) : (
          <div className="status complete">
            ✅ Rescue complete
          </div>
        )}
      </div>
    </div>
  );
}
