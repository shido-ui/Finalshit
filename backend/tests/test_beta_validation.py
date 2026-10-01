import json
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "beta_benchmarks.json"


def test_beta_benchmark_fixture_is_well_formed():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["scope"] == "single_user_jee_beta"
    cases = payload["cases"]
    assert len(cases) >= 3
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids))
    for case in cases:
        assert case["subject"] in {"Physics", "Chemistry", "Mathematics"}
        assert case["input_type"] == "synthetic_pdf"
        assert case["required_capabilities"]
        assert all(isinstance(value, str) for value in case["required_capabilities"])
