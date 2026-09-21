"""Write the tables (CSV), the figures (PNG), and the combined data (parquet) from the JSONL rows.

    uv run --extra analysis python -m experiments.report

The notebook shows the same numbers. This script exists so they can be rebuilt without Jupyter, for
example to refresh the figures used in the docs after a new run.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

import pandas as pd
from matplotlib.figure import Figure

from experiments import analysis

HERE = Path(__file__).parent
DATA = HERE / "data"
IMAGES = HERE.parent.parent / "docs" / "images"
PARITY_REPEATS = 5


def build(data_dir: Path, tables_dir: Path, images_dir: Path) -> dict[str, Path]:
    """Read every JSONL file under `data_dir` and write everything. Returns name -> path."""
    df = analysis.load(sorted(data_dir.glob("*.jsonl")))
    if df.empty:
        raise SystemExit(f"no rows under {data_dir}")
    tables_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    def table(name: str, frame: pd.DataFrame) -> None:
        path = tables_dir / f"{name}.csv"
        frame.to_csv(path, index=False)
        written[name] = path

    def figure(name: str, fig: Figure) -> None:
        path = images_dir / f"control-{name}.png"
        fig.savefig(path, dpi=140)
        written[f"figure-{name}"] = path

    df.to_parquet(data_dir / "results.parquet", index=False)
    written["results"] = data_dir / "results.parquet"

    screen = df[df["stage"] == "screen"]
    if not screen.empty:
        table(
            "screen",
            analysis.availability(screen)
            .assign(errors=lambda t: t["errors"].astype(str))
            .reset_index(),
        )

    main = analysis.trim_repeats(df[df["stage"] == "main"], PARITY_REPEATS)
    if not main.empty:
        acc = analysis.accuracy(main)
        table("accuracy", acc.merge(analysis.paired_versus_jev(main), on="label", how="left"))
        table(
            "consistency_agreement",
            analysis.consistency(main).merge(
                analysis.agreement_with_jev(main), on="label", how="outer"
            ),
        )
        inj = analysis.injection_table(main)
        cost = analysis.cost_table(main)
        table("injection", inj)
        table("cost", cost)
        figure("accuracy", analysis.plot_accuracy(acc, "Route accuracy, first 5 runs, 60 messages"))
        figure("injection", analysis.plot_injection(inj))
        figure("latency", analysis.plot_latency(cost))
        figure(
            "routes-jev",
            analysis.plot_route_matrix(analysis.route_matrix(main, "jev:jev:-"), "Jev"),
        )
    return written


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, default=DATA)
    p.add_argument("--tables", type=Path, default=DATA / "tables")
    p.add_argument("--images", type=Path, default=IMAGES)
    args = p.parse_args(argv)
    for name, path in build(args.data, args.tables, args.images).items():
        print(f"{name:24} {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
