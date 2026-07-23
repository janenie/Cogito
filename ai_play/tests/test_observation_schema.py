import pytest

from ai_play.observation_schema import (
    ObservationValidationError,
    validate_action_results,
)


@pytest.mark.parametrize("outcome", ["aligned", "not_found"])
def test_probe_result_accepts_completed_outcome(outcome):
    results = [{
        "status": "completed",
        "type": "probe_interaction",
        "outcome": outcome,
        "scan_steps": 3,
    }]
    assert validate_action_results(results) == results


@pytest.mark.parametrize(
    "patch",
    [
        {"outcome": "clicked"},
        {"scan_steps": -1},
        {"scan_steps": 10},
        {"scan_steps": 1.5},
    ],
)
def test_probe_result_rejects_invalid_fields(patch):
    result = {
        "status": "completed",
        "type": "probe_interaction",
        "outcome": "aligned",
        "scan_steps": 1,
        **patch,
    }
    with pytest.raises(ObservationValidationError):
        validate_action_results([result])
