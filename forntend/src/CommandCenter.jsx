import React from 'react';

const CommandCenter = ({ drones, onSelectDrone, selectedDroneId, onSetMode, onClearPath }) => {
  const selectedDrone = drones.find(d => d.id === selectedDroneId);

  return (
    <div className="command-center">
      <div className="drone-list">
        <h3>Drone Fleet ({drones.length})</h3>
        <div className="drone-grid">
          {drones.map(drone => (
            <div 
              key={drone.id}
              className={`drone-card ${selectedDroneId === drone.id ? 'selected' : ''} ${drone.status}`}
              onClick={() => onSelectDrone(drone.id)}
            >
              <div className="drone-header">
                <span className="drone-name">{drone.name}</span>
                <span className={`status-badge ${drone.status}`}>{drone.status}</span>
              </div>
              <div className="drone-stats">
                <div className="stat">
                  <span>Battery</span>
                  <div className="battery-bar">
                    <div 
                      className="fill" 
                      style={{ 
                        width: `${drone.battery * 100}%`,
                        backgroundColor: drone.battery < 0.2 ? '#ef4444' : '#22c55e'
                      }}
                    />
                  </div>
                </div>
                <div className="stat">
                  <span>Mode</span>
                  <span className={`mode-badge ${drone.control_mode || 'auto'}`}>
                    {drone.control_mode || 'AUTO'}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="control-panel">
        <h3>Manual Control</h3>
        {selectedDrone ? (
          <div className="selected-controls">
            <div className="selected-info">
              <h4>{selectedDrone.name}</h4>
              <p>Position: {Math.round(selectedDrone.x)}, {Math.round(selectedDrone.y)}</p>
            </div>
            
            <div className="action-buttons">
              <button 
                className={`btn ${!selectedDrone.control_mode || selectedDrone.control_mode === 'auto' ? 'btn-manual' : 'btn-auto'}`}
                onClick={() => onSetMode(selectedDrone.id, (!selectedDrone.control_mode || selectedDrone.control_mode === 'auto') ? 'manual' : 'auto')}
              >
                {(!selectedDrone.control_mode || selectedDrone.control_mode === 'auto') ? 'Take Control (Manual)' : 'Switch to Auto'}
              </button>
              
              {selectedDrone.control_mode === 'manual' && (
                <>
                  <button className="btn btn-path" disabled>
                    (Click Map to Fly)
                  </button>
                  <button className="btn btn-recall" onClick={() => onClearPath(selectedDrone.id)}>
                    Stop / Clear Path
                  </button>
                </>
              )}
            </div>
          </div>
        ) : (
          <div className="no-selection">
            Select a drone to take control
          </div>
        )}
      </div>
    </div>
  );
};

export default CommandCenter;
