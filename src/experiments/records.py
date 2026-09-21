"""One row per classification, appended to a JSONL file as it finishes, so a stopped run resumes."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from pathlib import Path

Key = tuple[str, str, str, int]  # (stage, engine label, item id, repeat)


@dataclass
class Record:
    stage: str
    label: str
    engine: str
    model: str
    setting: str
    item_id: str
    repeat: int
    started_at: float
    latency_s: float
    intent: str | None = None
    intent_confidence: float | None = None
    urgency: float | None = None
    injection: float | None = None
    route: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    error_kind: str | None = None  # "parse", "schema", "timeout", or "provider"
    error: str | None = None

    @property
    def key(self) -> Key:
        return (self.stage, self.label, self.item_id, self.repeat)

    @property
    def ok(self) -> bool:
        return self.error_kind is None


class Store:
    """Append-only JSONL. `done()` lets a rerun skip rows that already succeeded."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = asyncio.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)

    def read(self) -> list[dict]:
        if not self.path.is_file():
            return []
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def done(self, *, retry_errors: bool = False) -> set[Key]:
        keys: set[Key] = set()
        for row in self.read():
            if retry_errors and row.get("error_kind"):
                continue
            keys.add((row["stage"], row["label"], row["item_id"], row["repeat"]))
        return keys

    async def append(self, record: Record) -> None:
        line = json.dumps(asdict(record), ensure_ascii=False)
        async with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
