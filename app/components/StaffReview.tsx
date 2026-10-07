import { FormEvent, useCallback, useEffect, useState } from "react";
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

const STATUS_LABELS: Record<string, string> = {
  submitted: "Submitted",
  needs_review: "Needs review",
  reviewed: "Reviewed",
  escalated: "Escalated",
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
    <form className="card" onSubmit={handleSubmit} aria-labelledby="signin-heading">
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
      {error && (
        <div className="alert alert-error" role="alert">
          {error}
        </div>
      )}
      <button type="submit" className="primary" disabled={pending}>
        {pending ? "Signing in…" : "Sign in"}
      </button>
    </form>
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
      <section className="card" aria-label="Signed in">
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
        <button type="button" className="secondary" onClick={() => onSignOut(null)}>
          Sign out
        </button>
      </section>

      <section className="card" aria-labelledby="queue-heading">
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
          {queue.status === "loading" && (
            <p className="status-loading" role="status">
              Loading intakes…
            </p>
          )}
          {queue.status === "error" && (
            <div className="alert alert-error" role="alert">
              <p>{queue.message}</p>
              <button type="button" className="secondary" onClick={() => setReloadKey((k) => k + 1)}>
                Retry
              </button>
            </div>
          )}
          {queue.status === "ready" && queue.data.length === 0 && (
            <p className="muted">No intakes with this status.</p>
          )}
        </div>

        {queue.status === "ready" && queue.data.length > 0 && (
          <table className="queue">
            <thead>
              <tr>
                <th>Received</th>
                <th>Status</th>
                <th>Escalation reason</th>
                <th>Intake</th>
              </tr>
            </thead>
            <tbody>
              {queue.data.map((row) => (
                <tr key={row.id} aria-selected={row.id === selectedId}>
                  <td>{row.created_at ? new Date(row.created_at).toLocaleString() : "—"}</td>
                  <td>{STATUS_LABELS[row.review_status] ?? row.review_status}</td>
                  <td>{row.escalation_reason ?? "—"}</td>
                  <td>
                    <button type="button" className="secondary" onClick={() => setSelectedId(row.id)}>
                      Open {row.id.slice(0, 8)}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

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

  if (detail.status === "loading") {
    return (
      <p className="status-loading" role="status">
        Loading intake…
      </p>
    );
  }
  if (detail.status === "error") {
    return (
      <div className="alert alert-error" role="alert">
        {detail.message}
      </div>
    );
  }

  const intake = detail.data;
  const clinical = asObject(intake.structured.clinical_structuring);
  const sections = asObject(intake.report.report_sections);
  const safety = intake.safety;
  const actions = asStrings(safety.actions);
  const canTransition = intake.review_status === "needs_review";
  const pending = transition.status === "pending";

  return (
    <article className="card" aria-labelledby="detail-heading">
      <h2 id="detail-heading">Intake {intake.id.slice(0, 8)}</h2>
      <dl className="kv">
        <dt>Review status</dt>
        <dd data-testid="detail-status">{STATUS_LABELS[intake.review_status] ?? intake.review_status}</dd>
        <dt>Escalation reason</dt>
        <dd>{intake.escalation_reason ?? "None"}</dd>
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

      <div aria-live="polite">
        {pending && (
          <p className="status-loading" role="status">
            Updating status…
          </p>
        )}
        {transition.status === "done" && (
          <div className="alert alert-warn" role="status">
            Marked {transition.target === "reviewed" ? "reviewed" : "escalated"}.
          </div>
        )}
        {transition.status === "error" && (
          <div className="alert alert-error" role="alert">
            {transition.message}
          </div>
        )}
      </div>

      {canTransition ? (
        <div>
          <button type="button" className="primary" disabled={pending} onClick={() => handleTransition("reviewed")}>
            Mark reviewed
          </button>{" "}
          <button type="button" className="primary" disabled={pending} onClick={() => handleTransition("escalated")}>
            Mark escalated
          </button>
        </div>
      ) : (
        <p className="muted">Only intakes that need review can be marked reviewed or escalated.</p>
      )}
    </article>
  );
}
