import React from "react";
export default function ControlSliders({ state }) {
  let neu = state.neuromod || {};
  function setVal(k, v) {
    fetch("http://localhost:8765/control", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ [k]: parseFloat(v) })
    });
  }
  return (
    <div style={{ marginTop: 24 }}>
      <h3>Control</h3>
      {["dopamine", "serotonin", "oxytocin", "cortisol", "social_need"].map((k, i) =>
        <div key={k}>
          <label>{k}:</label>
          <input
            type="range" min="0" max="1" step="0.01"
            value={neu[k] || 0.5}
            onChange={e => setVal(k, e.target.value)}
            style={{ width: 160, marginLeft: 8 }}
          />
          <span style={{ marginLeft: 8 }}>{(neu[k] || 0.5).toFixed(2)}</span>
        </div>
      )}
    </div>
  );
}
