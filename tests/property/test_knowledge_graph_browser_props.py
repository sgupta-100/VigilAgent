"""
Property-based tests for the unified knowledge graph browser extension.

Covers spec ``deep-system-integration`` tasks 11.3, 11.5, 11.7 — the
browser discovery / HTTP-browser linking / unified context contracts on
``BrowserKnowledgeGraphExtension`` (the ``.browser`` view of
``UnifiedKnowledgeGraph``).

Architecture invariants honoured here:
  §9   scope-is-law       — URLs are evidence only; the extension never
                            grants scope. Tests use opaque
                            ``https://example.com/...`` URLs and never
                            touch the scope module.
  §17  ≥2-signal advisory — these read methods do NOT re-verify findings;
                            they describe graph topology only.

All tests build a *fresh* ``KnowledgeGraph`` per example so the global
singleton in ``backend.core.unified_knowledge_graph`` stays clean across
the suite.
"""
from __future__ import annotations

import string
from typing import Any, Dict

import pytest
from hypothesis import given, settings, strategies as st

from backend.core.unified_knowledge_graph import (
    BrowserKnowledgeGraphExtension,
    EdgeKind,
    KGNode,
    KnowledgeGraph,
    NodeKind,
    stable_id,
)


# ----------------------------------------------------------------------
# Strategies
# ----------------------------------------------------------------------
# URL paths constrained to a tiny alphabet so we never trip on URL
# parsers; the BrowserKnowledgeGraphExtension treats URLs as opaque
# labels, but keeping them simple makes counter-examples readable.
_url_path = st.text(alphabet=string.ascii_lowercase + string.digits + "/", min_size=1, max_size=20)


@st.composite
def url_strategy(draw) -> str:
    return "https://example.com/" + draw(_url_path)


# Discovery types accepted by the extension's ``_TYPE_MAP``. Keep to the
# canonical tokens (Architecture §12) so each kind is exercised.
_discovery_type = st.sampled_from(["endpoint", "route", "websocket"])


# Reserved keys that ``add_browser_discovery`` either overrides or maps
# specially — exclude from generated metadata so the round-trip
# assertion has a stable contract.
_RESERVED_META_KEYS = {
    "type", "scan_id", "source", "url",
    "framework", "route_pattern", "protocol",
}


@st.composite
def metadata_strategy(draw) -> Dict[str, Any]:
    keys = st.text(
        alphabet=string.ascii_lowercase + "_",
        min_size=3, max_size=10,
    ).filter(lambda k: k not in _RESERVED_META_KEYS)
    values = st.one_of(
        st.text(min_size=0, max_size=20),
        st.integers(min_value=-1000, max_value=1000),
        st.booleans(),
    )
    return draw(st.dictionaries(keys=keys, values=values, min_size=0, max_size=4))


def _fresh_extension() -> BrowserKnowledgeGraphExtension:
    """Build an isolated graph + extension pair (no global state)."""
    return BrowserKnowledgeGraphExtension(KnowledgeGraph())


# ----------------------------------------------------------------------
# Property 23 — Discovery Source Tagging  (Task 11.3 / Req 7.1, 7.2, 7.5)
# ----------------------------------------------------------------------
class TestDiscoverySourceTagging:
    """**Validates: Requirements 7.1, 7.2, 7.5**

    Property 23 — every node produced by ``add_browser_discovery`` is tagged
    with ``source == "browser_recon"`` AND every caller-supplied metadata
    key/value round-trips into ``node.props`` unchanged.
    """

    @settings(max_examples=20, deadline=None)
    @given(
        url=url_strategy(),
        dtype=_discovery_type,
        scan_id=st.text(alphabet=string.ascii_letters, min_size=1, max_size=10),
        metadata=metadata_strategy(),
    )
    def test_discovery_source_and_metadata_roundtrip(
        self, url: str, dtype: str, scan_id: str, metadata: Dict[str, Any]
    ) -> None:
        ext = _fresh_extension()
        discovery: Dict[str, Any] = {"type": dtype, "url": url, **metadata}

        node_id = ext.add_browser_discovery(discovery, scan_id=scan_id)
        node = ext.graph.nodes[node_id]

        # Core invariant: source is forcibly tagged + metadata round-trips.
        assert node.props["source"] == "browser_recon", (
            f"expected source=browser_recon, got {node.props.get('source')!r}"
        )
        for key, value in metadata.items():
            assert node.props.get(key) == value, (
                f"metadata roundtrip failed for {key!r}: "
                f"expected {value!r}, got {node.props.get(key)!r}"
            )


# ----------------------------------------------------------------------
# Property 24 — HTTP-Browser Endpoint Linking  (Task 11.5 / Req 7.3, 7.4)
# ----------------------------------------------------------------------
class TestHttpBrowserEndpointLinking:
    """**Validates: Requirements 7.3, 7.4**

    Property 24 — ``link_http_browser_endpoints`` is idempotent: calling it
    multiple times for the same (http_id, browser_id) pair yields exactly
    one ``HTTP_EQUIVALENT`` edge. This is the deduplication contract that
    keeps the knowledge graph from growing duplicate links when the same
    discovery is replayed across scans.
    """

    @settings(max_examples=20, deadline=None)
    @given(url=url_strategy())
    def test_link_is_idempotent(self, url: str) -> None:
        ext = _fresh_extension()
        graph = ext.graph

        # Manually upsert HTTP and browser endpoint nodes at the same URL.
        # Doing it manually (rather than via add_browser_discovery, which
        # would auto-link) lets us count edges before/after the explicit
        # link calls.
        http_node = graph.upsert_node(
            KGNode(NodeKind.ENDPOINT, url, {"scan_id": "S1", "method": "GET"})
        )
        browser_node = graph.upsert_node(
            KGNode(NodeKind.BROWSER_ENDPOINT, url, {"scan_id": "S1", "source": "browser_recon"})
        )
        assert len(graph.edges) == 0

        # First call creates exactly one HTTP_EQUIVALENT edge.
        ext.link_http_browser_endpoints(http_node.id, browser_node.id)
        edges_after_first = len(graph.edges)

        # Subsequent calls must not duplicate the edge (idempotent).
        ext.link_http_browser_endpoints(http_node.id, browser_node.id)
        ext.link_http_browser_endpoints(http_node.id, browser_node.id)
        edges_after_repeat = len(graph.edges)

        # Core invariant: edge count stays at 1 across all repeats AND
        # the edge is of kind HTTP_EQUIVALENT.
        assert edges_after_first == 1
        assert edges_after_repeat == edges_after_first, (
            f"link is not idempotent: edges grew from {edges_after_first} "
            f"to {edges_after_repeat}"
        )
        kinds = {e.kind for e in graph.edges.values()}
        assert kinds == {EdgeKind.HTTP_EQUIVALENT}


# ----------------------------------------------------------------------
# Property 25 — Unified Endpoint Context  (Task 11.7 / Req 7.6)
# ----------------------------------------------------------------------
class TestUnifiedEndpointContext:
    """**Validates: Requirements 7.6**

    Property 25 — when both an HTTP discovery and a browser discovery exist
    at the same URL, ``get_endpoint_context(url)`` returns BOTH context
    payloads (i.e. ``http`` and ``browser`` are simultaneously non-None).
    This is the contract that lets agents query a single URL and receive
    the union of HTTP-recon and browser-recon evidence.
    """

    @settings(max_examples=20, deadline=None)
    @given(
        url=url_strategy(),
        scan_id=st.text(alphabet=string.ascii_letters, min_size=1, max_size=10),
    )
    def test_get_endpoint_context_returns_both_views(
        self, url: str, scan_id: str
    ) -> None:
        ext = _fresh_extension()
        graph = ext.graph

        # 1. Seed an HTTP-side discovery at this URL.
        graph.upsert_node(
            KGNode(NodeKind.ENDPOINT, url, {"scan_id": scan_id, "method": "GET", "status": 200})
        )
        # 2. Seed a browser-side discovery at the same URL — this also
        #    auto-links to the HTTP twin via add_browser_discovery.
        ext.add_browser_discovery({"type": "endpoint", "url": url}, scan_id=scan_id)

        ctx = ext.get_endpoint_context(url)

        # Core invariant: BOTH http and browser context are populated.
        assert ctx["http"] is not None, "http context missing despite HTTP node present"
        assert ctx["browser"] is not None, "browser context missing despite browser node present"
        # Browser context must carry the recon provenance tag (§9 compliance).
        assert ctx["browser"].get("source") == "browser_recon"
