import React, { useState, useEffect } from "react";
import ChatPanel from "./components/ChatPanel";
import StatePanel from "./components/StatePanel";
import MemoriesPanel from "./components/MemoriesPanel";
import PersonaSwitcher from "./components/PersonaSwitcher";
import ControlSliders from "./components/ControlSliders";

function App() {
  const [state, setState] = useState({});
  const [memories, setMemories] = useState([]);
  const [persona, setPersona] = useState("Kay Zero");

  useEffect(() => {
    const poll = () => {
      fetch("http://localhost:8765/state")
        .then(r => r.json())
        .then(setState)
        .catch(()=>{});
      fetch("http://localhost:8765/memories")
        .then(r => r.json())
        .then(data => setMemories(data.memories || []))
        .catch(()=>{});
    };
    poll();
    const intv = setInterval(poll, 2000);
    return () => clearInterval(intv);
  }, []);

  return (
    <div style={{ display: "flex", height: "100vh", fontFamily: "monospace", background: "#111", color: "#eee" }}>
      <div style={{ flex: 2, display: "flex", flexDirection: "column", borderRight: "2px solid #222" }}>
        <ChatPanel setState={setState} />
      </div>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: "1em" }}>
        <StatePanel state={state} />
        <ControlSliders state={state} />
        <PersonaSwitcher persona={persona} setPersona={setPersona} />
        <MemoriesPanel memories={memories} />
      </div>
    </div>
  );
}
export default App;
