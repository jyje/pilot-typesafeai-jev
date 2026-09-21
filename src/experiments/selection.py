"""Which configs go on to the main stage. The rule uses availability, never accuracy.

Picking finalists by accuracy on the same messages would flatter them. A config passes when it was
screened on the whole set of messages, enough of its calls returned a usable answer, and it answers
fast enough to run at scale. The rule applies to Jev too. Every screened config still appears in the
results, passing or not.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from collections.abc import Iterable

MIN_VALID_RATE = 0.90
MAX_MEDIAN_LATENCY_S = 60.0
MIN_SCREEN_MESSAGES = 31  # a configuration must be screened on the whole screen set to pass


def screen_summary(rows: Iterable[dict]) -> dict[str, dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["label"]].append(row)
    summary = {}
    for label, group in grouped.items():
        messages = len({r["item_id"] for r in group})
        valid = [r for r in group if not r.get("error_kind")]
        latencies = [r["latency_s"] for r in valid]
        rate = len(valid) / len(group)
        median = statistics.median(latencies) if latencies else float("inf")
        summary[label] = {
            "calls": len(group),
            "messages": messages,
            "valid_rate": rate,
            "median_latency_s": median,
            # A few messages can show that a configuration fails, but never that it passes.
            "passes": (
                messages >= MIN_SCREEN_MESSAGES
                and rate >= MIN_VALID_RATE
                and median <= MAX_MEDIAN_LATENCY_S
            ),
        }
    return summary


def passing_labels(rows: Iterable[dict]) -> list[str]:
    return sorted(label for label, s in screen_summary(rows).items() if s["passes"])
