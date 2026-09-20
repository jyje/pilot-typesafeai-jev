"""Load the repo-level .env once per process, wherever the entry point is started from."""

from __future__ import annotations

import functools

from dotenv import find_dotenv, load_dotenv


@functools.cache
def load_env() -> None:
    """Walk up from this file to the first .env (the repo root), without overriding real env.

    The TypeSafe SDK then picks up TYPESAFE_API_KEY from the environment on its own.
    """
    load_dotenv(find_dotenv())
