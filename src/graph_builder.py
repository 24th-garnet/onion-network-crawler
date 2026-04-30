from __future__ import annotations

from pathlib import Path

import networkx as nx
import pandas as pd

from src.normalizer import normalize_url, onion_host_from_url
from src.storage import Storage


class GraphBuilder:
    def __init__(self, storage: Storage):
        self.storage = storage

    def _iter_seed_normalized(self):
        """depth=0 のキュー行は import-seeds で投入された初期 seed。"""
        rows = self.storage.query(
            """
            SELECT url FROM crawl_queue WHERE depth = 0
            """
        )
        seen: set[str] = set()
        for r in rows:
            nu = normalize_url(r["url"])
            if nu is None:
                continue
            if nu.normalized_url in seen:
                continue
            seen.add(nu.normalized_url)
            yield nu

    def _merge_seed_nodes_page(self, g: nx.DiGraph) -> None:
        for nu in self._iter_seed_normalized():
            if nu.normalized_url in g:
                g.nodes[nu.normalized_url]["is_seed"] = True
            else:
                g.add_node(
                    nu.normalized_url,
                    type="page",
                    onion_host=nu.onion_host,
                    is_seed=True,
                )

    def _merge_seed_nodes_service(self, g: nx.DiGraph) -> None:
        for nu in self._iter_seed_normalized():
            if not nu.onion_host:
                continue
            host = nu.onion_host
            if host in g:
                g.nodes[host]["is_seed"] = True
            else:
                g.add_node(host, type="service", is_seed=True)

    def build_page_graph(self) -> nx.DiGraph:
        g = nx.DiGraph()

        rows = self.storage.query(
            """
            SELECT source_url, target_url, target_onion_host, observed_at
            FROM links
            """
        )

        for r in rows:
            source = r["source_url"]
            target = r["target_url"]

            g.add_node(source, type="page", onion_host=onion_host_from_url(source))
            g.add_node(target, type="page", onion_host=onion_host_from_url(target))

            if g.has_edge(source, target):
                g[source][target]["weight"] += 1
            else:
                g.add_edge(
                    source,
                    target,
                    weight=1,
                    observed_at=r["observed_at"],
                    target_onion_host=r["target_onion_host"],
                )

        self._merge_seed_nodes_page(g)
        self._add_metrics(g)
        return g

    def build_service_graph(self) -> nx.DiGraph:
        g = nx.DiGraph()

        rows = self.storage.query(
            """
            SELECT source_url, target_url, target_onion_host, observed_at
            FROM links
            WHERE target_onion_host IS NOT NULL
            """
        )

        for r in rows:
            source_host = onion_host_from_url(r["source_url"])
            target_host = r["target_onion_host"]

            if not source_host or not target_host:
                continue

            if source_host == target_host:
                continue

            g.add_node(source_host, type="service")
            g.add_node(target_host, type="service")

            if g.has_edge(source_host, target_host):
                g[source_host][target_host]["weight"] += 1
            else:
                g.add_edge(
                    source_host,
                    target_host,
                    weight=1,
                    observed_at=r["observed_at"],
                )

        self._merge_seed_nodes_service(g)
        self._add_metrics(g)
        return g

    def _add_metrics(self, g: nx.DiGraph) -> None:
        in_deg = dict(g.in_degree())
        out_deg = dict(g.out_degree())

        nx.set_node_attributes(g, in_deg, "in_degree")
        nx.set_node_attributes(g, out_deg, "out_degree")

        if g.number_of_nodes() > 0 and g.number_of_edges() > 0:
            try:
                pagerank = nx.pagerank(g, weight="weight")
            except Exception:
                pagerank = {n: 0.0 for n in g.nodes}
        elif g.number_of_nodes() > 0 and g.number_of_edges() == 0:
            pagerank = {n: 1.0 / g.number_of_nodes() for n in g.nodes}
        else:
            pagerank = {n: 0.0 for n in g.nodes}

        nx.set_node_attributes(g, pagerank, "pagerank")

    def export_graph(
        self,
        level: str,
        export_dir: str | Path,
    ) -> dict[str, Path]:
        export_dir = Path(export_dir)
        export_dir.mkdir(parents=True, exist_ok=True)

        if level == "page":
            g = self.build_page_graph()
        elif level == "service":
            g = self.build_service_graph()
        else:
            raise ValueError("level must be either 'page' or 'service'")

        nodes_csv = export_dir / f"{level}_nodes.csv"
        edges_csv = export_dir / f"{level}_edges.csv"
        gexf_path = export_dir / f"{level}_graph.gexf"
        graphml_path = export_dir / f"{level}_graph.graphml"

        nodes = []
        for node, attrs in g.nodes(data=True):
            row = {"id": node}
            row.update(attrs)
            nodes.append(row)

        edges = []
        for source, target, attrs in g.edges(data=True):
            row = {"source": source, "target": target}
            row.update(attrs)
            edges.append(row)

        pd.DataFrame(nodes).to_csv(nodes_csv, index=False)
        pd.DataFrame(edges).to_csv(edges_csv, index=False)

        nx.write_gexf(g, gexf_path)
        nx.write_graphml(g, graphml_path)

        return {
            "nodes_csv": nodes_csv,
            "edges_csv": edges_csv,
            "gexf": gexf_path,
            "graphml": graphml_path,
        }