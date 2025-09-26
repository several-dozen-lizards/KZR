import React from "react";
export default function MemoriesPanel({ memories }) {
  return (
    <div style={{ marginTop: "2em" }}>
      <h3>Recent Memories</h3>
      <div style={{ maxHeight: 120, overflowY: "auto" }}>
        {(memories || []).map((m, i) =>
          <div key={i} style={{ padding: "4px 0", borderBottom: "1px solid #222" }}>
            <div><b>Time:</b> {m.timestamp}</div>
            <div><b>User:</b> {m.user_text}</div>
            <div><b>Kay:</b> {m.ai_text}</div>
            <div><b>Dominant:</b> {m.emotion_inferred}</div>
          </div>
        )}
      </div>
    </div>
  )
}
