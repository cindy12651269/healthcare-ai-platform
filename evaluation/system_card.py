"""
System card evaluation snapshot (Issue #43).

`evaluation/system_card_results.json` is the committed snapshot of the deterministic
mock-mode #32 safety & escalation results and #40 extraction results that the system
card page shows. tests/test_system_card.py re-runs both suites and fails if the
committed numbers drift from current behaviour. Regenerate after a deliberate change:

    python -m evaluation.system_card
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Any, Dict

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

RESULTS_PATH = Path(__file__).resolve().parent / "system_card_results.json"


def build_results() -> Dict[str, Any]:
    from evaluation.benchmark import run_extraction_benchmark, run_safety_benchmark

    safety = run_safety_benchmark()
    extraction = run_extraction_benchmark("mock")
    return {
        "source": "python -m evaluation.system_card (mock mode, deterministic)",
        "safety_escalation": {
            "issue": 32,
            "mode": safety["mode"],
            "categories": {
                name: {k: c[k] for k in ("cases", "guard_matches", "guard_match_rate",
                                         "escalation_matches", "escalation_match_rate", "known_gaps")}
                for name, c in safety["categories"].items()
            },
            "aggregate": safety["aggregated"],
            "limitation": "Match rates measure agreement with the labelled current rule baseline on 16 synthetic "
                          "cases, not safety accuracy or recall. Known gaps are recorded, not fixed.",
        },
        "extraction": {
            "issue": 40,
            "mode": extraction["mode"],
            "method": extraction["extraction_method"],
            "aggregate": extraction["aggregated"],
            "limitation": "In-sample: the rule-based lexicon was written with these 6 synthetic cases in view, so "
                          "1.00 is agreement with a tiny set, not a measure of real-world extraction quality.",
        },
    }


def load_results() -> Dict[str, Any]:
    with RESULTS_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    RESULTS_PATH.write_text(json.dumps(build_results(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {RESULTS_PATH}")
