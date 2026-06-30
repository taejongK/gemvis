"""Lightweight knowledge graph using rdflib with TTL (RDF/Turtle) persistence."""

import json
import logging
from pathlib import Path
from datetime import datetime
from urllib.parse import quote, unquote

from rdflib import Graph as RDFGraph, Namespace, URIRef, Literal, RDF

from gemvis.config import GRAPH_PATH
from gemvis.insight import GemInsight
from gemvis.embeddings import EmbeddingStore

logger = logging.getLogger(__name__)

NODE_TYPES = {"file", "person", "place", "project", "event", "date", "tag"}
# Internal/metadata types — hidden from graph view, search results, and stats.
SYSTEM_NODE_TYPES = {"daily_summary"}
EDGE_TYPES = {
    "mentions", "taken_at", "related_to", "part_of", "created_on",
    "tagged_with", "added_on",
    "belongs_to", "located_at", "participated_in", "works_on", "occurred_at",
    "covers_file",
}

GV_NODE = Namespace("http://gemvis.local/node/")
GV_TYPE = Namespace("http://gemvis.local/type/")
GV_REL = Namespace("http://gemvis.local/rel/")
GV_ATTR = Namespace("http://gemvis.local/attr/")

SPARQL_PREFIXES = """\
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX gvn:  <http://gemvis.local/node/>
PREFIX gvt:  <http://gemvis.local/type/>
PREFIX gvr:  <http://gemvis.local/rel/>
PREFIX gva:  <http://gemvis.local/attr/>
"""


class KnowledgeGraph:
    def __init__(
        self,
        graph_path: str | Path | None = None,
        embeddings: EmbeddingStore | None = None,
    ):
        self.graph_path = Path(graph_path) if graph_path else GRAPH_PATH
        self.rdf = RDFGraph()
        self._bind_namespaces()
        self.embeddings = embeddings if embeddings is not None else EmbeddingStore()
        self.load()

    def _bind_namespaces(self):
        self.rdf.bind("gvn", GV_NODE)
        self.rdf.bind("gvt", GV_TYPE)
        self.rdf.bind("gvr", GV_REL)
        self.rdf.bind("gva", GV_ATTR)

    def _node_uri(self, node_type: str, name: str) -> URIRef:
        """Build a URI for a node from its type and name."""
        return URIRef(str(GV_NODE) + f"{node_type}/{quote(name, safe='')}")

    def _uri_to_node_id(self, uri: URIRef) -> str | None:
        """Convert a node URI back to the internal node ID."""
        uri_str = str(uri)
        prefix = str(GV_NODE)
        if not uri_str.startswith(prefix):
            return None
        path = uri_str[len(prefix):]
        if "/" not in path:
            return None
        node_type, encoded_name = path.split("/", 1)
        name = unquote(encoded_name)
        return f"{node_type}:{name}"

    def _node_to_dict(self, uri: URIRef) -> dict | None:
        """Build a node dict from a URI by reading its rdf:type and attributes."""
        type_prefix = str(GV_TYPE)
        attr_prefix = str(GV_ATTR)

        node_id = self._uri_to_node_id(uri)
        if node_id is None:
            return None

        # Find node type
        node_type = None
        for obj in self.rdf.objects(uri, RDF.type):
            obj_str = str(obj)
            if obj_str.startswith(type_prefix):
                node_type = obj_str[len(type_prefix):]
                break
        if node_type is None:
            return None

        _, name = node_id.split(":", 1)
        result = {"id": node_id, "type": node_type, "name": name}

        # Collect attributes
        for pred, obj in self.rdf.predicate_objects(uri):
            pred_str = str(pred)
            if isinstance(obj, Literal) and pred_str.startswith(attr_prefix):
                attr_key = pred_str[len(attr_prefix):]
                result[attr_key] = str(obj)

        return result

    def _backfill_names(self):
        """Add gva:name literal for any nodes that only have it in their URI.

        Older TTL files don't store the display name as a literal, which makes
        SPARQL CONTAINS filters impossible. This fills in the missing triples.
        """
        name_pred = URIRef(str(GV_ATTR) + "name")
        type_prefix = str(GV_TYPE)
        added = 0
        for subj, _, obj in self.rdf.triples((None, RDF.type, None)):
            if not isinstance(subj, URIRef) or not str(obj).startswith(type_prefix):
                continue
            # Skip if already has a name
            if (subj, name_pred, None) in self.rdf:
                continue
            node_id = self._uri_to_node_id(subj)
            if node_id is None:
                continue
            _, display_name = node_id.split(":", 1)
            self.rdf.add((subj, name_pred, Literal(display_name)))
            added += 1
        if added:
            logger.info("Backfilled gva:name for %d nodes (migration)", added)

    def has_node(self, node_id: str) -> bool:
        """Check if a node exists in the graph."""
        if ":" not in node_id:
            return False
        node_type, name = node_id.split(":", 1)
        uri = self._node_uri(node_type, name)
        return (uri, RDF.type, None) in self.rdf

    def get_status(self, node_id: str) -> str | None:
        """Return the analysis_status of a node, or None if not found."""
        if not self.has_node(node_id):
            return None
        node_type, name = node_id.split(":", 1)
        uri = self._node_uri(node_type, name)
        status_pred = URIRef(str(GV_ATTR) + "analysis_status")
        for obj in self.rdf.objects(uri, status_pred):
            return str(obj)
        return None

    # ── v2: State machine + Hydration helpers ─────────────────────

    def upsert_skeleton(
        self,
        file_path: str,
        size_bytes: int | None,
        file_mtime: float | None,
        file_ctime: float | None,
        *,
        save: bool = True,
    ) -> str:
        """Stage 1 hydration: create/refresh a file node with physical metadata only.

        analysis_status is forced to "pending" so the watcher can enqueue LLM
        analysis. Does NOT touch existing LLM-derived attributes (category,
        summary, etc.) or existing entity neighbors.

        Returns the node ID (file:{file_path}).
        """
        mtime_iso = datetime.fromtimestamp(file_mtime).isoformat() if file_mtime else ""
        ctime_iso = datetime.fromtimestamp(file_ctime).isoformat() if file_ctime else ""
        added_at = datetime.now().isoformat()

        uri = self._node_uri("file", file_path)
        existed = (uri, RDF.type, None) in self.rdf

        # Preserve original added_at if node already exists
        if existed:
            existing_added = None
            added_at_pred = URIRef(str(GV_ATTR) + "added_at")
            for obj in self.rdf.objects(uri, added_at_pred):
                existing_added = str(obj)
                break
            if existing_added:
                added_at = existing_added

        attrs: dict[str, str] = {"analysis_status": "pending"}
        if mtime_iso:
            attrs["file_mtime"] = mtime_iso
        if ctime_iso:
            attrs["file_ctime"] = ctime_iso
        if size_bytes is not None:
            attrs["size_bytes"] = str(size_bytes)
        attrs["added_at"] = added_at

        node_id = self.add_node("file", file_path, **attrs)
        if save:
            self.save()
        return node_id

    def update_status(
        self,
        file_path: str,
        status: str,
        error: str | None = None,
        *,
        save: bool = True,
    ) -> bool:
        """Update only the analysis_status (and error) of an existing file node.

        Used for Stage 2 transitions (pending → processing → completed/failed)
        and Stage 3 rollback (on_modified → pending).

        Returns True if the node existed and was updated.
        """
        node_id = f"file:{file_path}"
        if not self.has_node(node_id):
            return False

        uri = self._node_uri("file", file_path)
        status_pred = URIRef(str(GV_ATTR) + "analysis_status")
        self.rdf.remove((uri, status_pred, None))
        self.rdf.add((uri, status_pred, Literal(status)))

        if error is not None:
            err_pred = URIRef(str(GV_ATTR) + "error")
            self.rdf.remove((uri, err_pred, None))
            self.rdf.add((uri, err_pred, Literal(error)))

        if save:
            self.save()
        return True

    def rollback_processing_to_pending(self) -> int:
        """On startup, flip any `analysis_status == "processing"` nodes back to
        "pending" so they get re-queued (Gemma 4 crash recovery).

        Returns the number of nodes rolled back.
        """
        type_uri = URIRef(str(GV_TYPE) + "file")
        status_pred = URIRef(str(GV_ATTR) + "analysis_status")
        rolled = 0
        for subj in list(self.rdf.subjects(RDF.type, type_uri)):
            current = None
            for obj in self.rdf.objects(subj, status_pred):
                current = str(obj)
                break
            if current == "processing":
                self.rdf.remove((subj, status_pred, None))
                self.rdf.add((subj, status_pred, Literal("pending")))
                rolled += 1
        if rolled:
            self.save()
            logger.info("Rolled back %d node(s) from processing → pending", rolled)
        return rolled

    def sparql(self, query: str, **bindings) -> list[dict]:
        """Run a SPARQL SELECT query with optional variable bindings.

        The PREFIX block for gvn/gvt/gvr/gva is auto-prepended.

        Example:
            kg.sparql(
                "SELECT ?file WHERE { ?file a gvt:file ; gvr:mentions ?p . ?p gva:name ?name }",
                name=Literal("김철수"),
            )
        """
        full_query = SPARQL_PREFIXES + "\n" + query
        init = bindings if bindings else None
        rows = []
        for row in self.rdf.query(full_query, initBindings=init):
            # rdflib Row → {var_name: value}
            rows.append({str(k): row[k] for k in row.labels})
        return rows

    def load(self):
        """Load graph from TTL file."""
        if not self.graph_path.exists():
            logger.info("No existing graph found, starting fresh")
            return
        try:
            self.rdf = RDFGraph()
            self._bind_namespaces()
            self.rdf.parse(self.graph_path, format="turtle")

            # Migration: backfill gva:name for nodes that predate the name-literal
            self._backfill_names()

            # Count nodes and edges for logging
            type_prefix = str(GV_TYPE)
            rel_prefix = str(GV_REL)
            node_count = sum(1 for _, _, o in self.rdf.triples((None, RDF.type, None))
                             if str(o).startswith(type_prefix))
            edge_count = sum(1 for _, p, o in self.rdf.triples((None, None, None))
                             if isinstance(o, URIRef) and str(p).startswith(rel_prefix))
            logger.info("Loaded graph with %d nodes, %d edges", node_count, edge_count)
        except Exception as e:
            logger.error("Failed to load graph: %s", e)
            self.rdf = RDFGraph()
            self._bind_namespaces()

    def save(self):
        """Save graph to TTL file."""
        self.graph_path.parent.mkdir(parents=True, exist_ok=True)
        self.rdf.serialize(destination=str(self.graph_path), format="turtle")

        type_prefix = str(GV_TYPE)
        rel_prefix = str(GV_REL)
        node_count = sum(1 for _, _, o in self.rdf.triples((None, RDF.type, None))
                         if str(o).startswith(type_prefix))
        edge_count = sum(1 for _, p, o in self.rdf.triples((None, None, None))
                         if isinstance(o, URIRef) and str(p).startswith(rel_prefix))
        logger.info("Saved graph: %d nodes, %d edges", node_count, edge_count)

    def _node_id(self, node_type: str, name: str) -> str:
        """Create a consistent node ID."""
        return f"{node_type}:{name}"

    def add_node(self, node_type: str, name: str, **attrs) -> str:
        """Add a node to the graph. Returns the node ID."""
        uri = self._node_uri(node_type, name)
        self.rdf.add((uri, RDF.type, URIRef(str(GV_TYPE) + node_type)))

        # Always store the display name as a literal so SPARQL queries can filter on it
        name_pred = URIRef(str(GV_ATTR) + "name")
        self.rdf.remove((uri, name_pred, None))
        self.rdf.add((uri, name_pred, Literal(name)))

        for key, val in attrs.items():
            if val is None or key == "name":
                continue
            # Remove old value for this attribute before setting new one
            attr_pred = URIRef(str(GV_ATTR) + key)
            self.rdf.remove((uri, attr_pred, None))
            self.rdf.add((uri, attr_pred, Literal(str(val))))
        return self._node_id(node_type, name)

    def add_edge(self, source_id: str, target_id: str, edge_type: str, **attrs):
        """Add an edge between two nodes."""
        src_type, src_name = source_id.split(":", 1)
        tgt_type, tgt_name = target_id.split(":", 1)
        src_uri = self._node_uri(src_type, src_name)
        tgt_uri = self._node_uri(tgt_type, tgt_name)
        self.rdf.add((src_uri, URIRef(str(GV_REL) + edge_type), tgt_uri))

    def _has_any_edge(self, uri: URIRef) -> bool:
        """True if the URI has any outgoing or incoming gvr: edge."""
        rel_prefix = str(GV_REL)
        for _, p, _ in self.rdf.triples((uri, None, None)):
            if str(p).startswith(rel_prefix):
                return True
        for _, p, _ in self.rdf.triples((None, None, uri)):
            if str(p).startswith(rel_prefix):
                return True
        return False

    def _remove_node_triples(self, node_id: str) -> bool:
        """Internal: remove a single node's triples + embedding. No cascade, no save."""
        if ":" not in node_id:
            return False
        node_type, name = node_id.split(":", 1)
        uri = self._node_uri(node_type, name)

        if (uri, RDF.type, None) not in self.rdf:
            return False

        self.rdf.remove((uri, None, None))
        self.rdf.remove((None, None, uri))

        try:
            self.embeddings.remove(node_id)
        except Exception as e:
            logger.warning("Failed to remove embedding for %s: %s", node_id, e)
        return True

    def remove_node(self, node_id: str, cascade_orphans: bool = True) -> bool:
        """Remove a node, all its attributes, and edges touching it.

        Also removes the associated embedding if present. If ``cascade_orphans``
        is True (default), any neighbor nodes that become orphaned (no other
        edges) as a result are removed as well. File nodes are never auto-removed
        by cascade since only the explicitly-targeted file should be deleted.

        Returns True if the node existed and was removed, False otherwise.
        """
        if ":" not in node_id:
            return False
        node_type, name = node_id.split(":", 1)
        uri = self._node_uri(node_type, name)

        if (uri, RDF.type, None) not in self.rdf:
            return False

        # Collect neighbor IDs before mutation (for cascade check)
        neighbor_ids: set[str] = set()
        if cascade_orphans:
            rel_prefix = str(GV_REL)
            for _, p, obj in self.rdf.triples((uri, None, None)):
                if isinstance(obj, URIRef) and str(p).startswith(rel_prefix):
                    nid = self._uri_to_node_id(obj)
                    if nid:
                        neighbor_ids.add(nid)
            for subj, p, _ in self.rdf.triples((None, None, uri)):
                if isinstance(subj, URIRef) and str(p).startswith(rel_prefix):
                    nid = self._uri_to_node_id(subj)
                    if nid:
                        neighbor_ids.add(nid)

        # Remove the main node
        self._remove_node_triples(node_id)
        logger.info("Removed node %s", node_id)

        # Cascade: remove neighbors that are now orphans (no other connections)
        # Skip file-type neighbors so deletion never propagates to other files.
        if cascade_orphans:
            for nid in neighbor_ids:
                if ":" not in nid:
                    continue
                ntype, nname = nid.split(":", 1)
                if ntype == "file":
                    continue
                nuri = self._node_uri(ntype, nname)
                if (nuri, RDF.type, None) not in self.rdf:
                    continue  # already gone
                if not self._has_any_edge(nuri):
                    self._remove_node_triples(nid)
                    logger.info("Removed orphan %s (cascade)", nid)

        self.save()
        return True

    def add_insight(self, insight: GemInsight, *, save: bool = True):
        """Add a GemInsight to the graph, creating nodes and edges.

        v2 (geminsight-develop): also persists the full GemInsight JSON as
        the `raw_insight` attribute so it can be rehydrated without lossy
        reassembly from neighbor nodes.
        """
        if insight.error:
            logger.warning("Skipping errored insight for %s: %s", insight.file_path, insight.error)
            return

        # Use file's actual timestamps if available
        if insight.file_mtime:
            file_mtime_iso = datetime.fromtimestamp(insight.file_mtime).isoformat()
        else:
            file_mtime_iso = datetime.now().isoformat()

        if insight.file_ctime:
            file_ctime_iso = datetime.fromtimestamp(insight.file_ctime).isoformat()
        else:
            file_ctime_iso = datetime.now().isoformat()

        # Preserve the original added_at if the skeleton stage already set it;
        # otherwise stamp it now.
        gemvis_added_at = insight.added_at or datetime.now().isoformat()
        insight.added_at = gemvis_added_at

        # Serialize the full GemInsight for lossless restoration (SSoT v2).
        raw_insight_json = json.dumps(insight.to_dict(), ensure_ascii=False)

        # File node — flat attributes (used by existing search/graph queries)
        # + raw_insight (used by InsightService for full object restoration).
        file_id = self.add_node(
            "file", insight.file_path,
            category=insight.category,
            summary=insight.summary,
            risk_level=insight.risk_level,
            file_mtime=file_mtime_iso,      # 파일 수정일
            file_ctime=file_ctime_iso,      # 파일 생성일
            added_at=gemvis_added_at,       # Gemvis 추가일
            analysis_status=insight.analysis_status or "completed",
            last_analyzed_at=insight.last_analyzed_at or "",
            size_bytes=str(insight.size_bytes) if insight.size_bytes is not None else "",
            error=insight.error or "",
            raw_insight=raw_insight_json,
        )

        # Entity nodes and edges
        entity_type_map = {
            "people": ("person", "mentions"),
            "places": ("place", "taken_at"),
            "projects": ("project", "part_of"),
            "events": ("event", "related_to"),
            "dates": ("date", "created_on"),
        }

        for entity_key, (node_type, edge_type) in entity_type_map.items():
            for entity_name in insight.entities.get(entity_key, []):
                if not entity_name:
                    continue
                entity_id = self.add_node(node_type, entity_name)
                self.add_edge(file_id, entity_id, edge_type)

        # Tag nodes and edges
        for tag in insight.tags:
            if not tag:
                continue
            tag_id = self.add_node("tag", tag)
            self.add_edge(file_id, tag_id, "tagged_with")

        # Entity-to-entity relations
        for rel in getattr(insight, "relations", []):
            src_name = rel.get("source", "")
            src_type = rel.get("source_type", "")
            tgt_name = rel.get("target", "")
            tgt_type = rel.get("target_type", "")
            rel_type = rel.get("relation", "related_to")
            if not (src_name and src_type and tgt_name and tgt_type):
                continue
            if src_type not in NODE_TYPES or tgt_type not in NODE_TYPES:
                continue
            if rel_type not in EDGE_TYPES:
                rel_type = "related_to"
            src_id = self.add_node(src_type, src_name)
            tgt_id = self.add_node(tgt_type, tgt_name)
            self.add_edge(src_id, tgt_id, rel_type)

        # File date node (based on file's actual modification time)
        if insight.file_mtime:
            date_str = datetime.fromtimestamp(insight.file_mtime).strftime("%Y-%m-%d")
        else:
            date_str = datetime.now().strftime("%Y-%m-%d")
        date_id = self.add_node("date", date_str)
        self.add_edge(file_id, date_id, "added_on")

        # Embed the file's semantic content (summary + tags + category + entity names)
        entity_text_parts = []
        for entity_list in insight.entities.values():
            for e in entity_list:
                if e:
                    entity_text_parts.append(e)
        embed_text = " ".join(filter(None, [
            insight.summary,
            insight.category,
            " ".join(insight.tags or []),
            " ".join(entity_text_parts),
        ])).strip()
        if embed_text:
            self.embeddings.add(file_id, embed_text)

        if save:
            self.save()

    def search_nodes(self, query: str, node_type: str | None = None) -> list[dict]:
        """Search nodes via SPARQL substring filter on name/summary/category.

        Matches if any of the text attributes contain the query (case-insensitive).
        """
        if not query:
            return []

        # Build optional type constraint
        type_filter = f"?s a gvt:{node_type} ." if node_type else "?s a ?node_type_uri . FILTER(STRSTARTS(STR(?node_type_uri), STR(gvt:)))"

        sparql_query = f"""
        SELECT DISTINCT ?s WHERE {{
            {type_filter}
            ?s gva:name ?name .
            OPTIONAL {{ ?s gva:summary ?summary }}
            OPTIONAL {{ ?s gva:category ?category }}
            FILTER(
                CONTAINS(LCASE(STR(?name)), LCASE(STR(?q))) ||
                CONTAINS(LCASE(STR(COALESCE(?summary, ""))), LCASE(STR(?q))) ||
                CONTAINS(LCASE(STR(COALESCE(?category, ""))), LCASE(STR(?q)))
            )
        }}
        """
        rows = self.sparql(sparql_query, q=Literal(query))

        results = []
        for row in rows:
            uri = row.get("s")
            if uri is None:
                continue
            node_dict = self._node_to_dict(uri)
            if node_dict and node_dict["type"] not in SYSTEM_NODE_TYPES:
                results.append(node_dict)
        return results

    def get_neighbors(self, node_id: str) -> list[dict]:
        """Get all neighboring nodes via SPARQL UNION (outgoing + incoming edges)."""
        if ":" not in node_id:
            return []
        node_type, name = node_id.split(":", 1)
        uri = self._node_uri(node_type, name)

        if (uri, RDF.type, None) not in self.rdf:
            return []

        rel_prefix = str(GV_REL)
        sparql_query = """
        SELECT DISTINCT ?neighbor ?pred WHERE {
            {
                ?target ?pred ?neighbor .
                FILTER(?target = ?uri)
                FILTER(STRSTARTS(STR(?pred), STR(gvr:)))
                FILTER(isIRI(?neighbor))
            } UNION {
                ?neighbor ?pred ?target .
                FILTER(?target = ?uri)
                FILTER(STRSTARTS(STR(?pred), STR(gvr:)))
                FILTER(isIRI(?neighbor))
            }
        }
        """
        rows = self.sparql(sparql_query, uri=uri)

        neighbors = []
        seen = set()
        for row in rows:
            n_uri = row.get("neighbor")
            p_uri = row.get("pred")
            if n_uri is None or p_uri is None:
                continue
            nd = self._node_to_dict(n_uri)
            if nd and nd["id"] not in seen:
                nd["edge_type"] = str(p_uri)[len(rel_prefix):]
                neighbors.append(nd)
                seen.add(nd["id"])
        return neighbors

    def get_file_nodes(self) -> list[dict]:
        """Get all file nodes, sorted by added_at descending."""
        files = []
        type_uri = URIRef(str(GV_TYPE) + "file")
        for uri in self.rdf.subjects(RDF.type, type_uri):
            node_dict = self._node_to_dict(uri)
            if node_dict:
                files.append(node_dict)
        files.sort(key=lambda x: x.get("added_at", ""), reverse=True)
        return files

    def get_all_nodes_by_type(self, node_type: str) -> list[dict]:
        """Get all nodes of a given type."""
        type_uri = URIRef(str(GV_TYPE) + node_type)
        results = []
        for uri in self.rdf.subjects(RDF.type, type_uri):
            node_dict = self._node_to_dict(uri)
            if node_dict:
                results.append(node_dict)
        return results

    def get_graph_data(self) -> dict:
        """Get all nodes and edges for visualization (excludes system metadata)."""
        type_prefix = str(GV_TYPE)
        rel_prefix = str(GV_REL)

        # Collect visible node IDs first so we can filter edges that reference hidden nodes
        visible_ids: set[str] = set()
        nodes = []
        for subj, _, obj in self.rdf.triples((None, RDF.type, None)):
            if not str(obj).startswith(type_prefix):
                continue
            node_dict = self._node_to_dict(subj)
            if node_dict is None:
                continue
            if node_dict["type"] in SYSTEM_NODE_TYPES:
                continue
            if node_dict["type"] == "file":
                node_dict["name"] = Path(node_dict["name"]).name
            nodes.append(node_dict)
            visible_ids.add(node_dict["id"])

        edges = []
        for subj, pred, obj in self.rdf.triples((None, None, None)):
            pred_str = str(pred)
            if isinstance(obj, URIRef) and pred_str.startswith(rel_prefix):
                src_id = self._uri_to_node_id(subj)
                tgt_id = self._uri_to_node_id(obj)
                if src_id in visible_ids and tgt_id in visible_ids:
                    edge_type = pred_str[len(rel_prefix):]
                    edges.append({
                        "source": src_id,
                        "target": tgt_id,
                        "type": edge_type,
                    })

        return {"nodes": nodes, "edges": edges}

    def get_stats(self) -> dict:
        """Get graph statistics by direct RDF iteration (Python 3.14 pyparsing workaround)."""
        type_prefix = str(GV_TYPE)
        rel_prefix = str(GV_REL)

        # Count nodes by type (direct iteration)
        type_counts = {}
        for s, p, o in self.rdf.triples((None, RDF.type, None)):
            if not str(o).startswith(type_prefix):
                continue
            t_name = str(o)[len(type_prefix):]
            if t_name in SYSTEM_NODE_TYPES:
                continue
            type_counts[t_name] = type_counts.get(t_name, 0) + 1

        total_nodes = sum(type_counts.values())

        # Count edges (direct iteration)
        total_edges = sum(
            1 for s, p, o in self.rdf.triples((None, None, None))
            if isinstance(o, URIRef) and str(p).startswith(rel_prefix)
        )

        return {
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "node_types": type_counts,
        }

    def clear(self):
        """Clear the graph and embeddings."""
        self.rdf = RDFGraph()
        self._bind_namespaces()
        self.embeddings.clear()
        self.save()

    # Backward compatibility alias
    def add_analysis_result(self, result: GemInsight):
        """Deprecated: Use add_insight() instead."""
        return self.add_insight(result)
