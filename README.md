# Healthcare AI Platform

AI-assisted pre-visit symptom intake for an outpatient clinic: free-text patient input is validated, structured against a schema, summarised without diagnosis, checked by deterministic safety rules, and (planned) routed to clinic staff for human review.

**Status:** in development — Phases 1–2 complete, Phase 3 in progress. Synthetic data only; no medical advice; no HIPAA compliance claim.

* What works today, with evidence: [`docs/project_status.md`](docs/project_status.md)
* Product and architecture overview: [`docs/overview.md`](docs/overview.md)
* Roadmap and remaining scope: [`docs/step3_roadmap.md`](docs/step3_roadmap.md)
* Completed phase records: [`docs/project_journal/`](docs/project_journal/)

Work is tracked in GitHub Issues and Projects and delivered as Issue → branch → tests → PR → review → merge → journal.

## Running tests

```bash
pip install -r requirements.txt   # note: manifest is incomplete; fixed in Phase 3
pytest
```

A full README (setup, demo walkthrough, architecture diagram) is part of Phase 4.
