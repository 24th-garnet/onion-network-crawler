from __future__ import annotations

import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
READONLY_SETTINGS_PATH = ROOT_DIR / "config" / "settings.yaml"
READONLY_SEEDS_PATH = ROOT_DIR / "data" / "seeds.txt"
RUNTIME_ROOT = Path("/tmp/onionnetwork-runtime")
RUNTIME_DATA_DIR = RUNTIME_ROOT / "data"
RUNTIME_EXPORT_DIR = RUNTIME_DATA_DIR / "exports"
RUNTIME_LOG_DIR = RUNTIME_ROOT / "logs"
RUNTIME_DB_PATH = RUNTIME_DATA_DIR / "onion_graph.db"
RUNTIME_SETTINGS_PATH = RUNTIME_ROOT / "settings.yaml"
RUNTIME_SEEDS_PATH = RUNTIME_DATA_DIR / "seeds.txt"
VISUALIZATION_PATH = RUNTIME_EXPORT_DIR / "service_interactive.html"

STEP_PLAN = [
    ("reset", "既存データをリセット", 15),
    ("init", "DB初期化", 30),
    ("import", "seeds投入(hidden wiki)", 45),
    ("crawl", "クロール実行", 75),
    ("export", "グラフ出力", 88),
    ("visualize", "可視化HTML生成", 96),
]


@dataclass
class CrawlJob:
    id: str
    status: str
    progress: int
    message: str
    logs: list[str] = field(default_factory=list)
    visualizationHtml: str | None = None
    startedAt: str = ""
    finishedAt: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "logs": self.logs,
            "visualizationHtml": self.visualizationHtml,
            "startedAt": self.startedAt,
            "finishedAt": self.finishedAt,
            "error": self.error,
        }


_current_job: CrawlJob | None = None
_lock = threading.Lock()


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _set_step(job: CrawlJob, step_key: str) -> None:
    for key, label, progress in STEP_PLAN:
        if key == step_key:
            job.progress = progress
            job.message = label
            return


def _reset_runtime_state() -> None:
    for db_file in [RUNTIME_DB_PATH, Path(f"{RUNTIME_DB_PATH}-shm"), Path(f"{RUNTIME_DB_PATH}-wal")]:
        if db_file.exists():
            db_file.unlink()

    for directory in [RUNTIME_EXPORT_DIR, RUNTIME_LOG_DIR]:
        if directory.exists():
            for p in sorted(directory.rglob("*"), reverse=True):
                if p.is_file():
                    p.unlink()
                else:
                    p.rmdir()
            directory.rmdir()

    RUNTIME_DATA_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_LOG_DIR.mkdir(parents=True, exist_ok=True)


def _prepare_runtime_files() -> None:
    settings_raw = READONLY_SETTINGS_PATH.read_text(encoding="utf-8")
    runtime_settings = settings_raw
    runtime_settings = runtime_settings.replace(
        'database_path: "data/onion_graph.db"',
        f'database_path: "{RUNTIME_DB_PATH}"',
    )
    runtime_settings = runtime_settings.replace(
        'export_dir: "data/exports"',
        f'export_dir: "{RUNTIME_EXPORT_DIR}"',
    )
    runtime_settings = runtime_settings.replace(
        'log_dir: "logs"',
        f'log_dir: "{RUNTIME_LOG_DIR}"',
    )

    RUNTIME_SETTINGS_PATH.write_text(runtime_settings, encoding="utf-8")
    RUNTIME_SEEDS_PATH.write_text(READONLY_SEEDS_PATH.read_text(encoding="utf-8"), encoding="utf-8")


def _run_runtime_command(command: str, extra_args: list[str] | None = None) -> str:
    args = [
        "python",
        "-m",
        "src.main",
        "--config",
        str(RUNTIME_SETTINGS_PATH),
        command,
    ]
    if extra_args:
        args.extend(extra_args)
    completed = subprocess.run(
        args,
        cwd=str(ROOT_DIR),
        text=True,
        capture_output=True,
        check=True,
    )
    return "\n".join(part for part in [" ".join(args), completed.stdout.strip(), completed.stderr.strip()] if part)


def _run_sequence(job: CrawlJob) -> None:
    try:
        _set_step(job, "reset")
        _reset_runtime_state()
        _prepare_runtime_files()

        _set_step(job, "init")
        job.logs.append(_run_runtime_command("init-db"))

        _set_step(job, "import")
        job.logs.append(_run_runtime_command("import-seeds", ["--seeds", str(RUNTIME_SEEDS_PATH)]))

        _set_step(job, "crawl")
        job.logs.append(_run_runtime_command("crawl"))

        _set_step(job, "export")
        job.logs.append(_run_runtime_command("export-graph", ["--level", "service"]))

        _set_step(job, "visualize")
        job.logs.append(_run_runtime_command("visualize", ["--level", "service", "--max-nodes", "500"]))

        job.visualizationHtml = VISUALIZATION_PATH.read_text(encoding="utf-8")
        job.progress = 100
        job.status = "done"
        job.message = "可視化まで完了しました"
        job.finishedAt = _utc_now()
    except subprocess.CalledProcessError as exc:
        job.status = "error"
        job.message = "処理が失敗しました"
        job.error = "\n".join(part for part in [str(exc), exc.stdout, exc.stderr] if part).strip()
        job.finishedAt = _utc_now()
    except Exception as exc:  # noqa: BLE001
        job.status = "error"
        job.message = "処理が失敗しました"
        job.error = str(exc)
        job.finishedAt = _utc_now()


def start_crawl_job() -> CrawlJob:
    global _current_job
    with _lock:
        if _current_job and _current_job.status == "running":
            return _current_job
        _current_job = CrawlJob(
            id=f"crawl-{int(time.time() * 1000)}",
            status="running",
            progress=5,
            message="ジョブを開始しました",
            startedAt=_utc_now(),
        )
        thread = threading.Thread(target=_run_sequence, args=(_current_job,), daemon=True)
        thread.start()
        return _current_job


def get_crawl_job() -> CrawlJob | None:
    return _current_job
