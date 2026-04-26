from __future__ import annotations

import argparse
from pathlib import Path

from src.config import load_config
from src.crawler import OnionCrawler
from src.graph_builder import GraphBuilder
from src.policy import CrawlPolicy
from src.seed_manager import SeedManager
from src.storage import Storage
from src.tor_fetcher import TorFetcher
from src.visualizer import Visualizer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Temporal Onion Graph MVP"
    )
    parser.add_argument(
        "--config",
        default="config/settings.yaml",
        help="Path to settings.yaml",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db")

    p_import = sub.add_parser("import-seeds")
    p_import.add_argument("--seeds", default="data/seeds.txt")
    p_import.add_argument("--origin", default="manual_hidden_wiki")

    p_crawl = sub.add_parser("crawl")
    p_crawl.add_argument("--max-pages", type=int, default=None)
    p_crawl.add_argument("--max-depth", type=int, default=None)

    p_export = sub.add_parser("export-graph")
    p_export.add_argument("--level", choices=["page", "service"], default="service")

    p_vis = sub.add_parser("visualize")
    p_vis.add_argument("--level", choices=["page", "service"], default="service")
    p_vis.add_argument("--max-nodes", type=int, default=1000)

    p_stats = sub.add_parser("stats")

    return parser


def cmd_stats(storage: Storage) -> None:
    stats = {
        "services": storage.query("SELECT COUNT(*) AS c FROM services")[0]["c"],
        "pages": storage.query("SELECT COUNT(*) AS c FROM pages")[0]["c"],
        "snapshots": storage.query("SELECT COUNT(*) AS c FROM snapshots")[0]["c"],
        "links": storage.query("SELECT COUNT(*) AS c FROM links")[0]["c"],
        "queue_pending": storage.query("SELECT COUNT(*) AS c FROM crawl_queue WHERE status='pending'")[0]["c"],
        "queue_done": storage.query("SELECT COUNT(*) AS c FROM crawl_queue WHERE status='done'")[0]["c"],
        "queue_failed": storage.query("SELECT COUNT(*) AS c FROM crawl_queue WHERE status='failed'")[0]["c"],
        "events": storage.query("SELECT COUNT(*) AS c FROM events")[0]["c"],
    }

    for k, v in stats.items():
        print(f"{k}: {v}")


def main() -> None:
    args = build_parser().parse_args()
    config = load_config(args.config)

    Path(config.export_dir).mkdir(parents=True, exist_ok=True)
    Path(config.log_dir).mkdir(parents=True, exist_ok=True)
    Path(config.database_path).parent.mkdir(parents=True, exist_ok=True)

    storage = Storage(config.database_path)

    try:
        if args.command == "init-db":
            storage.init_db()
            print(f"Initialized DB: {config.database_path}")

        elif args.command == "import-seeds":
            storage.init_db()
            policy = CrawlPolicy(config.policy)
            manager = SeedManager(storage, policy)
            count = manager.import_seeds(args.seeds, seed_origin=args.origin)
            print(f"Imported seeds: {count}")

        elif args.command == "crawl":
            storage.init_db()
            policy = CrawlPolicy(config.policy)
            fetcher = TorFetcher(config.tor, policy)
            crawler = OnionCrawler(storage, fetcher, policy)
            crawler.crawl(max_pages=args.max_pages, max_depth=args.max_depth)
            print("Crawl finished.")

        elif args.command == "export-graph":
            storage.init_db()
            builder = GraphBuilder(storage)
            paths = builder.export_graph(level=args.level, export_dir=config.export_dir)
            for name, path in paths.items():
                print(f"{name}: {path}")

        elif args.command == "visualize":
            storage.init_db()
            builder = GraphBuilder(storage)
            visualizer = Visualizer(builder)
            out = Path(config.export_dir) / f"{args.level}_interactive.html"
            path = visualizer.export_interactive_html(
                level=args.level,
                output_path=out,
                max_nodes=args.max_nodes,
            )
            print(f"interactive_html: {path}")

        elif args.command == "stats":
            storage.init_db()
            cmd_stats(storage)

    finally:
        storage.close()


if __name__ == "__main__":
    main()