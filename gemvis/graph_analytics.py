"""Graph topology analytics — derives cross-file insights from KG structure."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gemvis.knowledge_graph import KnowledgeGraph


class GraphAnalytics:
    def __init__(self, kg: KnowledgeGraph):
        self.kg = kg

    def compute_insights(self, node_id: str) -> dict:
        node_type = node_id.split(":", 1)[0] if ":" in node_id else ""
        result: dict = {"node_id": node_id, "node_type": node_type}

        graph = self.kg.get_graph_data()
        adj, node_map = self._build_adjacency(graph)

        if node_id not in adj:
            return result

        if node_type == "file":
            result["related_files"] = self._related_files(node_id, adj, node_map)
        else:
            result["bridge_score"] = self._bridge_score(node_id, adj)
            result["co_occurrences"] = self._co_occurrences(node_id, adj, node_map)
            result["timeline"] = self._timeline(node_id, adj, node_map)

        return result

    @staticmethod
    def _build_adjacency(graph: dict):
        adj: dict[str, set[str]] = defaultdict(set)
        node_map: dict[str, dict] = {}
        for n in graph.get("nodes", []):
            nid = n["id"]
            node_map[nid] = n
            adj.setdefault(nid, set())
        for e in graph.get("edges", []):
            s = e["source"] if isinstance(e["source"], str) else e["source"]["id"]
            t = e["target"] if isinstance(e["target"], str) else e["target"]["id"]
            adj[s].add(t)
            adj[t].add(s)
        return dict(adj), node_map

    @staticmethod
    def _bfs_component_count(adj: dict[str, set[str]], exclude: str | None = None) -> int:
        visited: set[str] = set()
        if exclude:
            visited.add(exclude)
        count = 0
        for node in adj:
            if node in visited:
                continue
            count += 1
            stack = [node]
            while stack:
                cur = stack.pop()
                if cur in visited:
                    continue
                visited.add(cur)
                for nb in adj.get(cur, ()):
                    if nb not in visited:
                        stack.append(nb)
        return count

    def _bridge_score(self, node_id: str, adj: dict[str, set[str]]) -> float:
        baseline = self._bfs_component_count(adj)
        removed = self._bfs_component_count(adj, exclude=node_id)
        new_components = removed - baseline
        if new_components <= 0:
            return 0.0
        return min(1.0, new_components / max(baseline, 1))

    def _co_occurrences(
        self, node_id: str, adj: dict[str, set[str]], node_map: dict[str, dict],
    ) -> list[dict]:
        connected_files = [
            nid for nid in adj.get(node_id, ())
            if node_map.get(nid, {}).get("type") == "file"
        ]

        entity_count: dict[str, int] = defaultdict(int)
        for fid in connected_files:
            for neighbor in adj.get(fid, ()):
                if neighbor != node_id and node_map.get(neighbor, {}).get("type") != "file":
                    entity_count[neighbor] += 1

        ranked = sorted(entity_count.items(), key=lambda x: x[1], reverse=True)[:10]
        return [
            {
                "entity_id": eid,
                "entity_name": node_map.get(eid, {}).get("name", eid),
                "entity_type": node_map.get(eid, {}).get("type", ""),
                "shared_count": cnt,
            }
            for eid, cnt in ranked
        ]

    def _related_files(
        self, file_id: str, adj: dict[str, set[str]], node_map: dict[str, dict],
    ) -> list[dict]:
        embeddings = self.kg.embeddings
        if embeddings is None or not embeddings.has(file_id):
            return []

        other_file_ids = [
            nid for nid, n in node_map.items()
            if n.get("type") == "file" and nid != file_id and embeddings.has(nid)
        ]
        if not other_file_ids:
            return []

        scores = embeddings.score_pair(file_id, other_file_ids)

        my_entities = {
            nid for nid in adj.get(file_id, ())
            if node_map.get(nid, {}).get("type") != "file"
        }

        results = []
        for fid, sim in scores.items():
            if sim <= 0:
                continue
            shared = my_entities & (adj.get(fid, set()) - {file_id})
            results.append({
                "file_id": fid,
                "file_name": node_map.get(fid, {}).get("name", fid),
                "shared_entities": [node_map.get(e, {}).get("name", e) for e in shared],
                "score": round(float(sim), 3),
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:10]

    def _timeline(
        self, node_id: str, adj: dict[str, set[str]], node_map: dict[str, dict],
    ) -> list[dict]:
        connected_files = [
            nid for nid in adj.get(node_id, ())
            if node_map.get(nid, {}).get("type") == "file"
        ]

        entries = []
        for fid in connected_files:
            n = node_map.get(fid, {})
            entries.append({
                "date": n.get("file_mtime", n.get("added_at", "")),
                "file_id": fid,
                "file_name": n.get("name", fid),
                "summary": n.get("summary", ""),
            })

        entries.sort(key=lambda x: x["date"])
        return entries
