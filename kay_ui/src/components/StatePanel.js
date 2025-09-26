import React from "react";
function bar(val, color, label) {
  return (
    <div style={{ marginBottom: 5 }}>
      <span>{label}</span>
      <div style={{
        display: "inline-block", marginLeft: 10,
        background: "#333", width: 120, height: 16, verticalAlign: "middle"
      }}>
        <div style={{
          background: color, width: `${Math.round((val || 0) * 100)}%`, height: 16
        }} />
      </div>
      <span style={{ marginLeft: 10 }}>{(val*100).toFixed(1)}%</span>
    </div>
  )
}
export default function StatePanel({ state }) {
  let emo = state.emotional_cocktail || {};
  let neu = state.neuromod || {};
  return (
    <div style={{ marginBottom: "2em" }}>
      <h3>Emotional State</h3>
      {Object.entries(emo).map(([k, v]) =>
        bar(v.intensity || 0, "#1fa", k)
      )}
      <h3>Neuromodulators</h3>
      {Object.entries(neu).map(([k, v]) =>
        typeof v === "number" ? bar(v, "#f80", k) : null
      )}
    </div>
  )
}
