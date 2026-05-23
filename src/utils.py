from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dir(path: str | Path) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def load_json(path: str | Path, default: Any) -> Any:
    p = Path(path)
    if not p.exists():
        return default
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str | Path, data: Any) -> None:
    ensure_dir(Path(path).parent)
    with Path(path).open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def text_hash(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()[:24]


def getenv_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def normalize_title(title: str) -> str:
    t = (title or "").strip()
    t = re.sub(r"\s+-\s+[^-]+$", "", t)
    t = re.sub(r"\[[^\]]+\]", "", t)
    t = re.sub(r"\([^\)]*특징주[^\)]*\)", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+", " ", t).strip().lower()
    return t


def prune_timestamp_map(items: dict[str, str], retention_days: int) -> dict[str, str]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    kept: dict[str, str] = {}
    for key, value in items.items():
        try:
            dt = datetime.fromisoformat(value)
            if dt >= cutoff:
                kept[key] = value
        except Exception:
            continue
    return kept
