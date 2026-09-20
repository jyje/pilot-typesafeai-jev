import pytest

from pilot_jev.retry import with_retries


async def test_retries_transient_errors_then_succeeds():
    calls = []

    async def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise ConnectionResetError("reset by peer")
        return "ok"

    seen = []
    result = await with_retries(flaky, delay=0, on_retry=lambda n, e: seen.append(n))
    assert result == "ok"
    assert len(calls) == 3
    assert seen == [1, 2]


async def test_gives_up_after_the_last_attempt():
    async def always_down():
        raise TimeoutError("read timed out")

    with pytest.raises(TimeoutError):
        await with_retries(always_down, attempts=2, delay=0)


async def test_does_not_retry_real_bugs():
    calls = []

    async def buggy():
        calls.append(1)
        raise ValueError("bad input")

    with pytest.raises(ValueError):
        await with_retries(buggy, delay=0)
    assert len(calls) == 1


async def test_jev_errors_are_never_retried():
    from typesafe_sdk import TypeSafeAPIConnectionError

    calls = []

    async def jev_down():
        calls.append(1)
        raise TypeSafeAPIConnectionError("down")

    with pytest.raises(TypeSafeAPIConnectionError):
        await with_retries(jev_down, delay=0)
    assert len(calls) == 1


async def test_nim_http_503_is_retried_but_403_is_not():
    calls = []

    async def busy():
        calls.append(1)
        if len(calls) == 1:
            raise Exception("[503] Service Unavailable")  # noqa: TRY002
        return "ok"

    assert await with_retries(busy, delay=0) == "ok"

    async def forbidden():
        raise Exception("[403] Forbidden")  # noqa: TRY002

    with pytest.raises(Exception, match="403"):
        await with_retries(forbidden, delay=0)
