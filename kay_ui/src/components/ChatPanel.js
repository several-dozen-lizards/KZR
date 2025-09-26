import React, { useState } from "react";

function ChatPanel({ setState }) {
  const [log, setLog] = useState([]);
  const [input, setInput] = useState("");

  const send = async () => {
    if (!input) return;
    setLog(l => [...l, { who: "You", text: input }]);
    setInput("");
    const r = await fetch("http://localhost:8765/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: input })
    }).then(r => r.json());
    setLog(l => [...l, { who: "Kay", text: r.reply }]);
    setState(s => ({ ...s, ...r.state }));
  };

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: "1em", overflowY: "auto" }}>
      <div style={{ flex: 1, overflowY: "auto", marginBottom: "1em", maxHeight: "80vh" }}>
        {log.map((item, i) =>
          <div key={i} style={{ margin: ".5em 0", color: item.who === "You" ? "#fff" : "#1fa" }}>
            <b>{item.who}:</b> {item.text}
          </div>
        )}
      </div>
      <div style={{ display: "flex" }}>
        <input
          style={{ flex: 1, fontSize: "1.2em", padding: "0.5em" }}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && send()}
        />
        <button onClick={send} style={{ marginLeft: "1em", fontSize: "1.1em", padding: "0.5em" }}>Send</button>
      </div>
    </div>
  );
}
export default ChatPanel;
