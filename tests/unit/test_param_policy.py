from __future__ import annotations
import sys
from pathlib import Path

# Make "src" importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from pai.providers.param_policy import ParamPolicy
import yaml


def write_yaml(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.strip() + "\n", encoding="utf-8")
    return p


def test_policy_drop_removes_params_and_warns(tmp_path: Path):
    # GIVEN a policy that drops sampling knobs for nano models
    policy_file = write_yaml(
        tmp_path / "providers" / "openai.yaml",
        """
        rules:
          - when_model_matches: "^gpt-5-nano"
            action: drop
            params: [temperature, top_p, frequency_penalty, presence_penalty]
            message: "Nano models use default sampling only."
        """,
    )
    policy = ParamPolicy.load(policy_file)

    raw = {"temperature": 0.2, "top_p": 0.9, "foo": "bar"}
    effective, warnings = policy.evaluate("gpt-5-nano-2025-08-07", raw)

    # THEN unsupported are removed, others untouched
    assert "temperature" not in effective
    assert "top_p" not in effective
    assert effective.get("foo") == "bar"
    # AND we get one warning
    assert len(warnings) == 1
    assert "Nano models use default sampling only." in warnings[0]


def test_policy_reject_raises(tmp_path: Path):
    policy_file = write_yaml(
        tmp_path / "providers" / "openai.yaml",
        """
        rules:
          - when_model_matches: "^gpt-5-nano"
            action: reject
            params: [temperature]
            message: "Remove temperature for nano models."
        """,
    )
    policy = ParamPolicy.load(policy_file)

    raw = {"temperature": 0.2}
    try:
        policy.evaluate("gpt-5-nano-2025-08-07", raw)
        raise AssertionError("Expected ValueError for reject rule")
    except ValueError as e:
        assert "Remove temperature for nano models." in str(e)


def test_policy_first_match_wins(tmp_path: Path):
    # Second rule would allow, but first matching rule should win (drop).
    policy_file = write_yaml(
        tmp_path / "providers" / "openai.yaml",
        """
        rules:
          - when_model_matches: "^gpt-5-nano"
            action: drop
            params: [temperature]
          - when_model_matches: ".*"
            action: allow
            params: [temperature]
        """,
    )
    policy = ParamPolicy.load(policy_file)
    effective, warnings = policy.evaluate("gpt-5-nano-x", {"temperature": 0.2})
    assert "temperature" not in effective
    assert warnings  # got at least one warning


def test_policy_default_allow_when_no_rule(tmp_path: Path):
    policy_file = write_yaml(
        tmp_path / "providers" / "openai.yaml",
        """
        rules:
          - when_model_matches: "^other-family"
            action: drop
            params: [temperature]
        """,
    )
    policy = ParamPolicy.load(policy_file)
    effective, warnings = policy.evaluate("gpt-4o-mini", {"temperature": 0.2})
    # No matching rule - keep params as-is, no warnings
    assert effective.get("temperature") == 0.2
    assert warnings == []