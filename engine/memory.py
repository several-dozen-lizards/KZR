
from __future__ import annotations
import json, os, time
from typing import Dict, Any

class Memory:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(self.path, exist_ok=True)
        self.state_file = os.path.join(self.path, "state.json")
        if not os.path.exists(self.state_file):
            self._write({"truths": [], "motifs": [], "callbacks": [], "notes": []})

    def _read(self) -> Dict[str, Any]:
        with open(self.state_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, data: Dict[str, Any]) -> None:
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add_truth(self, text: str) -> None:
        data = self._read()
        if text not in data["truths"]:
            data["truths"].append(text); self._write(data)

    def add_motif(self, motif: str) -> None:
        data = self._read()
        if motif not in data["motifs"]:
            data["motifs"].append(motif); self._write(data)

    def add_callback(self, callback: str) -> None:
        data = self._read()
        if callback not in data["callbacks"]:
            data["callbacks"].append(callback); self._write(data)

    def add_note(self, note: str) -> None:
        data = self._read()
        data["notes"].append({"t": time.time(), "note": note}); self._write(data)

    def snapshot(self) -> Dict[str, Any]:
        return self._read()
