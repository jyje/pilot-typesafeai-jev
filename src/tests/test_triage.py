import pytest
from typesafe_sdk import Choice, Noul, Score

from pilot_jev.triage import Policy, Triage, decide, parse_triage, triage_questions
from tests.conftest import build_response, intent, noul, urgency


def test_questions_are_one_fan_out_of_three_primitives():
    questions = triage_questions()
    assert set(questions) == {"intent", "urgency", "injection"}
    assert isinstance(questions["intent"], Choice)
    assert isinstance(questions["urgency"], Score)
    assert isinstance(questions["injection"], Noul)
    # A no-match outcome keeps the Choice honest when nothing fits.
    assert "other" in questions["intent"].criteria


def test_parse_triage_reads_typed_answers():
    response = build_response(
        intent=intent("technical", 0.77), urgency=urgency(1.0), injection=noul(0.05)
    )
    assert parse_triage(response) == Triage("technical", 0.77, 1.0, 0.05)


@pytest.mark.parametrize(
    ("triage", "route"),
    [
        (Triage("billing", 0.9, 0.2, 0.01), "answer"),
        (Triage("billing", 0.9, 1.6, 0.01), "escalate"),
        (Triage("billing", 0.3, 0.2, 0.01), "review"),
        (Triage("other", 0.9, 0.2, 0.01), "review"),
        (Triage("billing", 0.9, 0.2, 0.95), "refuse"),
        # Refusal outranks urgency, and urgency outranks uncertainty.
        (Triage("billing", 0.9, 1.9, 0.95), "refuse"),
        (Triage("other", 0.2, 1.9, 0.01), "escalate"),
    ],
)
def test_decide_precedence(triage, route):
    assert decide(triage) == route


def test_policy_thresholds_are_tunable():
    strict = Policy(injection_block=0.3)
    assert decide(Triage("billing", 0.9, 0.2, 0.4), strict) == "refuse"
    assert decide(Triage("billing", 0.9, 0.2, 0.4)) == "answer"


def test_decide_boundaries_are_inclusive_where_the_policy_says_so():
    assert decide(Triage("billing", 0.9, 0.0, 0.8)) == "refuse"  # injection >= 0.8
    assert decide(Triage("billing", 0.9, 1.5, 0.0)) == "escalate"  # urgency >= 1.5
    assert decide(Triage("billing", 0.5, 0.0, 0.0)) == "answer"  # confidence >= 0.5 passes


@pytest.mark.parametrize(
    ("triage", "route"),
    [
        (Triage("billing", 0.9, 0.0, float("nan")), "refuse"),
        (Triage("billing", 0.9, float("nan"), 0.0), "escalate"),
        (Triage("billing", float("nan"), 0.0, 0.0), "review"),
    ],
)
def test_decide_fails_closed_on_nan(triage, route):
    assert decide(triage) == route
