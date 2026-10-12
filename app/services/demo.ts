// Guided demo (#43). NEXT_PUBLIC_DEMO_MODE is a browser-visible boolean inlined at build time;
// it only controls whether demo hints are shown. It never carries a secret or a credential.
export const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

// Synthetic scenario presets. They only fill the intake form: the patient still ticks consent,
// client validation still runs, and submission goes through the normal POST /api/ingest pipeline.
export interface ScenarioPreset {
  id: "routine" | "emergency" | "prescription" | "vague";
  label: string;
  text: string;
  expect: string;
}

export const SCENARIO_PRESETS: ScenarioPreset[] = [
  {
    id: "routine",
    label: "Routine symptoms",
    text: "I have had a sore throat and a mild fever for two days.",
    expect: "Not flagged: stored as submitted, symptoms and duration extracted.",
  },
  {
    id: "emergency",
    label: "Emergency language",
    text: "I have chest pain and shortness of breath since this morning.",
    expect: "Emergency guidance shown; flagged for staff review (emergency_signal).",
  },
  {
    id: "prescription",
    label: "Prescription request",
    text: "Should I take 500 mg of amoxicillin for this cough?",
    expect: "Generated report blocked; safe acknowledgement shown; flagged (blocked_prescription).",
  },
  {
    id: "vague",
    label: "Vague / low confidence",
    text: "I just don't feel right and wanted to check in.",
    expect: "No lexicon symptom; confidence below 0.5; flagged (low_confidence).",
  },
];

// Seeded synthetic staff identities (db/seed_demo.py). Identities only: staff bearer tokens are
// issued by the demo operator (docs/deployment.md) and are never part of the frontend bundle.
export const DEMO_STAFF = [
  { userId: "demo-staff-a", clinicId: "default", role: "clinic_staff" },
  { userId: "demo-admin-a", clinicId: "default", role: "clinic_admin" },
  { userId: "demo-admin-b", clinicId: "demo-clinic-b", role: "clinic_admin" },
];
