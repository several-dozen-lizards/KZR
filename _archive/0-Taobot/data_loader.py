import json
from py2neo import Graph, Node, Relationship
from dotenv import load_dotenv
load_dotenv()  # Loads variables from .env into environment
import os


# Connect to Neo4j
graph = Graph("bolt://localhost:7687", auth=("neo4j", "00000000"))


# Load JSON-LD
with open("self2.json") as f:
    data = json.load(f)

# First pass: create nodes
node_map = {}
for obj in data['@graph']:
    if 'id' in obj:  # Only create nodes for objects with an 'id'
        properties = {k: v for k, v in obj.items() if k not in ['id', 'type', 'relations']}
        # Flatten current_state if present
        if "current_state" in properties:
            for k, v in properties["current_state"].items():
                properties[f"current_state_{k}"] = v
            del properties["current_state"]
        node = Node(obj['type'], id=obj['id'], **properties)
        graph.merge(node, obj['type'], "id")
        node_map[obj['id']] = node

# Second pass: create relationships
for obj in data['@graph']:
    if 'relations' in obj and 'id' in obj:
        for rel in obj['relations']:
            target_id = rel['target']
            rel_type = rel['type'].upper()
            target_node = node_map.get(target_id)
            node = node_map.get(obj['id'])
            if node and target_node:
                edge = Relationship(node, rel_type, target_node)
                graph.merge(edge)

# Handle standalone edge objects (those with 'source' and 'target' but no 'id')
for obj in data['@graph']:
    if 'source' in obj and 'target' in obj and 'type' in obj and 'id' not in obj:
        source_node = node_map.get(obj['source'])
        target_node = node_map.get(obj['target'])
        rel_type = obj['type'].upper()
        if source_node and target_node:
            edge = Relationship(source_node, rel_type, target_node)
            graph.merge(edge)
