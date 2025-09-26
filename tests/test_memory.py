# tests/test_memory.py
from engine.memory_system import MemorySystem
mem = MemorySystem()
mem.encode_memory("hello", "response a", {"Fondness":{"intensity":0.6,"age":0}}, ["Fondness"])
mem.encode_memory("hello again", "response b", {"Anger":{"intensity":0.5,"age":0}}, ["Anger"])
res = mem.retrieve_biased_memories({"Fondness":{"intensity":0.7,"age":0}})
print("retrieved", len(res), "mems")
assert any("response a" in (m.get("assistant") or m.get("response","")) for m in res)
