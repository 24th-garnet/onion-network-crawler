from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class TorConfig:
    proxy_url: str
    request_timeout_sec: int
    max_retries: int
    retry_sleep_sec: int
    user_agent: str


@dataclass(frozen=True)
class PolicyConfig:
    max_depth: int
    max_pages: int
    max_response_bytes: int
    same_host_delay_sec: int
    allowed_schemes: list[str]
    allowed_content_types: list[str]
    skip_extensions: list[str]


@dataclass(frozen=True)
class AppConfig:
    database_path: Path
    export_dir: Path
    log_dir: Path
    tor: TorConfig
    policy: PolicyConfig


def load_config(path: str | Path) -> AppConfig:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f)

    tor_raw = raw["tor"]
    policy_raw = raw["policy"]

    return AppConfig(
        database_path=Path(raw["database_path"]),
        export_dir=Path(raw["export_dir"]),
        log_dir=Path(raw["log_dir"]),
        tor=TorConfig(
            proxy_url=str(tor_raw["proxy_url"]),
            request_timeout_sec=int(tor_raw["request_timeout_sec"]),
            max_retries=int(tor_raw["max_retries"]),
            retry_sleep_sec=int(tor_raw["retry_sleep_sec"]),
            user_agent=str(tor_raw["user_agent"]),
        ),
        policy=PolicyConfig(
            max_depth=int(policy_raw["max_depth"]),
            max_pages=int(policy_raw["max_pages"]),
            max_response_bytes=int(policy_raw["max_response_bytes"]),
            same_host_delay_sec=int(policy_raw["same_host_delay_sec"]),
            allowed_schemes=list(policy_raw["allowed_schemes"]),
            allowed_content_types=list(policy_raw["allowed_content_types"]),
            skip_extensions=list(policy_raw["skip_extensions"]),
        ),
    )