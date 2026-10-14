import Head from "next/head";
import Link from "next/link";
import ApiStatus from "../components/ApiStatus";
import SiteNav from "../components/SiteNav";
import { waitForApi } from "../services/api";
import { DEMO_MODE, DEMO_STAFF, SCENARIO_PRESETS } from "../services/demo";

// Guided demo landing page (#43): entry points and the end-to-end workflow.
const WORKFLOW: Array<[string, string]> = [
  ["Patient intake", "A synthetic patient describes symptoms and gives consent."],
  ["AI processing", "Mock mode: a deterministic rule-based extractor structures the intake (not an LLM)."],
  ["Safety & escalation", "Rule-based guard blocks diagnosis/prescription content, adds emergency guidance, masks PHI; escalation rules flag intakes for review."],
  ["Staff review", "Clinic staff see only their clinic's queue and mark flagged intakes reviewed or escalated."],
  ["Evidence timeline", "Why it was flagged, the recorded evidence, provenance, webhook delivery and staff actions."],
  ["FHIR export", "A validated FHIR R4 Bundle of the intake, previewed and downloaded (synthetic demo data)."],
];

interface LandingProps {
  demoMode?: boolean; // injectable for tests; defaults to NEXT_PUBLIC_DEMO_MODE
  checkApi?: typeof waitForApi; // injectable for tests (#67 cold start)
}

export default function Landing({ demoMode = DEMO_MODE, checkApi = waitForApi }: LandingProps) {
  return (
    <>
      <Head>
        <title>Guided Demo | Healthcare AI Platform</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      <header className="site-header">
        <div className="container">
          <span className="brand">Healthcare AI Platform</span>
          <span className="badges">
            <span className="badge">Demo · synthetic data only</span>
          </span>
        </div>
        <div className="container">
          <SiteNav current="/" />
        </div>
      </header>

      <main className="container">
        {/* Starts waking the API while the visitor reads this page (#67) */}
        <ApiStatus wait={checkApi} />
        <section className="intro">
          <h1>Pre-visit intake with human review — guided demo</h1>
          <p>
            A patient-facing intake that is structured, safety-checked and escalated to clinic staff when needed. Every
            step runs on synthetic data in deterministic mock mode.
          </p>
        </section>

        <section className="card" aria-labelledby="entry-heading">
          <h2 id="entry-heading">Start here</h2>
          <div className="entry-points">
            <Link className="entry" href="/intake">
              <strong>Patient</strong>
              <span>Submit a synthetic intake, or pick one of the four scenarios.</span>
            </Link>
            <Link className="entry" href="/staff">
              <strong>Staff</strong>
              <span>
                Review your clinic&apos;s queue, evidence timeline and FHIR export. Needs an access token issued on
                request by the demo operator.
              </span>
            </Link>
            <Link className="entry" href="/system-card">
              <strong>System card</strong>
              <span>Pipeline, safety and escalation rules, evaluation results, limitations.</span>
            </Link>
          </div>
        </section>

        <section className="card" aria-labelledby="workflow-heading">
          <h2 id="workflow-heading">How it works</h2>
          <ol className="workflow" data-testid="workflow">
            {WORKFLOW.map(([title, body]) => (
              <li key={title}>
                <strong>{title}</strong> — {body}
              </li>
            ))}
          </ol>
        </section>

        <section className="card" aria-labelledby="scenarios-heading">
          <h2 id="scenarios-heading">Four scenarios to try</h2>
          <ul>
            {SCENARIO_PRESETS.map((p) => (
              <li key={p.id}>
                <strong>{p.label}</strong>: {p.expect}
              </li>
            ))}
          </ul>
          <p className="muted">Then sign in as staff to see the intake in the queue, its evidence timeline and FHIR export.</p>
        </section>

        {demoMode && (
          <section className="card" aria-labelledby="demo-staff-heading" data-testid="demo-staff">
            <h2 id="demo-staff-heading">Demo staff accounts</h2>
            <p className="muted">
              Synthetic staff users seeded in this demo environment. Each clinic is pre-loaded with intakes in every
              review status; staff see only their own clinic.
            </p>
            <table>
              <thead>
                <tr>
                  <th>User</th>
                  <th>Clinic</th>
                  <th>Role</th>
                </tr>
              </thead>
              <tbody>
                {DEMO_STAFF.map((u) => (
                  <tr key={u.userId}>
                    <td>
                      <code>{u.userId}</code>
                    </td>
                    <td>{u.clinicId}</td>
                    <td>{u.role}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="muted">
              Sign-in uses a short-lived bearer token issued by the demo operator for one of these users. Tokens are not
              published on this page or in the site code; ask the person who shared this demo.
            </p>
          </section>
        )}
      </main>

      <footer className="site-footer container">
        Portfolio demonstration. Not a medical device; not for real patient data.
      </footer>
    </>
  );
}
