"""The analysis functions on small frames whose right answers are known by hand."""

import io
import json
from collections.abc import Mapping, Sequence

import pandas as pd
import pytest

from experiments import analysis, dataset

JEV = "jev:jev:-"
GPT = "openai:gpt-5.6-luna:low"


def rows_for(
    label: str,
    engine: str,
    routes: Mapping[str, Sequence[str | None]],
    latency=1.0,
    error=None,
):
    out = []
    for item_id, answers in routes.items():
        for repeat, route in enumerate(answers, 1):
            out.append(
                {
                    "stage": "t",
                    "label": label,
                    "engine": engine,
                    "model": label.split(":")[1],
                    "setting": label.split(":")[2],
                    "item_id": item_id,
                    "repeat": repeat,
                    "started_at": 0.0,
                    "latency_s": latency,
                    "route": route,
                    "input_tokens": 100,
                    "output_tokens": 10,
                    "reasoning_tokens": None,
                    "error_kind": error,
                    "error": None,
                }
            )
    return out


def frame(*groups) -> pd.DataFrame:
    path_rows = [r for g in groups for r in g]
    buffer = "\n".join(json.dumps(r) for r in path_rows)
    return analysis.load([_write(buffer)])


def _write(text: str):
    import tempfile
    from pathlib import Path

    path = Path(tempfile.mkstemp(suffix=".jsonl")[1])
    path.write_text(text)
    return path


# c01 answer, c02 escalate, c03 refuse (attack? no: core), a01 attack refuse, b01 benign answer.
JEV_ROWS = rows_for(
    JEV,
    "jev",
    {
        "c01": ["answer"] * 4,
        "c02": ["escalate"] * 4,
        "a01": ["refuse"] * 4,
        "b01": ["answer"] * 4,
    },
    latency=0.5,
)
GPT_ROWS = rows_for(
    GPT,
    "openai",
    {
        "c01": ["answer"] * 4,
        "c02": ["escalate", "escalate", "answer", "answer"],  # 50% consistent, 50% right
        "a01": ["answer", "answer", "answer", "refuse"],  # the attack mostly slips through
        "b01": ["refuse"] * 4,  # a benign message refused every time
    },
    latency=3.0,
)


def test_load_adds_expected_routes_and_groups():
    df = frame(JEV_ROWS)
    row = df[df["item_id"] == "a01"].iloc[0]
    assert (row["expected"], row["group"], bool(row["expected_injection"])) == (
        "refuse",
        "attack",
        True,
    )
    assert df["hit"].all()


def test_availability_reports_validity_speed_and_the_screen_rule():
    slow = rows_for("nim:m:default", "nim", {"c01": ["answer"] * 10}, latency=90.0)
    dead = rows_for("nim:n:default", "nim", {"c01": [None] * 10}, latency=1.0, error="timeout")
    table = analysis.availability(frame(JEV_ROWS, GPT_ROWS, slow, dead))
    assert table.loc[JEV, "passes"] and table.loc[GPT, "passes"]
    assert not table.loc["nim:m:default", "passes"]  # too slow
    assert table.loc["nim:n:default", "valid_rate"] == 0.0
    assert not table.loc["nim:n:default", "passes"]
    assert table.loc[GPT, "median_s"] == 3.0


def test_majority_and_consistency():
    m = analysis.majority(frame(GPT_ROWS)).set_index("item_id")
    assert m.loc["c01", "mode"] == "answer" and m.loc["c01", "share"] == 1.0
    assert m.loc["c02", "share"] == 0.5
    assert m.loc["a01", "mode"] == "answer" and m.loc["a01", "share"] == 0.75
    assert analysis.consistency(frame(GPT_ROWS)).iloc[0]["consistency"] == pytest.approx(
        (1.0 + 0.5 + 0.75 + 1.0) / 4
    )


def test_accuracy_is_the_share_of_runs_on_the_expected_route_with_an_interval():
    acc = analysis.accuracy(frame(JEV_ROWS, GPT_ROWS)).set_index("label")
    assert acc.loc[JEV, "accuracy"] == 1.0
    assert acc.loc[GPT, "accuracy"] == pytest.approx((4 + 2 + 1 + 0) / 16)
    assert acc.loc[GPT, "lo"] <= acc.loc[GPT, "accuracy"] <= acc.loc[GPT, "hi"]
    only_attacks = analysis.accuracy(frame(GPT_ROWS), groups=["attack"]).iloc[0]
    assert only_attacks["accuracy"] == 0.25


def test_the_bootstrap_resamples_messages_and_is_repeatable():
    df = analysis.valid(frame(GPT_ROWS))
    a = analysis.bootstrap_ci(df["hit"], df["item_id"])
    assert a == analysis.bootstrap_ci(df["hit"], df["item_id"])
    assert a[1] <= a[0] <= a[2]
    constant = analysis.bootstrap_ci(pd.Series([1.0] * 6), pd.Series(list("aabbcc")))
    assert constant == (1.0, 1.0, 1.0)
    assert all(pd.isna(x) for x in analysis.bootstrap_ci(pd.Series([], dtype=float), pd.Series([])))


def test_cohen_kappa_on_known_cases():
    assert analysis.cohen_kappa(list("aabb"), list("aabb")) == 1.0
    assert analysis.cohen_kappa(list("aabb"), list("bbaa")) == -1.0
    assert analysis.cohen_kappa(list("aaaa"), list("aaaa")) == 1.0
    assert 0 < analysis.cohen_kappa(list("aabbab"), list("aabbba")) < 1
    assert pd.isna(analysis.cohen_kappa([], []))


def test_agreement_with_jev_compares_most_common_routes():
    out = analysis.agreement_with_jev(frame(JEV_ROWS, GPT_ROWS)).iloc[0]
    assert out["label"] == GPT and out["messages"] == 4
    assert out["agree_with_jev"] == 0.25  # only c01 matches; c02 ties, a01 and b01 differ
    assert out["kappa"] < 0.5


def test_injection_table_counts_attacks_that_slip_through_and_benign_refusals():
    table = analysis.injection_table(frame(JEV_ROWS, GPT_ROWS)).set_index("label")
    assert table.loc[JEV, "attack_passes"] == 0.0 and table.loc[JEV, "benign_refused"] == 0.0
    assert table.loc[GPT, "attack_passes"] == 0.75 and table.loc[GPT, "benign_refused"] == 1.0


def test_cost_table_and_route_matrix():
    df = frame(JEV_ROWS, GPT_ROWS)
    cost = analysis.cost_table(df).set_index("label")
    assert cost.loc[GPT, "median_s"] == 3.0 and cost.loc[GPT, "input_tokens"] == 100
    matrix = analysis.route_matrix(df, GPT)
    assert list(matrix.index) == analysis.ROUTES and matrix.to_numpy().sum() == 16
    assert matrix.loc["escalate", "answer"] == 2 and matrix.loc["refuse", "answer"] == 3


def test_every_figure_renders_to_png():
    df = frame(JEV_ROWS, GPT_ROWS)
    figures = [
        analysis.plot_accuracy(analysis.accuracy(df)),
        analysis.plot_latency(analysis.cost_table(df)),
        analysis.plot_route_matrix(analysis.route_matrix(df, GPT), "gpt"),
        analysis.plot_injection(analysis.injection_table(df)),
    ]
    for fig in figures:
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png")
        assert buffer.getvalue().startswith(b"\x89PNG")


def test_an_empty_input_gives_an_empty_frame():
    assert analysis.load([_write("")]).empty
    assert dataset.ALL_ITEMS  # the merge source is available


def test_trim_repeats_keeps_the_first_n_runs_of_every_config():
    df = frame(JEV_ROWS, GPT_ROWS)
    assert set(analysis.trim_repeats(df, 2)["repeat"]) == {1, 2}
    assert len(analysis.trim_repeats(df, 2)) == len(df) // 2


def per_message_frame(jev_acc: list[float], other_acc: list[float], runs: int = 5) -> pd.DataFrame:
    """Rows where message i is answered correctly in round(acc * runs) of `runs` runs."""
    rows = []
    for label, engine, accs in [(JEV, "jev", jev_acc), (GPT, "openai", other_acc)]:
        for i, acc in enumerate(accs):
            hits = round(acc * runs)
            routes = ["answer"] * hits + ["review"] * (runs - hits)
            rows += rows_for(label, engine, {f"c{i + 1:02d}": routes})
    frame_ = frame(rows)
    frame_["hit"] = frame_["route"] == "answer"  # the message set is invented: answer is right
    return frame_


def test_the_paired_bootstrap_finds_a_steady_gap_that_overlapping_intervals_hide():
    jev = [0.4, 0.6, 0.8, 1.0] * 5
    other = [a - 0.1 for a in jev]  # a constant 0.1 lower on every message
    df = per_message_frame(jev, other, runs=10)
    marginal = analysis.accuracy(df).set_index("label")
    assert marginal.loc[JEV, "lo"] < marginal.loc[GPT, "hi"]  # the two intervals overlap
    out = analysis.paired_versus_jev(df).iloc[0]
    assert out["vs_jev"] == "worse"
    assert out["difference"] == pytest.approx(-0.1)
    assert out["diff_hi"] < 0 and out["messages"] == 20


def test_the_paired_bootstrap_calls_no_gap_not_distinguishable():
    jev = [0.4, 0.6, 0.8, 1.0] * 5
    other = [0.6, 0.4, 1.0, 0.8] * 5  # differences of both signs
    out = analysis.paired_versus_jev(per_message_frame(jev, other)).iloc[0]
    assert out["vs_jev"] == "not distinguishable"
    assert out["diff_lo"] <= 0 <= out["diff_hi"]


def test_the_paired_bootstrap_can_call_a_config_better():
    jev = [0.4, 0.6] * 10
    other = [a + 0.2 for a in jev]
    assert analysis.paired_versus_jev(per_message_frame(jev, other)).iloc[0]["vs_jev"] == "better"


def test_paired_versus_jev_only_compares_messages_both_engines_answered():
    df = per_message_frame([1.0, 1.0, 1.0], [1.0, 1.0, 1.0])
    df = df[~((df["label"] == GPT) & (df["item_id"] == "c03"))]
    out = analysis.paired_versus_jev(df).iloc[0]
    assert out["messages"] == 2


def test_paired_versus_jev_without_jev_rows_is_empty():
    assert analysis.paired_versus_jev(frame(GPT_ROWS)).empty


def test_the_report_script_writes_tables_figures_and_parquet(tmp_path):
    from experiments import report

    rows = [{**r, "stage": stage} for stage in ("screen", "main") for r in [*JEV_ROWS, *GPT_ROWS]]
    data = tmp_path / "data"
    data.mkdir()
    (data / "run.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    written = report.build(data, tmp_path / "tables", tmp_path / "images")
    assert {"screen", "accuracy", "injection", "cost", "results", "figure-accuracy"} <= set(written)
    assert all(path.is_file() for path in written.values())
    assert pd.read_parquet(written["results"]).shape[0] == len(rows)
    accuracy = pd.read_csv(written["accuracy"]).set_index("label")
    assert accuracy.loc[GPT, "vs_jev"] in {"better", "worse", "not distinguishable"}


def test_the_report_script_refuses_an_empty_data_directory(tmp_path):
    from experiments import report

    with pytest.raises(SystemExit):
        report.build(tmp_path, tmp_path / "t", tmp_path / "i")
