// Dashboard content (#69): workflow stages, the real-vs-mock panel and capability cards.
// Every statement here is bounded by docs/project_status.md §3 (capability matrix); every link points
// at a committed file in this repository or a section of the system card. tests/Dashboard.test.tsx
// checks that each repository path (and heading anchor) exists.

export const REPO_URL = "https://github.com/cindy12651269/healthcare-ai-platform";

export interface EvidenceLink {
  label: string;
  href: string; // "/system-card#…" (in-app) or a repository path such as "docs/auth.md#roles-and-clinic-isolation"
}

// Repository paths become links to the file on GitHub's main branch; in-app paths stay relative.
export const evidenceHref = (href: string) => (href.startsWith("/") ? href : `${REPO_URL}/blob/main/${href}`);

export type Maturity = "implemented" | "mock" | "limited" | "conditional";

export const MATURITY_LABELS: Record<Maturity, string> = {
  implemented: "Implemented",
  mock: "Mock mode",
  limited: "Demo limit",
  conditional: "Conditional",
};

export interface WorkflowStage {
  id: string;
  title: string;
  summary: string;
  tags: Maturity[];
  note: string; // what is mock or limited at this stage
}

export const WORKFLOW: WorkflowStage[] = [
  {
    id: "intake",
    title: "Patient intake",
    summary: "A synthetic patient describes symptoms and gives consent; a keyword PHI check runs before processing.",
    tags: ["implemented", "limited"],
    note: "Unauthenticated by design; synthetic data only. Every intake goes to one seeded clinic.",
  },
  {
    id: "structuring",
    title: "Structuring",
    summary: "Symptoms, duration, onset, severity and red flags are extracted into a fixed schema.",
    tags: ["mock"],
    note: "Hosted demo: a deterministic rule-based extractor with a small fixed lexicon, not an LLM.",
  },
  {
    id: "report",
    title: "Report + safety guard",
    summary: "A short pre-visit report is produced, then a rule-based guard blocks diagnosis and prescription content, masks PHI patterns and adds emergency guidance.",
    tags: ["implemented", "mock"],
    note: "Report text comes from a deterministic mock builder. The guard is keyword/regex rules with recorded gaps.",
  },
  {
    id: "escalation",
    title: "Escalation rules",
    summary: "Emergency language, blocked output or low structuring confidence set the intake to needs review, with reason codes.",
    tags: ["implemented"],
    note: "Deterministic rules; paraphrases outside the rules can be missed.",
  },
  {
    id: "queue",
    title: "Clinic review queue",
    summary: "Clinic staff see only their own clinic's queue and mark flagged intakes reviewed or escalated.",
    tags: ["implemented", "limited"],
    note: "Needs a short-lived token issued on request by the demo operator.",
  },
  {
    id: "timeline",
    title: "Evidence timeline",
    summary: "Why the intake was flagged, recorded guard matches in the input, processing provenance, any webhook delivery attempts and staff actions.",
    tags: ["implemented"],
    note: "Shows persisted records only; no model reasoning is stored or shown.",
  },
  {
    id: "fhir",
    title: "FHIR R4 export",
    summary: "One intake as a FHIR R4 Bundle, validated in CI against the official R4 JSON Schema, previewed and downloaded.",
    tags: ["implemented", "limited"],
    note: "Export only: no FHIR server, no transmission, synthetic data.",
  },
];

// Not a step every intake takes: it branches off the escalation rules.
export const WEBHOOK_BRANCH = {
  after: "escalation",
  title: "Signed webhook",
  summary: "Escalated intakes trigger one HMAC-signed, PHI-free notification with bounded retries, only when a receiver is configured.",
  note: "Disabled on the hosted demo (no receiver configured).",
};

export type RealVsMockKind = "mock" | "real" | "opt-in" | "not-connected";

export const REAL_VS_MOCK_LABELS: Record<RealVsMockKind, string> = {
  mock: "Mock",
  real: "Implemented",
  "opt-in": "Opt-in, not run here",
  "not-connected": "Not connected",
};

export const REAL_VS_MOCK: Array<{ kind: RealVsMockKind; title: string; body: string }> = [
  {
    kind: "mock",
    title: "Hosted demo runs in mock mode",
    body: "The public demo and CI run with LLM_MODE=mock: deterministic, no API key, no model calls. The live status above shows the mode the API actually reports.",
  },
  {
    kind: "mock",
    title: "Structuring is rule-based, not an LLM",
    body: "In mock mode, symptom extraction is a deterministic rule-based baseline with a small fixed lexicon; report text comes from a deterministic builder.",
  },
  {
    kind: "opt-in",
    title: "Real mode: opt-in OpenAI integration",
    body: "LLM_MODE=real calls OpenAI with timeouts, bounded retries and JSON-schema validation, and never falls back to mock. It is not exercised in CI or on the hosted demo.",
  },
  {
    kind: "not-connected",
    title: "RAG is not connected to the API",
    body: "A retrieval agent and in-memory store exist and are tested, but the API pipeline does not use them. Retrieval quality is unmeasured.",
  },
  {
    kind: "mock",
    title: "Embeddings are mock vectors",
    body: "Embeddings are SHA-256-derived, so retrieval ranking carries no semantic meaning.",
  },
  {
    kind: "real",
    title: "Safety rules and staff review are implemented",
    body: "The rule-based guard, escalation rules, clinic-scoped review queue, evidence timeline and FHIR export run for real and are tested, within the limits listed on the system card.",
  },
];

export const NOT_CLAIMED =
  "Not a medical device. Not clinically validated, no clinical-accuracy claim, no HIPAA or other compliance claim, and not production-ready. Synthetic data only.";

export interface Capability {
  id: string;
  title: string;
  status: string; // as in docs/project_status.md §3
  statusTone: "success" | "warning";
  summary: string;
  limits: string;
  evidence: EvidenceLink[];
}

export const CAPABILITIES: Capability[] = [
  {
    id: "rbac",
    title: "Clinic-scoped RBAC",
    status: "RBAC complete · isolation partial",
    statusTone: "warning",
    summary: "Server-side clinic_staff / clinic_admin checks on every review endpoint, re-read from the database on each request; every intake query filters on the caller's clinic.",
    limits: "Operator-issued tokens, no login flow or SSO. All patient intakes go to one seeded clinic.",
    evidence: [
      { label: "Auth, roles & clinic isolation", href: "docs/auth.md#roles-and-clinic-isolation" },
      { label: "RBAC tests", href: "tests/test_auth_rbac.py" },
      { label: "Review-queue isolation tests", href: "tests/test_review_queue.py" },
    ],
  },
  {
    id: "safety-guard",
    title: "Rule-based safety guard",
    status: "Complete · rule-based scope",
    statusTone: "success",
    summary: "Blocks diagnostic certainty and prescription/dosing content, masks PHI patterns in report text and adds emergency guidance.",
    limits: "Keyword/regex rules, not a model. Labelled gaps are recorded, not fixed.",
    evidence: [
      { label: "System card: safety rules", href: "/system-card#safety-rules" },
      { label: "Safety guard tests", href: "tests/test_safety_guard.py" },
      { label: "Safety & escalation evaluation", href: "docs/evaluation_benchmark.md#safety--escalation-evaluation-issue-32" },
    ],
  },
  {
    id: "escalation",
    title: "Escalation and human review",
    status: "Complete · rule-based scope",
    statusTone: "success",
    summary: "Emergency signals, blocked output and low confidence set needs review with reason codes; staff resolve each flagged intake as reviewed or escalated.",
    limits: "Only needs-review intakes can be transitioned. Rules miss paraphrases outside their patterns.",
    evidence: [
      { label: "System card: escalation rules", href: "/system-card#escalation-rules" },
      { label: "Escalation rules (#29)", href: "docs/data_model.md#escalation-rules-29" },
      { label: "Allowed transitions", href: "docs/review_queue_api.md#allowed-transitions" },
      { label: "Escalation tests", href: "tests/test_escalation.py" },
    ],
  },
  {
    id: "timeline",
    title: "Evidence timeline",
    status: "Partial · explainability",
    statusTone: "warning",
    summary: "Per intake: the triggered rule, recorded matches highlighted in the input, processing provenance, any webhook delivery attempts and staff transitions.",
    limits: "Stage timings are not persisted and the report does not cite retrieval sources.",
    evidence: [
      { label: "Evidence & timeline API (#41)", href: "docs/review_queue_api.md#intake-evidence--timeline-41" },
      { label: "Timeline tests", href: "tests/test_timeline.py" },
    ],
  },
  {
    id: "fhir",
    title: "FHIR R4 export",
    status: "Partial · export only",
    statusTone: "warning",
    summary: "Clinic-scoped R4 Bundle of one intake (QuestionnaireResponse, Questionnaire, Task, Organization, Device, Provenance), validated in CI against the pinned R4 JSON Schema.",
    limits: "No FHIR server, inbound FHIR, Patient/Condition resources or coding.",
    evidence: [
      { label: "FHIR mapping", href: "docs/interoperability/fhir_mapping.md" },
      { label: "Not mapped", href: "docs/interoperability/fhir_mapping.md#deliberately-not-mapped" },
      { label: "FHIR export tests", href: "tests/test_fhir_export.py" },
    ],
  },
  {
    id: "webhook",
    title: "Signed webhook",
    status: "Partial · conditional",
    statusTone: "warning",
    summary: "When a receiver is configured, an escalation triggers one HMAC-SHA256-signed, PHI-free notification, with an idempotency key, bounded retries and a delivery log.",
    limits: "Single receiver, no automatic resend, not a delivery guarantee. Disabled on the hosted demo.",
    evidence: [
      { label: "Webhook design", href: "docs/escalation_webhook.md" },
      { label: "Webhook limitations", href: "docs/escalation_webhook.md#limitations" },
      { label: "Webhook tests", href: "tests/test_webhook.py" },
    ],
  },
  {
    id: "evaluation",
    title: "CI-gated evaluation",
    status: "Partial · mock mode",
    statusTone: "warning",
    summary: "The safety & escalation and extraction suites run in CI on every PR; the system card shows a committed snapshot of their results that a test keeps in sync.",
    limits: "Tiny synthetic sets in mock mode; the extraction result is in-sample. Not clinical or model accuracy.",
    evidence: [
      { label: "System card: evaluation", href: "/system-card#evaluation" },
      { label: "CI workflow", href: ".github/workflows/ci.yml" },
      { label: "Snapshot sync test", href: "tests/test_system_card.py" },
      { label: "Evaluation harness", href: "docs/evaluation_benchmark.md" },
    ],
  },
];
