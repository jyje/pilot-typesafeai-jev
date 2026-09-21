"""Turn the JSONL rows into DataFrames, numbers, and figures. Needs the `analysis` extra.

Every function takes the long-format frame from `load()` (one row per classification) and returns a
frame or a figure, so a notebook and a script share the same numbers.

Uncertainty: messages, not repeats, are the unit of generalization, so confidence intervals come
from a bootstrap that resamples messages (with all of their repeats) and not single runs.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from experiments import dataset
from experiments.selection import MAX_MEDIAN_LATENCY_S, MIN_VALID_RATE, SCREEN_IDS

ROUTES = ["answer", "escalate", "review", "refuse"]
# A call the infrastructure failed (a 429, a 503, a timeout) says nothing about the model, so it is
# left out of accuracy and reported. A reply that failed the schema is the model's own miss.
INFRASTRUCTURE_KINDS = frozenset({"provider", "timeout"})


def load(paths: Iterable[Path]) -> pd.DataFrame:
    """Read JSONL files into one frame and add the expected route, group, and short names."""
    rows = [json.loads(line) for p in paths for line in p.read_text("utf-8").splitlines() if line]
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    items = pd.DataFrame(
        [(i.id, i.group, i.expected, i.expected_injection) for i in dataset.ALL_ITEMS],
        columns=["item_id", "group", "expected", "expected_injection"],
    )
    df = df.merge(items, on="item_id", how="left", validate="many_to_one")
    df["ok"] = df["error_kind"].isna()
    df["short"] = df["model"].str.split("/").str[-1] + "|" + df["setting"]
    df["hit"] = df["route"] == df["expected"]
    return df


def trim_repeats(df: pd.DataFrame, n: int) -> pd.DataFrame:
    """Keep repeats 1..n, so engines run a different number of times are compared on equal terms."""
    return df[df["repeat"] <= n]


def valid(df: pd.DataFrame) -> pd.DataFrame:
    """Calls that returned a usable answer."""
    return df[df["ok"]]


def terminal(df: pd.DataFrame) -> pd.DataFrame:
    """One row per logical run: its last attempt that was not an infrastructure failure.

    A run can have several rows, because a rerun redoes failures. Counting every row would count one
    run twice. If every attempt failed for infrastructure reasons, the last attempt stands in, and
    `scored` leaves it out.
    """
    key = ["stage", "label", "item_id", "repeat"]
    ordered = df.assign(_infra=df["error_kind"].isin(INFRASTRUCTURE_KINDS)).sort_values(
        [*key, "_infra", "started_at"], ascending=[True] * len(key) + [False, True]
    )
    return ordered.groupby(key, sort=False).tail(1).drop(columns="_infra")


def scored(df: pd.DataFrame) -> pd.DataFrame:
    """Runs counted in accuracy: usable answers, plus replies that failed the schema (as misses)."""
    t = terminal(df)
    return t[~t["error_kind"].isin(INFRASTRUCTURE_KINDS)]


def exclusions(df: pd.DataFrame) -> pd.DataFrame:
    """Per config: runs scored, replies counted as misses, and runs missing for infrastructure.

    A run is missing when every attempt at it failed for infrastructure reasons. A run that failed
    once and then succeeded on a rerun is not missing.
    """
    t = terminal(df)
    rows = []
    for label, g in t.groupby("label", sort=False):
        infra = g["error_kind"].isin(INFRASTRUCTURE_KINDS)
        rows.append(
            (
                label,
                int((~infra).sum()),
                int(g["error_kind"].isin({"parse", "schema"}).sum()),
                int(infra.sum()),
            )
        )
    return pd.DataFrame(rows, columns=["label", "scored", "bad_replies", "infrastructure_failures"])


def availability(df: pd.DataFrame) -> pd.DataFrame:
    """Per config: calls, usable share, speed, and whether it passes the screen rule.

    The rule needs the whole screen set of messages, nothing else, at least `MIN_VALID_RATE` usable
    calls, and a median latency of at most `MAX_MEDIAN_LATENCY_S`. It uses availability, not accuracy.
    """
    g = df.groupby("label", sort=False)
    out = pd.DataFrame(
        {
            "engine": g["engine"].first(),
            "calls": g.size(),
            "messages": g["item_id"].apply(lambda s: len(set(s) & SCREEN_IDS)),
            "valid_rate": g["ok"].mean(),
            "median_s": valid(df).groupby("label")["latency_s"].median(),
            "p95_s": valid(df).groupby("label")["latency_s"].quantile(0.95),
            "errors": g["error_kind"].agg(lambda s: dict(s.dropna().value_counts())),
        }
    )
    exact = g["item_id"].apply(lambda s: set(s) == SCREEN_IDS)
    out["passes"] = (
        exact & (out["valid_rate"] >= MIN_VALID_RATE) & (out["median_s"] <= MAX_MEDIAN_LATENCY_S)
    )
    return out.sort_values(["engine", "label"])


def majority(df: pd.DataFrame, column: str = "route") -> pd.DataFrame:
    """Per config and message: the most common answer and the share of runs that gave it."""
    v = valid(terminal(df))
    counts = v.groupby(["label", "item_id", column]).agg(n=("ok", "size")).reset_index()
    counts = counts.sort_values(
        ["label", "item_id", "n", column], ascending=[True, True, False, True]
    )
    top = counts.drop_duplicates(["label", "item_id"]).copy()
    top["mode"] = top[column]
    total = v.groupby(["label", "item_id"]).agg(runs=("ok", "size")).reset_index()
    out = top[["label", "item_id", "mode", "n"]].merge(total, on=["label", "item_id"])
    out["share"] = out["n"] / out["runs"]
    return out


def bootstrap_ci(
    values: pd.Series, item_ids: pd.Series, *, draws: int = 2000, seed: int = 7
) -> tuple[float, float, float]:
    """Mean of `values` and a 95% interval from resampling whole messages."""
    frame = pd.DataFrame({"v": values.to_numpy(dtype=float), "item": item_ids.to_numpy()})
    per_item = frame.groupby("item")["v"].mean().to_numpy()
    if len(per_item) == 0:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    means = rng.choice(per_item, size=(draws, len(per_item)), replace=True).mean(axis=1)
    lo, hi = np.quantile(means, [0.025, 0.975])
    return float(per_item.mean()), float(lo), float(hi)


def accuracy(df: pd.DataFrame, groups: Sequence[str] | None = None) -> pd.DataFrame:
    """Share of scored runs on the expected route, per config, with a message-level interval.

    A reply that failed the schema counts as a miss; an infrastructure failure is left out (see
    `exclusions`).
    """
    v = scored(df)
    if groups:
        v = v[v["group"].isin(groups)]
    rows = []
    for label, g in v.groupby("label", sort=False):
        mean, lo, hi = bootstrap_ci(g["hit"], g["item_id"])
        rows.append((label, g["engine"].iloc[0], g["short"].iloc[0], len(g), mean, lo, hi))
    return pd.DataFrame(rows, columns=["label", "engine", "short", "runs", "accuracy", "lo", "hi"])


def paired_versus_jev(
    df: pd.DataFrame, jev_label: str = "jev:jev:-", *, draws: int = 2000, seed: int = 7
) -> pd.DataFrame:
    """Each config's accuracy minus Jev's, message by message, with a paired bootstrap interval.

    Both engines answered the same messages, so the difference is taken per message and messages are
    resampled together. That detects a small, steady gap that two separate intervals would hide. A
    config is "better" or "worse" when the 95% interval of the difference excludes zero, otherwise
    "not distinguishable", which is no detected difference at this sample size, not equality.
    """
    per = analysis_per_message(df)
    if jev_label not in per.columns:
        return pd.DataFrame(
            columns=["label", "difference", "diff_lo", "diff_hi", "messages", "vs_jev"]
        )
    rng = np.random.default_rng(seed)
    rows = []
    for label in per.columns:
        if label == jev_label:
            continue
        gap = (per[label] - per[jev_label]).dropna().to_numpy(dtype=float)
        if len(gap) == 0:
            continue
        means = rng.choice(gap, size=(draws, len(gap)), replace=True).mean(axis=1)
        lo, hi = (float(x) for x in np.quantile(means, [0.025, 0.975]))
        verdict = "better" if lo > 0 else "worse" if hi < 0 else "not distinguishable"
        rows.append((label, float(gap.mean()), lo, hi, len(gap), verdict))
    return pd.DataFrame(
        rows, columns=["label", "difference", "diff_lo", "diff_hi", "messages", "vs_jev"]
    )


def analysis_per_message(df: pd.DataFrame) -> pd.DataFrame:
    """Share of scored runs on the expected route: one row per message, one column per config."""
    v = scored(df)
    return v.groupby(["item_id", "label"])["hit"].mean().unstack("label")


def consistency(df: pd.DataFrame) -> pd.DataFrame:
    """Mean share of runs agreeing with the message's most common route, per config."""
    m = majority(df)
    return m.groupby("label", sort=False)["share"].mean().rename("consistency").reset_index()


def cohen_kappa(a: Sequence[str], b: Sequence[str]) -> float:
    a, b = list(a), list(b)
    if not a:
        return float("nan")
    labels = sorted(set(a) | set(b))
    observed = sum(x == y for x, y in zip(a, b, strict=True)) / len(a)
    expected = sum((a.count(k) / len(a)) * (b.count(k) / len(b)) for k in labels)
    return 1.0 if expected == 1.0 else (observed - expected) / (1 - expected)


def agreement_with_jev(df: pd.DataFrame, jev_label: str = "jev:jev:-") -> pd.DataFrame:
    """Message-level agreement of each config's most common route with Jev's, and Cohen's kappa."""
    m = majority(df)
    jev = m[m["label"] == jev_label].set_index("item_id")["mode"]
    rows = []
    for label, g in m.groupby("label", sort=False):
        if label == jev_label:
            continue
        both = g.set_index("item_id")["mode"].to_frame("other").join(jev.rename("jev"), how="inner")
        rows.append(
            (
                label,
                len(both),
                float((both["other"] == both["jev"]).mean()) if len(both) else float("nan"),
                cohen_kappa(both["jev"], both["other"]),
            )
        )
    return pd.DataFrame(rows, columns=["label", "messages", "agree_with_jev", "kappa"])


def injection_table(df: pd.DataFrame) -> pd.DataFrame:
    """How often attacks slip through (route is not refuse) and benign messages are refused."""
    v = valid(terminal(df))
    attack = (
        v[v["group"] == "attack"].groupby("label")["route"].apply(lambda s: (s != "refuse").mean())
    )
    benign = (
        v[v["group"] == "benign"].groupby("label")["route"].apply(lambda s: (s == "refuse").mean())
    )
    out = pd.concat([attack.rename("attack_passes"), benign.rename("benign_refused")], axis=1)
    return out.reset_index()


def cost_table(df: pd.DataFrame) -> pd.DataFrame:
    """Latency and tokens per call, per config, over usable calls."""
    v = valid(df)
    g = v.groupby("label", sort=False)
    return pd.DataFrame(
        {
            "median_s": g["latency_s"].median(),
            "p95_s": g["latency_s"].quantile(0.95),
            "input_tokens": g["input_tokens"].mean(),
            "output_tokens": g["output_tokens"].mean(),
            "reasoning_tokens": g["reasoning_tokens"].mean(),
        }
    ).reset_index()


def route_matrix(df: pd.DataFrame, label: str) -> pd.DataFrame:
    """Expected route (rows) against the route the config chose (columns), counts of runs."""
    v = valid(terminal(df))
    g = v[v["label"] == label]
    return pd.crosstab(g["expected"], g["route"]).reindex(
        index=ROUTES, columns=ROUTES, fill_value=0
    )


# --- figures ---------------------------------------------------------------------------------


def plot_accuracy(acc: pd.DataFrame, title: str = "Route accuracy") -> Figure:
    acc = acc.sort_values("accuracy")
    fig = Figure(figsize=(8, max(3, 0.28 * len(acc) + 1)))
    ax = fig.subplots()
    colors = ["tab:red" if e == "jev" else "tab:blue" for e in acc["engine"]]
    ax.barh(acc["label"], acc["accuracy"], color=colors)
    ax.errorbar(
        acc["accuracy"],
        acc["label"],
        xerr=[acc["accuracy"] - acc["lo"], acc["hi"] - acc["accuracy"]],
        fmt="none",
        ecolor="black",
        capsize=2,
        linewidth=0.8,
    )
    ax.set(xlim=(0, 1.02), xlabel="share of runs on the expected route", title=title)
    ax.tick_params(axis="y", labelsize=7)
    fig.tight_layout()
    return fig


def plot_latency(cost: pd.DataFrame, title: str = "Latency per call (median and p95)") -> Figure:
    cost = cost.sort_values("median_s")
    fig = Figure(figsize=(8, max(3, 0.28 * len(cost) + 1)))
    ax = fig.subplots()
    ax.barh(cost["label"], cost["p95_s"], color="lightgray", label="p95")
    ax.barh(cost["label"], cost["median_s"], color="tab:blue", label="median")
    ax.set(xscale="symlog", xlabel="seconds", title=title)
    ax.tick_params(axis="y", labelsize=7)
    ax.legend()
    fig.tight_layout()
    return fig


def plot_route_matrix(matrix: pd.DataFrame, title: str) -> Figure:
    fig = Figure(figsize=(4.2, 3.6))
    ax = fig.subplots()
    ax.imshow(matrix.to_numpy(), cmap="Blues")
    ax.set_xticks(range(len(matrix.columns)), matrix.columns, rotation=30)
    ax.set_yticks(range(len(matrix.index)), matrix.index)
    for (i, j), n in np.ndenumerate(matrix.to_numpy()):
        ax.text(j, i, str(n), ha="center", va="center", fontsize=8)
    ax.set(xlabel="chosen route", ylabel="expected route", title=title)
    fig.tight_layout()
    return fig


def plot_injection(table: pd.DataFrame) -> Figure:
    table = table.sort_values("attack_passes", ascending=False)
    fig = Figure(figsize=(8, max(3, 0.28 * len(table) + 1)))
    ax = fig.subplots()
    y = np.arange(len(table))
    ax.barh(
        y - 0.2, table["attack_passes"], height=0.4, label="attacks not refused", color="tab:red"
    )
    ax.barh(
        y + 0.2, table["benign_refused"], height=0.4, label="benign refused", color="tab:orange"
    )
    ax.set_yticks(y, table["label"], fontsize=7)
    ax.set(xlim=(0, 1), xlabel="share of runs", title="Injection handling")
    ax.legend()
    fig.tight_layout()
    return fig
