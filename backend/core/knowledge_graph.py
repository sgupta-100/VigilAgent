from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable


class NodeKind(str, Enum):
    TARGET = "target"
    DOMAIN = "domain"
    HOST = "host"
    SERVICE = "service"
    URL = "url"
    ENDPOINT = "endpoint"
    PARAMETER = "parameter"
    AUTH_SCHEME = "auth_scheme"
    TOKEN = "token"
    COOKIE = "cookie"
    SESSION = "session"
    CREDENTIAL = "credential"
    SECRET = "secret"
    VULNERABILITY = "vulnerability"
    CVE = "cve"
    WEAKNESS = "weakness"
    FINDING = "finding"
    EVIDENCE = "evidence"
    OBJECTIVE = "objective"
    ATTACK_PATH = "attack_path"
    TECHNIQUE = "technique"


class EdgeKind(str, Enum):
    RESOLVES_TO = "resolves_to"
    EXPOSES = "exposes"
    CONTAINS_ENDPOINT = "contains_endpoint"
    ACCEPTS_PARAMETER = "accepts_parameter"
    AUTHENTICATED_BY = "authenticated_by"
    HAS_SESSION = "has_session"
    LEAKS_SECRET = "leaks_secret"
    HAS_VULN = "has_vuln"
    VALIDATES = "validates"
    EXPLOITS = "exploits"
    LEADS_TO = "leads_to"
    PIVOTS_TO = "pivots_to"
    ESCALATES_TO = "escalates_to"
    REACHES = "reaches"
    SUPPORTS = "supports"


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class KGNode:
    kind: NodeKind
    label: str
    props: dict[str, Any] = field(default_factory=dict)
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = stable_id(self.kind.value, self.label)


@dataclass
class KGEdge:
    src_id: str
    dst_id: str
    kind: EdgeKind
    weight: float = 1.0
    props: dict[str, Any] = field(default_factory=dict)
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = stable_id(self.src_id, self.kind.value, self.dst_id)


def stable_id(*parts: str) -> str:
    raw = "|".join(part.lower().strip() for part in parts)
    return hashlib.sha1(raw.encode("utf-8", errors="replace")).hexdigest()


class KnowledgeGraph:
    def __init__(self) -> None:
        self.nodes: dict[str, KGNode] = {}
        self.edges: dict[str, KGEdge] = {}

    def upsert_node(self, node: KGNode) -> KGNode:
        existing = self.nodes.get(node.id)
        if existing:
            existing.props.update(node.props)
            return existing
        self.nodes[node.id] = node
        return node

    def upsert_edge(self, edge: KGEdge) -> KGEdge:
        existing = self.edges.get(edge.id)
        if existing:
            existing.weight = max(existing.weight, edge.weight)
            existing.props.update(edge.props)
            return existing
        self.edges[edge.id] = edge
        return edge

    def link(self, src: KGNode, dst: KGNode, kind: EdgeKind, *, weight: float = 1.0, props: dict[str, Any] | None = None) -> KGEdge:
        src = self.upsert_node(src)
        dst = self.upsert_node(dst)
        return self.upsert_edge(KGEdge(src.id, dst.id, kind, weight, props or {}))

    def by_kind(self, kind: NodeKind) -> list[KGNode]:
        return [node for node in self.nodes.values() if node.kind == kind]

    def neighbors(self, node_id: str, *, direction: str = "out", edge_kind: EdgeKind | None = None) -> list[KGNode]:
        found: list[KGNode] = []
        for edge in self.edges.values():
            if edge_kind and edge.kind != edge_kind:
                continue
            if direction in {"out", "both"} and edge.src_id == node_id and edge.dst_id in self.nodes:
                found.append(self.nodes[edge.dst_id])
            if direction in {"in", "both"} and edge.dst_id == node_id and edge.src_id in self.nodes:
                found.append(self.nodes[edge.src_id])
        return found

    def ingest_finding(self, finding: dict[str, Any], *, scan_id: str = "GLOBAL") -> KGNode:
        endpoint = str(finding.get("endpoint") or finding.get("url") or finding.get("affected_target") or "unknown")
        vuln_type = str(finding.get("vuln_type") or finding.get("type") or finding.get("title") or "vulnerability")
        severity = str(finding.get("severity") or "info").lower()
        endpoint_node = KGNode(NodeKind.ENDPOINT, endpoint, {"scan_id": scan_id})
        vuln_node = KGNode(NodeKind.VULNERABILITY, vuln_type, {"scan_id": scan_id, "severity": severity})
        finding_node = KGNode(NodeKind.FINDING, str(finding.get("id") or stable_id(scan_id, endpoint, vuln_type)), {"scan_id": scan_id, **finding})
        self.link(endpoint_node, vuln_node, EdgeKind.HAS_VULN, weight=_severity_weight(severity))
        self.link(vuln_node, finding_node, EdgeKind.VALIDATES, weight=_severity_weight(severity))
        return finding_node

    def ingest_http_record(self, record: Any, *, scan_id: str = "GLOBAL") -> None:
        url = getattr(record, "url", "") or record.get("url", "")
        status = getattr(record, "status", 0) if not isinstance(record, dict) else record.get("status", 0)
        method = getattr(record, "method", "") if not isinstance(record, dict) else record.get("method", "")
        endpoint = KGNode(NodeKind.ENDPOINT, str(url), {"scan_id": scan_id, "method": method, "status": status})
        self.upsert_node(endpoint)
        if status in {401, 403}:
            self.link(endpoint, KGNode(NodeKind.AUTH_SCHEME, "auth_required", {"scan_id": scan_id}), EdgeKind.AUTHENTICATED_BY)

    def plan_attack_paths(self, *, max_depth: int = 5) -> list[list[KGNode]]:
        paths: list[list[KGNode]] = []
        starts = [node for node in self.nodes.values() if node.kind in {NodeKind.VULNERABILITY, NodeKind.FINDING}]
        adjacency: dict[str, list[str]] = {}
        for edge in self.edges.values():
            if edge.kind in {EdgeKind.LEADS_TO, EdgeKind.PIVOTS_TO, EdgeKind.ESCALATES_TO, EdgeKind.EXPLOITS, EdgeKind.HAS_VULN}:
                adjacency.setdefault(edge.src_id, []).append(edge.dst_id)

        def walk(node_id: str, path: list[str]) -> None:
            if len(path) >= max_depth or node_id not in adjacency:
                if len(path) > 1:
                    paths.append([self.nodes[item] for item in path if item in self.nodes])
                return
            for nxt in adjacency.get(node_id, []):
                if nxt not in path:
                    walk(nxt, [*path, nxt])

        for start in starts:
            walk(start.id, [start.id])
        return sorted(paths, key=len, reverse=True)

    def bulk_upsert(self, nodes: Iterable[KGNode], edges: Iterable[KGEdge]) -> None:
        for node in nodes:
            self.upsert_node(node)
        for edge in edges:
            self.upsert_edge(edge)

    def stats(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for node in self.nodes.values():
            counts[node.kind.value] = counts.get(node.kind.value, 0) + 1
        return {"nodes": len(self.nodes), "edges": len(self.edges), "by_kind": counts}


def _severity_weight(severity: str) -> float:
    return {
        "critical": 10.0,
        "high": 7.5,
        "medium": 5.0,
        "low": 2.5,
        "informational": 1.0,
        "info": 1.0,
    }.get(severity.lower(), 1.0)


knowledge_graph = KnowledgeGraph()
