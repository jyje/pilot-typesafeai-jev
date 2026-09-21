"""One row per classification, appended to a JSONL file as it finishes, so a stopped run resumes."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

Key = tuple[str, str, str, int]  # (stage, engine label, item id, repeat)
RETRYABLE_KINDS = frozenset({"provider", "timeout"})


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


# Diagnostics worth keeping from a failed call. Everything else in an error message (a response
# body, a request id, a piece of the model's output) stays out of the versioned data.
KNOWN_TAGS = (
    "usage_limit_reached",
    "insufficient_quota",
    "overloaded",
    "guided_json",
    "ResourceExhausted",
)
_STATUS = re.compile(r"\[(\d{3})\]|Error code: (\d{3})|HTTP (\d{3})")
_PARSE = "parse: output was not valid structured data"
_CLEAN = re.compile(rf"\w+(?: HTTP \d{{3}})?(?: (?:{'|'.join(KNOWN_TAGS)}))*")


def clean_error(kind: str | None, text: str | None) -> str | None:
    """Reduce an error message to what is safe and useful to publish.

    Provider errors and timeouts keep the exception class, the HTTP status, and any known tag. A
    parse failure loses the model's output. A schema failure keeps only which field was wrong.
    """
    if not kind or not text:
        return None
    if kind == "parse":
        return _PARSE
    if kind == "schema":
        return "schema: " + text.removeprefix("schema: ").split(":", 1)[0][:80]
    if ":" not in text:
        # Already clean only if it has exactly the shape this function writes.
        return text if _CLEAN.fullmatch(text) else "Error"
    name = text.split(":", 1)[0].strip()
    parts = [name if re.fullmatch(r"\w+", name) else "Error"]
    if match := _STATUS.search(text):
        parts.append("HTTP " + next(g for g in match.groups() if g))
    parts += [tag for tag in KNOWN_TAGS if tag.lower() in text.lower()]
    return " ".join(parts)


def clean_row(row: dict) -> dict:
    """The same reduction for a row already written, and a fix for one mislabelled error.

    An intent that was not a string raised `TypeError` and was recorded as a provider error. It is a
    reply that failed the schema, so it is relabelled.
    """
    out = dict(row)
    if (out.get("error") or "").startswith("TypeError: unhashable type"):
        out["error_kind"], out["error"] = "schema", "schema: intent is not a string"
        return out
    out["error"] = clean_error(out.get("error_kind"), out.get("error"))
    return out


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
        """Keys to skip on a rerun. With `retry_errors`, failed calls of the infrastructure kind
        (`provider` and `timeout`: a 429, a 503, a timeout) count as not done, and a later success
        for the same key makes it done again. A reply that failed the schema (`parse`, `schema`)
        is what the model answered, so it is a result and is never retried."""
        keys: set[Key] = set()
        for row in self.read():
            if retry_errors and row.get("error_kind") in RETRYABLE_KINDS:
                continue
            keys.add((row["stage"], row["label"], row["item_id"], row["repeat"]))
        return keys

    async def append(self, record: Record) -> None:
        line = json.dumps(asdict(record), ensure_ascii=False)
        async with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
