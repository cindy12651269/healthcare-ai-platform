# Synthetic /api/ingest responses for the local #70 visual check: the real mock pipeline (LLM_MODE=mock)
# run on the four SCENARIO_PRESETS texts with persistence and the webhook off. No database, no network.
# Usage (repo root): PYTHONPATH=. python3 <this file> <out.json>
import json
import os
import sys

os.environ["LLM_MODE"] = "mock"
os.environ["ENABLE_PERSISTENCE"] = "false"
os.environ.pop("WEBHOOK_URL", None)

from api.deps import get_pipeline  # noqa: E402

PRESETS = {  # app/services/demo.ts
    "routine": "I have had a sore throat and a mild fever for two days.",
    "emergency": "I have chest pain and shortness of breath since this morning.",
    "prescription": "Should I take 500 mg of amoxicillin for this cough?",
    "vague": "I just don't feel right and wanted to check in.",
}

pipeline = get_pipeline()
out = {
    key: pipeline.run(
        raw_text=text,
        meta={"source": "web", "input_type": "intake", "consent_granted": True, "user_id": None},
    )
    for key, text in PRESETS.items()
}
with open(sys.argv[1], "w") as f:
    json.dump(out, f, indent=1, default=str)
