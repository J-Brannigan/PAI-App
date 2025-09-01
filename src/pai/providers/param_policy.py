from __future__ import annotations
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

import yaml

@dataclass
class PolicyRule:
    regex: re.Pattern
    action: str              # "allow" | "drop" | "reject"
    params: List[str]
    message: Optional[str] = None

@dataclass
class ParamPolicy:
    rules: List[PolicyRule]

    @classmethod
    def load(cls, path: Path) -> "ParamPolicy":
        data = yaml.safe_load(path.read_text()) or {}
        rules: List[PolicyRule] = []
        for r in data.get("rules", []):
            rx = re.compile(str(r["when_model_matches"]))
            action = str(r["action"]).lower()
            params = [str(p) for p in r.get("params", [])]
            message = r.get("message")
            rules.append(PolicyRule(regex=rx, action=action, params=params, message=message))
        return cls(rules)

    def evaluate(self, model: str, raw_params: Dict[str, Any], *, default_action: str = "allow"
                 ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Returns (effective_params, warnings).
        - allow: keep listed keys (ignore others? we don't prune non-listed; we only act on the listed set)
        - drop:  remove listed keys, add a warning
        - reject: raise ValueError with message
        """
        effective = dict(raw_params or {})
        warnings: List[str] = []

        # Find first matching rule
        rule = next((r for r in self.rules if r.regex.search(model)), None)
        action = rule.action if rule else default_action
        params = set(rule.params) if rule else set()

        if action == "drop":
            dropped = sorted([k for k in params if k in effective])
            for k in dropped:
                effective.pop(k, None)
            if dropped:
                msg = rule.message or f"Dropping unsupported params for model '{model}': {dropped}"
                warnings.append(msg)

        elif action == "reject":
            bad = sorted([k for k in params if k in effective])
            if bad:
                msg = rule.message or f"Unsupported params for model '{model}': {bad}"
                raise ValueError(msg)

        # action == "allow": we don't need to do anything; we don't restrict to 'params' here
        return effective, warnings
