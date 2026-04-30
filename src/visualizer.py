from __future__ import annotations

from pathlib import Path

from pyvis.network import Network

from src.graph_builder import GraphBuilder


class Visualizer:
    def __init__(self, graph_builder: GraphBuilder):
        self.graph_builder = graph_builder

    def export_interactive_html(
        self,
        level: str,
        output_path: str | Path,
        max_nodes: int = 1000,
    ) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if level == "page":
            g = self.graph_builder.build_page_graph()
        elif level == "service":
            g = self.graph_builder.build_service_graph()
        else:
            raise ValueError("level must be either 'page' or 'service'")

        if g.number_of_nodes() > max_nodes:
            ranked = sorted(
                g.nodes(data=True),
                key=lambda x: float(x[1].get("pagerank", 0.0)),
                reverse=True,
            )
            keep = {n for n, _ in ranked[:max_nodes]}
            g = g.subgraph(keep).copy()

        net = Network(
            height="850px",
            width="100%",
            directed=True,
            notebook=False,
            bgcolor="#ffffff",
            font_color="#222222",
            # local は lib/ への相対パスを出力するため、Vercel 上で iframe(srcDoc)
            # 埋め込み時に https://*.vercel.app/lib/... が 404 になり描画できない。
            # remote は bindings をインライン化し vis を CDN から読むため埋め込みに適する。
            cdn_resources="remote",
        )

        for node, attrs in g.nodes(data=True):
            label = node[:24] + "..." if len(node) > 27 else node
            pagerank = float(attrs.get("pagerank", 0.0))
            in_degree = int(attrs.get("in_degree", 0))
            out_degree = int(attrs.get("out_degree", 0))

            size = 10 + min(40, pagerank * 1000 + in_degree)

            title = (
                f"id: {node}<br>"
                f"in_degree: {in_degree}<br>"
                f"out_degree: {out_degree}<br>"
                f"pagerank: {pagerank:.6f}"
            )

            net.add_node(
                node,
                label=label,
                title=title,
                size=size,
            )

        for source, target, attrs in g.edges(data=True):
            weight = int(attrs.get("weight", 1))
            net.add_edge(source, target, value=weight, title=f"weight: {weight}")

        net.force_atlas_2based()
        net.write_html(str(output_path), notebook=False)
        return output_path