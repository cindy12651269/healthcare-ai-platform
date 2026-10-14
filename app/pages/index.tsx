import Link from "next/link";
import AppShell from "../components/AppShell";
import { Wait } from "../components/ApiStatus";
import SystemStatus from "../components/SystemStatus";
import { Card, DataTable, Tag } from "../components/ui";
import type { StatusTone } from "../components/ui";
import { waitForApi } from "../services/api";
import { DEMO_MODE, DEMO_STAFF, SCENARIO_PRESETS } from "../services/demo";
import {
  CAPABILITIES,
  MATURITY_LABELS,
  Maturity,
  NOT_CLAIMED,
  REAL_VS_MOCK,
  REAL_VS_MOCK_LABELS,
  RealVsMockKind,
  WEBHOOK_BRANCH,
  WORKFLOW,
  evidenceHref,
} from "../services/evidence";

// Product dashboard (#69): what the product does, how an intake moves through it, what is real vs. mock,
// and the evidence behind each capability. Content and claims live in services/evidence.ts.

const MATURITY_TONES: Record<Maturity, StatusTone> = {
  implemented: "success",
  mock: "info",
  limited: "neutral",
  conditional: "escalated",
};

const REAL_VS_MOCK_TONES: Record<RealVsMockKind, StatusTone> = {
  mock: "info",
  real: "success",
  "opt-in": "warning",
  "not-connected": "neutral",
};

interface DashboardProps {
  demoMode?: boolean; // injectable for tests; defaults to NEXT_PUBLIC_DEMO_MODE
  checkApi?: Wait; // injectable for tests (#67 cold start)
}

export default function Dashboard({ demoMode = DEMO_MODE, checkApi = waitForApi }: DashboardProps) {
  return (
    <AppShell title="Product Dashboard" current="/" width="workspace">
      <section className="hero" aria-labelledby="hero-heading">
        <div className="hero-copy">
          <p className="eyebrow">Pre-visit intake · human review · synthetic demo</p>
          <h1 id="hero-heading">Pre-visit patient intake, rule-checked and routed to clinic staff for human review</h1>
          <p className="hero-lead">
            Patients describe their symptoms before a visit. The platform structures the intake, checks the generated
            report against safety rules and flags anything risky for clinic staff, who review it with the evidence and
            can export it as FHIR R4.
          </p>
          <div className="cta-row">
            <Link className="btn btn-primary" href="/intake">
              Try Patient Intake
            </Link>
            <Link className="btn btn-secondary" href="/staff">
              Explore Staff Workflow
            </Link>
          </div>
          <p className="muted small" data-testid="staff-cta-note">
            The staff workflow needs an access token issued on request by the demo operator. Without one, the system
            card and the patient intake are fully open.
          </p>
        </div>
        {/* Starts waking the API while the visitor reads this page (#67); the page's only /health poller */}
        <SystemStatus wait={checkApi} />
      </section>

      <div className="dashboard-grid">
        <Card aria-labelledby="workflow-heading" className="workflow-card">
          <h2 id="workflow-heading">How an intake moves through the system</h2>
          <p className="muted">
            Seven stages from patient to clinic. Labels show what is implemented, what runs in mock mode on this demo and
            where the demo has limits.
          </p>
          <ol className="flow" data-testid="workflow" aria-label="Workflow stages">
            {WORKFLOW.map((stage, i) => (
              <li key={stage.id} className="flow-step" data-stage={stage.id}>
                <span className="flow-marker" aria-hidden="true">
                  {i + 1}
                </span>
                <div className="flow-body">
                  <h3>{stage.title}</h3>
                  <p className="flow-tags">
                    {stage.tags.map((t) => (
                      <Tag key={t} tone={MATURITY_TONES[t]}>
                        {MATURITY_LABELS[t]}
                      </Tag>
                    ))}
                  </p>
                  <p>{stage.summary}</p>
                  <p className="muted small">{stage.note}</p>
                  {stage.id === WEBHOOK_BRANCH.after && (
                    <div className="flow-branch" data-testid="webhook-branch">
                      <p className="flow-branch-title">
                        <Tag tone={MATURITY_TONES.conditional}>Conditional branch</Tag> <strong>{WEBHOOK_BRANCH.title}</strong>
                      </p>
                      <p>{WEBHOOK_BRANCH.summary}</p>
                      <p className="muted small">{WEBHOOK_BRANCH.note}</p>
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </Card>

        <Card as="aside" aria-labelledby="real-mock-heading" className="real-mock" data-testid="real-vs-mock">
          <h2 id="real-mock-heading">What is real vs. mock</h2>
          <ul className="real-mock-list">
            {REAL_VS_MOCK.map((row) => (
              <li key={row.title} data-kind={row.kind}>
                <Tag tone={REAL_VS_MOCK_TONES[row.kind]}>{REAL_VS_MOCK_LABELS[row.kind]}</Tag>
                <strong>{row.title}</strong>
                <p>{row.body}</p>
              </li>
            ))}
          </ul>
          <p className="not-claimed" data-testid="not-claimed">
            {NOT_CLAIMED}
          </p>
          <p className="small">
            <Link href="/system-card">Read the system card</Link> for rules, evaluation results and limitations.
          </p>
        </Card>
      </div>

      <section aria-labelledby="capabilities-heading" className="capabilities">
        <h2 id="capabilities-heading">Capabilities and their evidence</h2>
        <p className="muted">
          Each card links to the committed code, tests or documentation behind it. Status follows the project&apos;s
          capability matrix.
        </p>
        <ul className="capability-grid" data-testid="capabilities">
          {CAPABILITIES.map((c) => (
            <li key={c.id} className="card capability" data-capability={c.id}>
              <h3>{c.title}</h3>
              <p>
                <Tag tone={c.statusTone}>{c.status}</Tag>
              </p>
              <p>{c.summary}</p>
              <p className="muted small">
                <strong>Limits:</strong> {c.limits}
              </p>
              <p className="evidence-label">Evidence</p>
              <ul className="evidence-links">
                {c.evidence.map((e) => (
                  <li key={e.href}>
                    <a href={evidenceHref(e.href)} data-evidence={e.href}>
                      {e.label}
                    </a>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      </section>

      <div className="dashboard-grid dashboard-grid-even">
        <Card aria-labelledby="scenarios-heading">
          <h2 id="scenarios-heading">Four scenarios to try</h2>
          <ul className="scenario-list">
            {SCENARIO_PRESETS.map((p) => (
              <li key={p.id}>
                <strong>{p.label}</strong>: {p.expect}
              </li>
            ))}
          </ul>
          <p className="muted">Then sign in as staff to see the intake in the queue, its evidence timeline and FHIR export.</p>
        </Card>

        <Card aria-labelledby="access-heading" data-testid="access-policy">
          <h2 id="access-heading">Demo access</h2>
          <p>
            Staff sign-in needs a short-lived access token for one of the seeded synthetic staff users. Tokens are issued
            on request by the demo operator and are never published: there is no public sign-up, guest login or shared
            password.
          </p>
          {demoMode && (
            <div data-testid="demo-staff">
              <h3 id="demo-staff-heading">Demo staff accounts</h3>
              <p className="muted">
                Synthetic staff users seeded in this demo environment. Each clinic is pre-loaded with intakes in every
                review status; staff see only their own clinic.
              </p>
              <DataTable
                label="Demo staff accounts"
                layout="stack"
                rows={DEMO_STAFF}
                rowKey={(u) => u.userId}
                columns={[
                  { key: "user", header: "User", render: (u) => <code>{u.userId}</code> },
                  { key: "clinic", header: "Clinic", render: (u) => u.clinicId },
                  { key: "role", header: "Role", render: (u) => u.role },
                ]}
              />
              <p className="muted">
                Sign-in uses a short-lived bearer token issued by the demo operator for one of these users. Tokens are
                not published on this page or in the site code; ask the person who shared this demo.
              </p>
            </div>
          )}
        </Card>
      </div>
    </AppShell>
  );
}
