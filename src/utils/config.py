from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

def get_project_root() -> Path:
    return Path(__file__).resolve().parents[2]

def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    root = get_project_root()
    load_dotenv(root / ".env", override=True)

    path = Path(config_path) if config_path else root / "config.yaml"
    with path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    config["_root"] = str(root)
    return config
