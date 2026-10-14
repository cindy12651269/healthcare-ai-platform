import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import FhirExport from "./FhirExport";
import IntakeEvidence from "./IntakeEvidence";
import { Alert, Button, Card, DataTable, EmptyState, LoadingMessage, ReasonList, StatusBadge } from "./ui";
import {
  IntakeDetail,
  IntakeSummary,
  ReviewStatus,
  STAFF_MESSAGES,
  StaffApi,
  StaffMe,
  TransitionTarget,
  staffApi,
} from "../services/staffApi";

type JsonObject = Record<string, unknown>;

// Review statuses a staff member can filter the queue by ("" = all)
const FILTERS: Array<[ReviewStatus | "", string]> = [
  ["needs_review", "Needs review"],
  ["reviewed", "Reviewed"],
  ["escalated", "Escalated"],
  ["submitted", "Submitted (not flagged)"],
  ["", "All"],
];

const REPORT_SECTIONS: Array<[string, string]> = [
  ["overview", "Overview"],
  ["symptom_analysis", "Symptom analysis"],
  ["clinical_insights", "Clinical insights"],
  ["risk_summary", "Risk summary"],
  ["recommendations", "Recommendations"],
];

const asObject = (v: unknown): JsonObject | undefined =>
  v && typeof v === "object" && !Array.isArray(v) ? (v as JsonObject) : undefined;
const asStrings = (v: unknown): string[] =>
  Array.isArray(v) ? v.filter((s): s is string => typeof s === "string") : [];

interface Session {
  token: string;
  me: StaffMe;
  clinicId: string;
}

type Load<T> = { status: "loading" } | { status: "error"; message: string } | { status: "ready"; data: T };

type TransitionState =
  | { status: "idle" }
  | { status: "pending"; target: TransitionTarget }
  | { status: "done"; target: TransitionTarget }
  | { status: "error"; message: string };

interface StaffReviewProps {
  api?: StaffApi; // injectable for tests
}

// Staff review workflow (Issue #31): sign in with an operator-issued token (#28),
// then list, open and transition the clinic's intakes (#30). The token lives only in
// component state for this tab and is never persisted.
export default function StaffReview({ api = staffApi }: StaffReviewProps) {
  const [session, setSession] = useState<Session | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const signOut = useCallback((message: string | null = null) => {
    setSession(null);
    setNotice(message);
  }, []);

  if (!session) {
    return (
      <SignIn
        api={api}
        notice={notice}
        onSignedIn={(s) => {
          setNotice(null);
          setSession(s);
        }}
      />
    );
  }
  return <Workspace api={api} session={session} onSignOut={signOut} onSwitchClinic={setSession} />;
}

function SignIn({
  api,
  notice,
  onSignedIn,
}: {
  api: StaffApi;
  notice: string | null;
  onSignedIn: (s: Session) => void;
}) {
  const [token, setToken] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(notice);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const value = token.trim();
    if (!value) {
      setError("Please paste your staff access token.");
      return;
    }
    setPending(true);
    setError(null);
    const result = await api.fetchStaffMe(value);
    setPending(false);
    if (!result.ok) {
      setError(result.message);
      return;
    }
    const clinic = result.data.memberships[0];
    if (!clinic) {
      setError("Your account has no clinic membership. Ask your clinic admin for access.");
      return;
    }
    setToken("");
    onSignedIn({ token: value, me: result.data, clinicId: clinic.clinic_id });
  }

  return (
    <div className="signin-grid">
      <StaffAccessPolicy />
      <Card as="form" onSubmit={handleSubmit} aria-labelledby="signin-heading">
        <h2 id="signin-heading">Staff sign-in</h2>
        <p className="muted small">
          Paste the access token issued to you by your operator (<code>python -m api.auth issue-token</code>).
          It is kept only in this browser tab and is cleared when you sign out or reload.
        </p>
        <label className="field-label" htmlFor="staff-token">
          Access token
        </label>
        <input
          id="staff-token"
          className="staff-input"
          type="password"
          autoComplete="off"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          disabled={pending}
        />
        {error && <Alert variant="error">{error}</Alert>}
        <Button type="submit" variant="primary" disabled={pending}>
          {pending ? "Signing in…" : "Sign in"}
        </Button>
      </Card>
    </div>
  );
}

// Staff-access policy for public visitors (#67). Tokens are issued on request by the demo operator;
// there is deliberately no public token endpoint, guest login or shared password.
function StaffAccessPolicy() {
  return (
    <Card aria-labelledby="staff-access-heading" data-testid="staff-access-policy">
      <h2 id="staff-access-heading">Visiting the public demo?</h2>
      <p>
        Staff sign-in needs a short-lived access token for one of the seeded synthetic staff users. Tokens are issued
        on request by the demo operator and are never published: there is no public sign-up, guest login or shared
        password.
      </p>
      <p className="muted small">
        Without a token you can still submit a scenario on <Link href="/intake">Patient intake</Link> and read the{" "}
        <Link href="/system-card">System card</Link>. To see the staff queue, evidence timeline and FHIR export, ask the
        person who shared this demo for a token or a guided walkthrough.
      </p>
    </Card>
  );
}

function Workspace({
  api,
  session,
  onSignOut,
  onSwitchClinic,
}: {
  api: StaffApi;
  session: Session;
  onSignOut: (message?: string | null) => void;
  onSwitchClinic: (s: Session) => void;
}) {
  const { token, clinicId, me } = session;
  const [filter, setFilter] = useState<ReviewStatus | "">("needs_review");
  // Result tagged with the request it answers; a stale or missing tag means "loading"
  const [loaded, setLoaded] = useState<{ key: string; result: Load<IntakeSummary[]> } | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  // 401 at any point ends the session; other errors are shown in place
  const handleAuth = useCallback(
    (kind: string) => {
      if (kind === "unauthorized") onSignOut(STAFF_MESSAGES.unauthorized);
    },
    [onSignOut],
  );

  const requestKey = `${clinicId}|${filter}|${reloadKey}`;
  useEffect(() => {
    let active = true;
    api.listIntakes(token, clinicId, filter || null).then((result) => {
      if (!active) return;
      if (result.ok) {
        setLoaded({ key: requestKey, result: { status: "ready", data: result.data } });
      } else {
        handleAuth(result.kind);
        setLoaded({ key: requestKey, result: { status: "error", message: result.message } });
      }
    });
    return () => {
      active = false;
    };
  }, [api, token, clinicId, filter, requestKey, handleAuth]);
  const queue: Load<IntakeSummary[]> =
    loaded && loaded.key === requestKey ? loaded.result : { status: "loading" };

  const role = me.memberships.find((m) => m.clinic_id === clinicId)?.role;

  return (
    <>
      <Card aria-label="Signed in" className="identity-bar">
        <p>
          Signed in as <strong>{me.email}</strong> · clinic <strong>{clinicId}</strong>
          {role ? ` (${role})` : ""}
        </p>
        {me.memberships.length > 1 && (
          <label className="field-label">
            Clinic{" "}
            <select
              value={clinicId}
              onChange={(e) => {
                setSelectedId(null);
                onSwitchClinic({ ...session, clinicId: e.target.value });
              }}
            >
              {me.memberships.map((m) => (
                <option key={m.clinic_id} value={m.clinic_id}>
                  {m.clinic_id}
                </option>
              ))}
            </select>
          </label>
        )}
        <Button onClick={() => onSignOut(null)}>Sign out</Button>
      </Card>

      <Card aria-labelledby="queue-heading">
        <h2 id="queue-heading">Review queue</h2>
        <label className="field-label" htmlFor="status-filter">
          Status
        </label>
        <select
          id="status-filter"
          className="staff-input"
          value={filter}
          onChange={(e) => {
            setSelectedId(null);
            setFilter(e.target.value as ReviewStatus | "");
          }}
        >
          {FILTERS.map(([value, label]) => (
            <option key={label} value={value}>
              {label}
            </option>
          ))}
        </select>

        <div aria-live="polite">
          {queue.status === "loading" && <LoadingMessage>Loading intakes…</LoadingMessage>}
          {queue.status === "error" && (
            <Alert variant="error">
              <p>{queue.message}</p>
              <Button onClick={() => setReloadKey((k) => k + 1)}>Retry</Button>
            </Alert>
          )}
          {queue.status === "ready" && queue.data.length === 0 && <EmptyState title="No intakes with this status." />}
        </div>

        {queue.status === "ready" && queue.data.length > 0 && (
          <DataTable
            label="Review queue"
            layout="stack"
            rows={queue.data}
            rowKey={(row) => row.id}
            rowProps={(row) => ({ "aria-selected": row.id === selectedId })}
            columns={[
              {
                key: "received",
                header: "Received",
                render: (row) => (row.created_at ? new Date(row.created_at).toLocaleString() : "—"),
              },
              { key: "status", header: "Status", render: (row) => <StatusBadge status={row.review_status} /> },
              { key: "reason", header: "Escalation reason", render: (row) => <ReasonList reasons={row.escalation_reason} /> },
              {
                key: "open",
                header: "Intake",
                render: (row) => (
                  <Button size="sm" onClick={() => setSelectedId(row.id)}>
                    Open {row.id.slice(0, 8)}
                  </Button>
                ),
              },
            ]}
          />
        )}
      </Card>

      {selectedId && (
        <IntakeDetailView
          key={selectedId}
          api={api}
          token={token}
          clinicId={clinicId}
          intakeId={selectedId}
          onAuthError={handleAuth}
          onTransitioned={() => setReloadKey((k) => k + 1)}
        />
      )}
    </>
  );
}

function IntakeDetailView({
  api,
  token,
  clinicId,
  intakeId,
  onAuthError,
  onTransitioned,
}: {
  api: StaffApi;
  token: string;
  clinicId: string;
  intakeId: string;
  onAuthError: (kind: string) => void;
  onTransitioned: () => void;
}) {
  const [detail, setDetail] = useState<Load<IntakeDetail>>({ status: "loading" });
  const [transition, setTransition] = useState<TransitionState>({ status: "idle" });

  const load = useCallback(async () => {
    const result = await api.getIntake(token, clinicId, intakeId);
    if (result.ok) {
      setDetail({ status: "ready", data: result.data });
    } else {
      onAuthError(result.kind);
      setDetail({ status: "error", message: result.message });
    }
  }, [api, token, clinicId, intakeId, onAuthError]);

  useEffect(() => {
    let active = true;
    api.getIntake(token, clinicId, intakeId).then((result) => {
      if (!active) return;
      if (result.ok) {
        setDetail({ status: "ready", data: result.data });
      } else {
        onAuthError(result.kind);
        setDetail({ status: "error", message: result.message });
      }
    });
    return () => {
      active = false;
    };
  }, [api, token, clinicId, intakeId, onAuthError]);

  async function handleTransition(target: TransitionTarget) {
    if (transition.status === "pending") return;
    setTransition({ status: "pending", target });
    const result = await api.transitionIntake(token, clinicId, intakeId, target);
    if (result.ok) {
      setDetail({ status: "ready", data: result.data });
      setTransition({ status: "done", target });
      onTransitioned();
      return;
    }
    onAuthError(result.kind);
    setTransition({ status: "error", message: result.message });
    // The server's current state wins (e.g. another staff member resolved it first)
    if (result.kind === "conflict" || result.kind === "not_found") {
      await load();
      onTransitioned();
    }
  }

  if (detail.status === "loading") return <LoadingMessage>Loading intake…</LoadingMessage>;
  if (detail.status === "error") return <Alert variant="error">{detail.message}</Alert>;

  const intake = detail.data;
  const clinical = asObject(intake.structured.clinical_structuring);
  const sections = asObject(intake.report.report_sections);
  const safety = intake.safety;
  const actions = asStrings(safety.actions);
  const canTransition = intake.review_status === "needs_review";
  const pending = transition.status === "pending";

  return (
    <Card as="article" aria-labelledby="detail-heading">
      <h2 id="detail-heading">Intake {intake.id.slice(0, 8)}</h2>
      <dl className="kv">
        <dt>Review status</dt>
        <dd data-testid="detail-status">
          <StatusBadge status={intake.review_status} />
        </dd>
        <dt>Escalation reason</dt>
        <dd>
          <ReasonList reasons={intake.escalation_reason} empty="None" />
        </dd>
        <dt>Received</dt>
        <dd>{intake.created_at ? new Date(intake.created_at).toLocaleString() : "—"}</dd>
      </dl>

      <h3>Structured summary</h3>
      <dl className="kv">
        <dt>Reported concern</dt>
        <dd>{typeof clinical?.chief_complaint === "string" ? clinical.chief_complaint : "—"}</dd>
        <dt>Symptoms</dt>
        <dd>{asStrings(clinical?.symptoms).join(", ") || "None extracted"}</dd>
        <dt>Clinical summary</dt>
        <dd>{typeof clinical?.clinical_summary === "string" ? clinical.clinical_summary : "—"}</dd>
        <dt>Structuring confidence</dt>
        <dd>{typeof clinical?.confidence_level === "number" ? clinical.confidence_level : "—"}</dd>
      </dl>

      <h3>Report</h3>
      {REPORT_SECTIONS.map(([key, heading]) =>
        typeof sections?.[key] === "string" ? (
          <section className="report-section" key={key}>
            <h4>{heading}</h4>
            <p>{sections[key] as string}</p>
          </section>
        ) : null,
      )}

      <h3>Safety result</h3>
      <dl className="kv">
        <dt>Output allowed</dt>
        <dd>{safety.allowed === false ? "No (blocked)" : "Yes"}</dd>
        <dt>Severity</dt>
        <dd>{typeof safety.severity === "string" ? safety.severity : "—"}</dd>
        <dt>Guard actions</dt>
        <dd>{actions.join(", ") || "None"}</dd>
      </dl>

      {/* Keyed on status so a staff transition remounts it and reloads the timeline */}
      <IntakeEvidence
        key={intake.review_status}
        api={api}
        token={token}
        clinicId={clinicId}
        intakeId={intakeId}
        onAuthError={onAuthError}
      />

      {/* Keyed on status so a stale export is cleared after a transition */}
      <FhirExport
        key={`fhir-${intake.review_status}`}
        api={api}
        token={token}
        clinicId={clinicId}
        intakeId={intakeId}
        onAuthError={onAuthError}
      />

      <div aria-live="polite">
        {pending && <LoadingMessage>Updating status…</LoadingMessage>}
        {transition.status === "done" && (
          <Alert variant="success">Marked {transition.target === "reviewed" ? "reviewed" : "escalated"}.</Alert>
        )}
        {transition.status === "error" && <Alert variant="error">{transition.message}</Alert>}
      </div>

      {canTransition ? (
        <div className="button-row">
          <Button variant="primary" disabled={pending} onClick={() => handleTransition("reviewed")}>
            Mark reviewed
          </Button>
          <Button variant="danger" disabled={pending} onClick={() => handleTransition("escalated")}>
            Mark escalated
          </Button>
        </div>
      ) : (
        <p className="muted">Only intakes that need review can be marked reviewed or escalated.</p>
      )}
    </Card>
  );
}
