import logging

import aiohttp
import httpx2
import openai
import pytest

from pilot_jev import retry
from pilot_jev.retry import DEFAULT_ATTEMPTS, is_transient, retry_after, with_retries


def http_error(status: int):
    return aiohttp.ClientResponseError(request_info=None, history=(), status=status)  # ty: ignore[invalid-argument-type]


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


async def test_permanent_http_errors_are_not_retried_but_busy_ones_are():
    calls = []

    async def not_found():
        calls.append(1)
        raise http_error(404)

    with pytest.raises(aiohttp.ClientResponseError):
        await with_retries(not_found, delay=0)
    assert len(calls) == 1

    attempts = []

    async def busy():
        attempts.append(1)
        if len(attempts) == 1:
            raise http_error(503)
        return "ok"

    assert await with_retries(busy, delay=0) == "ok"


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


def openai_error(
    cls,
    status: int,
    *,
    code: str | None = None,
    type_: str | None = None,
    headers: dict | None = None,
):
    request = httpx2.Request("POST", "https://example.invalid/v1/responses")
    response = httpx2.Response(status, headers=headers, request=request)
    body = {"message": "secret detail"}
    if code:
        body["code"] = code
    if type_:
        body["type"] = type_
    return cls("secret detail", response=response, body=body if (code or type_) else None)


class Counter:
    """An async call that fails with each queued error in turn, then succeeds. Counts calls."""

    def __init__(self, *errors: Exception) -> None:
        self.errors = list(errors)
        self.calls = 0

    async def __call__(self) -> str:
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return "ok"


@pytest.fixture
def waits(monkeypatch) -> list[float]:
    """Record the waits instead of sleeping, and make jitter deterministic (its upper bound)."""
    recorded: list[float] = []

    async def fake_sleep(seconds):
        recorded.append(seconds)

    monkeypatch.setattr(retry.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(retry.random, "uniform", lambda _low, high: high)
    return recorded


def test_the_default_is_three_tries_per_logical_call():
    assert DEFAULT_ATTEMPTS == 3


async def test_a_call_that_keeps_failing_makes_exactly_the_default_number_of_tries(waits):
    call = Counter(*[TimeoutError("slow")] * 10)
    with pytest.raises(TimeoutError):
        await with_retries(call)
    assert call.calls == DEFAULT_ATTEMPTS
    assert len(waits) == DEFAULT_ATTEMPTS - 1


@pytest.mark.parametrize(
    "error",
    [
        openai_error(openai.AuthenticationError, 401),
        openai_error(openai.PermissionDeniedError, 403),
        openai_error(openai.NotFoundError, 404),
        openai_error(openai.BadRequestError, 400),
        openai_error(openai.RateLimitError, 429, code="usage_limit_reached"),
        openai_error(openai.RateLimitError, 429, code="insufficient_quota"),
        # The ChatGPT backend reports a used-up plan in `type`, not `code`.
        openai_error(openai.RateLimitError, 429, type_="usage_limit_reached"),
    ],
    ids=lambda e: f"{type(e).__name__}-{e.status_code}-{e.code or e.type}",
)
async def test_permanent_openai_errors_are_tried_once(waits, error):
    call = Counter(error)
    with pytest.raises(type(error)):
        await with_retries(call)
    assert call.calls == 1
    assert waits == []


@pytest.mark.parametrize(
    "error",
    [
        openai_error(openai.RateLimitError, 429),
        openai_error(openai.InternalServerError, 500),
        openai_error(openai.InternalServerError, 503),
        openai.APIConnectionError(request=httpx2.Request("POST", "https://example.invalid")),
        openai.APITimeoutError(request=httpx2.Request("POST", "https://example.invalid")),
    ],
    ids=lambda e: type(e).__name__,
)
async def test_transient_openai_errors_are_retried_and_then_succeed(waits, error):
    call = Counter(error)
    assert await with_retries(call) == "ok"
    assert call.calls == 2
    assert len(waits) == 1


async def test_waits_grow_exponentially_and_are_capped(waits):
    call = Counter(*[ConnectionError("down")] * 10)
    with pytest.raises(ConnectionError):
        await with_retries(call, attempts=5, delay=2.0, max_delay=6.0)
    assert waits == [2.0, 4.0, 6.0, 6.0]  # jitter pinned to its upper bound by the fixture


async def test_jitter_keeps_each_wait_between_half_and_all_of_the_step(monkeypatch):
    monkeypatch.setattr(retry.asyncio, "sleep", lambda _s: _noop())
    step = 8.0
    samples = [retry.backoff(3, delay=2.0, max_delay=60.0) for _ in range(200)]
    assert all(step / 2 <= w <= step for w in samples)
    assert len(set(samples)) > 1


async def _noop():
    return None


async def test_retry_after_seconds_replace_the_backoff_and_are_capped(waits):
    slow = openai_error(openai.RateLimitError, 429, headers={"retry-after": "7"})
    call = Counter(slow)
    assert await with_retries(call, delay=1.0) == "ok"
    assert waits == [7.0]

    waits.clear()
    huge = openai_error(openai.RateLimitError, 429, headers={"retry-after": "9999"})
    assert await with_retries(Counter(huge), max_delay=30.0) == "ok"
    assert waits == [30.0]


def test_retry_after_reads_seconds_dates_and_ignores_garbage():
    def error(value: str):
        return openai_error(openai.RateLimitError, 429, headers={"retry-after": value})

    assert retry_after(error("3")) == 3.0
    assert retry_after(error("-5")) == 0.0
    assert retry_after(error("soon")) is None
    assert retry_after(error("Wed, 21 Oct 2015 07:28:00 GMT")) == 0.0  # a past date
    assert retry_after(ConnectionError("no response")) is None


async def test_each_retry_reaches_the_hook_and_the_log_without_the_error_message(waits, caplog):
    seen: list[tuple[int, str]] = []
    call = Counter(openai_error(openai.InternalServerError, 503))
    with caplog.at_level(logging.WARNING, logger="pilot_jev.retry"):
        await with_retries(call, on_retry=lambda n, e: seen.append((n, type(e).__name__)))
    assert seen == [(1, "InternalServerError")]
    assert "InternalServerError (HTTP 503)" in caplog.text
    assert "secret detail" not in caplog.text


async def test_the_same_transient_error_gets_the_same_tries_on_both_providers(waits):
    nim = Counter(*[Exception("[503] Service Unavailable")] * 10)
    codex = Counter(*[openai_error(openai.InternalServerError, 503)] * 10)
    for call in (nim, codex):
        with pytest.raises(Exception):  # noqa: B017 - the exact type differs per provider
            await with_retries(call)
    assert nim.calls == codex.calls == DEFAULT_ATTEMPTS


@pytest.mark.parametrize("status", [408, 409, 500, 501, 502, 503, 504, 529, 599])
async def test_openai_statuses_the_sdk_would_retry_are_still_retried(waits, status):
    call = Counter(openai_error(openai.APIStatusError, status))
    assert await with_retries(call) == "ok"
    assert call.calls == 2


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_other_client_errors_are_not_retried(status):
    assert not is_transient(openai_error(openai.APIStatusError, status))


def test_the_x_should_retry_header_decides_when_present():
    yes = openai_error(openai.APIStatusError, 400, headers={"x-should-retry": "true"})
    no = openai_error(openai.InternalServerError, 503, headers={"x-should-retry": "false"})
    assert is_transient(yes)
    assert not is_transient(no)
    # A used-up plan stays permanent even if the header says otherwise.
    spent = openai_error(
        openai.RateLimitError, 429, code="usage_limit_reached", headers={"x-should-retry": "true"}
    )
    assert not is_transient(spent)


def test_openai_status_errors_are_classified_by_status_and_code():
    assert is_transient(openai_error(openai.RateLimitError, 429))
    assert not is_transient(openai_error(openai.RateLimitError, 429, code="usage_limit_reached"))
    assert not is_transient(openai_error(openai.AuthenticationError, 401))


async def test_a_used_up_plan_reported_in_the_type_field_is_never_retried_and_never_waits(waits):
    error = openai_error(openai.RateLimitError, 429, type_="usage_limit_reached")
    assert not is_transient(error)
    call = Counter(error)
    with pytest.raises(openai.RateLimitError):
        await with_retries(call)
    assert call.calls == 1
    assert waits == []
