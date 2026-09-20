"""The Korean notebooks must carry exactly the English notebooks' code, outputs, and results."""

import sync_notebooks_ko


def test_korean_notebooks_are_in_sync_with_the_english_ones(capsys):
    exit_code = sync_notebooks_ko.main(["--check"])
    assert exit_code == 0, capsys.readouterr().out
