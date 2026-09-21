"""Settings come from defaults, the file, the environment, then overrides, and bad ones fail loudly."""

import pytest

from experiments import config
from experiments.config import RunConfig, load


def write(tmp_path, text: str):
    path = tmp_path / "config.toml"
    path.write_text(text)
    return path


def test_the_defaults_are_parallel_with_a_window_of_ten():
    cfg = load(path=None, env={})
    assert (cfg.mode, cfg.window, cfg.in_flight) == ("parallel", 10, 10)


def test_the_shipped_file_selects_parallel_with_a_window_of_ten():
    cfg = load(env={})
    assert (cfg.mode, cfg.window, cfg.order) == ("parallel", 10, "shuffle")


def test_layers_override_in_order(tmp_path):
    path = write(tmp_path, '[run]\nmode = "sequential"\nwindow = 3\n')
    assert load(path, env={}).in_flight == 1
    assert load(path, env={"EXPERIMENT_MODE": "parallel"}).in_flight == 3
    cfg = load(path, env={"EXPERIMENT_MODE": "parallel"}, overrides={"window": 6, "mode": None})
    assert (cfg.mode, cfg.window) == ("parallel", 6)


def test_sequential_mode_runs_one_at_a_time_whatever_the_window():
    assert RunConfig(mode="sequential", window=10).in_flight == 1


@pytest.mark.parametrize(
    "env",
    [
        {"EXPERIMENT_MODE": "serial"},
        {"EXPERIMENT_WINDOW": "0"},
        {"EXPERIMENT_WINDOW": "ten"},
        {"EXPERIMENT_TIMEOUT_S": "-1"},
        {"EXPERIMENT_ORDER": "random"},
    ],
)
def test_invalid_settings_are_rejected(env):
    with pytest.raises(ValueError):
        load(path=None, env=env)


def test_unknown_keys_are_rejected(tmp_path):
    with pytest.raises(ValueError, match="unknown"):
        load(write(tmp_path, "[run]\nwindwo = 4\n"), env={})
    with pytest.raises(ValueError, match="unknown"):
        load(path=None, env={}, overrides={"parallel": True})


def test_the_default_path_is_the_file_next_to_the_module():
    assert config.DEFAULT_PATH.name == "config.toml" and config.DEFAULT_PATH.is_file()
