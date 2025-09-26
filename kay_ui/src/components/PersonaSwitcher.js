import React, { useState } from "react";
const personas = ["Kay Zero", "Kay Shadow", "Kay Villain", "Kay Therapist"];
export default function PersonaSwitcher({ persona, setPersona }) {
  return (
    <div>
      <h3>Persona</h3>
      <select value={persona} onChange={e => {
        setPersona(e.target.value);
        fetch("http://localhost:8765/persona", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ persona: e.target.value })
        });
      }}>
        {personas.map(p => <option key={p}>{p}</option>)}
      </select>
    </div>
  );
}
