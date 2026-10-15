import Link from "next/link";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import FhirExport from "./FhirExport";
import IntakeEvidence from "./IntakeEvidence";
import { Alert, Button, Card, DataTable, EmptyState, LoadingMessage, ReasonList, StatusBadge } from "./ui";
import { formatStaffDateTime, intakeRef } from "../services/format";
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

// Status tabs (#71). The queue is loaded once per clinic with the existing unfiltered list call
// (GET …/intakes, not paginated) and filtered here, so every count is taken from that same response.
const FILTERS: Array<[ReviewStatus | "", string]> = [
  ["needs_review", "Needs review"],
  ["reviewed", "Reviewed"],
  ["escalated", "Escalated"],
  ["submitted", "Submitted"],
  ["", "All"],
];

const CONFIRM_COPY: Record<TransitionTarget, { title: string; body: string; action: string }> = {
  reviewed: {
    title: "Mark this intake reviewed?",
    body: "It leaves the needs-review queue. Reviewed and escalated are final in this workflow.",
    action: "Confirm: mark reviewed",
  },
  escalated: {
    title: "Mark this intake escalated?",
    body: "It is recorded as escalated for clinical follow-up. Reviewed and escalated are final in this workflow.",
    action: "Confirm: mark escalated",
  },
};

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

// The API answers 401 "Invalid or expired token" for both cases, so the UI cannot tell them apart
const SIGN_IN_MESSAGES: Partial<Record<string, string>> = {
  unauthorized:
    "This token was not accepted: it is invalid or has expired. Tokens are short-lived; ask the demo operator for a new one.",
  forbidden: "This token is valid but has no staff access. Ask the demo operator for a staff token.",
  unavailable: STAFF_MESSAGES.unavailable,
};

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
      setError(SIGN_IN_MESSAGES[result.kind] ?? result.message);
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
        <p className="muted small" id="token-help">
          Paste the short-lived access token the demo operator issued to you. It stays in this tab&apos;s memory only:
          it is never saved to browser storage or cookies, and it is gone when you sign out, reload or close the tab.
        </p>
        <label className="field-label" htmlFor="staff-token">
          Access token
        </label>
        <input
          id="staff-token"
          className="staff-input"
          type="password"
          autoComplete="off"
          aria-describedby={error ? "token-help token-error" : "token-help"}
          aria-invalid={error ? true : undefined}
          value={token}
          onChange={(e) => setToken(e.target.value)}
          disabled={pending}
        />
        {error && (
          <Alert variant="error" id="token-error" title="Sign-in failed">
            <p>{error}</p>
          </Alert>
        )}
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
  const queueHeadingRef = useRef<HTMLHeadingElement>(null);
  const lastOpened = useRef<string | null>(null);

  // 401 at any point ends the session; other errors are shown in place
  const handleAuth = useCallback(
    (kind: string) => {
      if (kind === "unauthorized") onSignOut(STAFF_MESSAGES.unauthorized);
    },
    [onSignOut],
  );

  // Only the signed-in clinic is ever requested; the server enforces membership (403 otherwise)
  const requestKey = `${clinicId}|${reloadKey}`;
  useEffect(() => {
    let active = true;
    api.listIntakes(token, clinicId, null).then((result) => {
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
  }, [api, token, clinicId, requestKey, handleAuth]);
  const queue: Load<IntakeSummary[]> =
    loaded && loaded.key === requestKey ? loaded.result : { status: "loading" };

  const all = queue.status === "ready" ? queue.data : [];
  const count = (f: ReviewStatus | "") => (f ? all.filter((r) => r.review_status === f).length : all.length);
  const rows = filter ? all.filter((r) => r.review_status === filter) : all;
  const role = me.memberships.find((m) => m.clinic_id === clinicId)?.role;

  function open(id: string) {
    lastOpened.current = id;
    setSelectedId(id);
  }
  const restoreFocus = useRef(false);
  function backToQueue() {
    restoreFocus.current = true;
    setSelectedId(null);
  }
  // After the queue is shown again (post-commit), return focus to the row that was opened, or the heading
  useEffect(() => {
    if (selectedId || !restoreFocus.current) return;
    restoreFocus.current = false;
    const row = lastOpened.current && document.querySelector<HTMLButtonElement>(`[data-intake-id="${lastOpened.current}"]`);
    (row || queueHeadingRef.current)?.focus();
  }, [selectedId]);

  return (
    <>
      <Card aria-label="Signed in" className="identity-bar">
        <p>
          Signed in as <strong>{me.email}</strong> · clinic <strong>{clinicId}</strong>
          {role ? ` · ${role}` : ""}
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

      <div className="workspace" data-view={selectedId ? "detail" : "queue"}>
        <Card aria-labelledby="queue-heading" className="workspace-queue">
          <h2 id="queue-heading" ref={queueHeadingRef} tabIndex={-1}>
            Review queue
          </h2>
          <div className="status-tabs" role="group" aria-label="Filter by review status">
            {FILTERS.map(([value, label]) => (
              <Button
                key={label}
                size="sm"
                aria-pressed={filter === value}
                data-filter={value || "all"}
                onClick={() => {
                  setSelectedId(null);
                  setFilter(value);
                }}
              >
                {label}
                {queue.status === "ready" && <span className="tab-count">{count(value)}</span>}
              </Button>
            ))}
          </div>
          {queue.status === "ready" && (
            <p className="muted small" data-testid="queue-scope">
              Counts are from the {all.length} intake{all.length === 1 ? "" : "s"} returned for clinic {clinicId} when
              the queue was loaded. Times are in UTC.
            </p>
          )}

          <div aria-live="polite">
            {queue.status === "loading" && <LoadingMessage>Loading intakes…</LoadingMessage>}
            {queue.status === "error" && (
              <Alert variant="error">
                <p>{queue.message}</p>
                <Button onClick={() => setReloadKey((k) => k + 1)}>Retry</Button>
              </Alert>
            )}
            {queue.status === "ready" && rows.length === 0 && <EmptyState title="No intakes with this status." />}
          </div>

          {queue.status === "ready" && rows.length > 0 && (
            <DataTable
              label="Review queue"
              layout="stack"
              rows={rows}
              rowKey={(row) => row.id}
              rowProps={(row) => ({ "aria-selected": row.id === selectedId })}
              columns={[
                {
                  key: "intake",
                  header: "Intake",
                  render: (row) => (
                    <Button size="sm" data-intake-id={row.id} aria-label={`Open intake ${intakeRef(row.id)}`} onClick={() => open(row.id)}>
                      {intakeRef(row.id)}
                    </Button>
                  ),
                },
                { key: "status", header: "Status", render: (row) => <StatusBadge status={row.review_status} /> },
                { key: "reason", header: "Escalation reason", render: (row) => <ReasonList reasons={row.escalation_reason} /> },
                { key: "received", header: "Received (UTC)", render: (row) => formatStaffDateTime(row.created_at) },
              ]}
            />
          )}
        </Card>

        <div className="workspace-detail">
          {selectedId ? (
            <IntakeDetailView
              key={selectedId}
              api={api}
              token={token}
              clinicId={clinicId}
              intakeId={selectedId}
              onAuthError={handleAuth}
              onTransitioned={() => setReloadKey((k) => k + 1)}
              onBack={backToQueue}
            />
          ) : (
            <Card className="detail-placeholder">
              <EmptyState title="Select an intake" description="Open an intake from the queue to see its evidence, timeline and actions." />
            </Card>
          )}
        </div>
      </div>
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
  onBack,
}: {
  api: StaffApi;
  token: string;
  clinicId: string;
  intakeId: string;
  onAuthError: (kind: string) => void;
  onTransitioned: () => void;
  onBack: () => void;
}) {
  const [detail, setDetail] = useState<Load<IntakeDetail>>({ status: "loading" });
  const [transition, setTransition] = useState<TransitionState>({ status: "idle" });
  const [confirming, setConfirming] = useState<TransitionTarget | null>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  const focusedOnce = useRef(false);

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

  // Move focus to the opened intake once (so keyboard and screen-reader users land on it)
  useEffect(() => {
    if (detail.status === "ready" && !focusedOnce.current) {
      focusedOnce.current = true;
      headingRef.current?.focus();
    }
  }, [detail.status]);
  useEffect(() => {
    if (confirming) confirmRef.current?.focus();
  }, [confirming]);

  async function handleTransition(target: TransitionTarget) {
    if (transition.status === "pending") return;
    setConfirming(null);
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

  const back = (
    <Button variant="ghost" className="back-to-queue" onClick={onBack}>
      ← Back to queue
    </Button>
  );

  if (detail.status === "loading") return <Card>{back}<LoadingMessage>Loading intake…</LoadingMessage></Card>;
  if (detail.status === "error")
    return (
      <Card>
        {back}
        <Alert variant="error">{detail.message}</Alert>
      </Card>
    );

  const intake = detail.data;
  const clinical = asObject(intake.structured.clinical_structuring);
  const sections = asObject(intake.report.report_sections);
  const safety = intake.safety;
  const actions = asStrings(safety.actions);
  const canTransition = intake.review_status === "needs_review";
  const pending = transition.status === "pending";

  return (
    <Card as="article" aria-labelledby="detail-heading" className="intake-detail">
      {back}
      <header className="detail-header">
        <h2 id="detail-heading" ref={headingRef} tabIndex={-1}>
          Intake {intakeRef(intake.id)}
        </h2>
        <div className="detail-status" data-testid="detail-status">
          <StatusBadge status={intake.review_status} />
          <ReasonList reasons={intake.escalation_reason} empty="No escalation reason" />
        </div>
        <dl className="kv">
          <dt>Intake ID</dt>
          <dd>
            <code>{intake.id}</code>
          </dd>
          <dt>Received</dt>
          <dd>{formatStaffDateTime(intake.created_at)}</dd>
          <dt>Last updated</dt>
          <dd>{formatStaffDateTime(intake.updated_at)}</dd>
        </dl>
      </header>

      <section aria-labelledby="actions-heading" className="detail-actions">
        <h3 id="actions-heading">Review action</h3>
        <div aria-live="polite">
          {pending && <LoadingMessage>Updating status…</LoadingMessage>}
          {transition.status === "done" && (
            <Alert variant="success">Marked {transition.target === "reviewed" ? "reviewed" : "escalated"}. The queue and timeline were refreshed.</Alert>
          )}
          {transition.status === "error" && <Alert variant="error">{transition.message}</Alert>}
        </div>
        {canTransition ? (
          confirming ? (
            <div className="confirm-step" role="group" aria-labelledby="confirm-title" data-testid="confirm-step">
              <p id="confirm-title">
                <strong>{CONFIRM_COPY[confirming].title}</strong>
              </p>
              <p className="muted small">{CONFIRM_COPY[confirming].body}</p>
              <div className="button-row">
                <Button
                  ref={confirmRef}
                  variant={confirming === "escalated" ? "danger" : "primary"}
                  disabled={pending}
                  onClick={() => handleTransition(confirming)}
                >
                  {CONFIRM_COPY[confirming].action}
                </Button>
                <Button disabled={pending} onClick={() => setConfirming(null)}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <div className="button-row">
              <Button variant="primary" disabled={pending} onClick={() => setConfirming("reviewed")}>
                Mark reviewed
              </Button>
              <Button variant="danger" disabled={pending} onClick={() => setConfirming("escalated")}>
                Mark escalated
              </Button>
            </div>
          )
        ) : (
          <p className="muted">Only intakes that need review can be marked reviewed or escalated.</p>
        )}
      </section>

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
    </Card>
  );
}
