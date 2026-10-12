import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import StaffReview from "../components/StaffReview";
import {
  IntakeDetail,
  IntakeSummary,
  IntakeTimeline,
  STAFF_MESSAGES,
  StaffApi,
  StaffResult,
  listIntakes,
  transitionIntake,
} from "../services/staffApi";

const TOKEN = "v1.payload.signature";

const ME = {
  user_id: "staff-a",
  email: "staff-a@example.test",
  memberships: [{ clinic_id: "default", role: "clinic_staff" }],
};

function summary(id: string, review_status: IntakeSummary["review_status"], reason: string | null): IntakeSummary {
  return {
    id,
    trace_id: `trace-${id}`,
    review_status,
    escalation_reason: reason,
    created_at: "2026-10-01T10:00:00Z",
    updated_at: "2026-10-01T10:00:00Z",
  };
}

function detail(over: Partial<IntakeDetail> = {}): IntakeDetail {
  return {
    ...summary("flagged-0001", "needs_review", "emergency_signal"),
    clinic_id: "default",
    structured: {
      clinical_structuring: {
        chief_complaint: "Chest pain since this morning.",
        symptoms: ["chest pain"],
        clinical_summary: "Short history of chest pain.",
        confidence_level: 0.9,
      },
    },
    report: {
      report_sections: {
        overview: "Pre-visit intake received.",
        symptom_analysis: "Symptoms noted: chest pain.",
        clinical_insights: "Not a medical assessment.",
        risk_summary: "Seek urgent care if severe.",
        recommendations: "Share notes with your care team.",
      },
    },
    safety: { allowed: true, actions: ["add_emergency_guidance"], reasons: [], severity: "high" },
    ...over,
  };
}

function timeline(over: Partial<IntakeTimeline> = {}): IntakeTimeline {
  return {
    intake_id: "flagged-0001",
    clinic_id: "default",
    review_status: "needs_review",
    evidence: {
      original_input: "Chest pain since this morning.",
      extracted: { symptoms: ["chest pain"], duration: null, onset: "since this morning", severity: null,
        red_flags: ["chest pain"], confidence_level: 0.7 },
      recorded_matches: [
        { type: "EMERGENCY", detail: "Emergency or crisis signal detected", match: "chest pain", found_in_input: true },
        { type: "EMERGENCY", detail: "Emergency or crisis signal detected", match: "report only", found_in_input: false },
      ],
      escalation_rules: [
        { reason: "emergency_signal", rule: "Emergency or crisis language in the intake or the generated report",
          evidence: { guard_action_recorded: true } },
      ],
      provenance: { execution_mode: "mock", model_version: "mock", prompt_version: "deterministic_rule_based_baseline_v1",
        pipeline_version: "v0.1.0", run_id: "run-1" },
    },
    events: [
      { kind: "submitted", at: "2026-10-01T09:59:59Z", at_source: "intake.timestamp", details: {} },
      { kind: "processed", at: "2026-10-01T10:00:00Z", at_source: "record.created_at",
        details: { execution_mode: "mock", model_version: "mock", run_id: "run-1" } },
      { kind: "safety_evaluated", at: "2026-10-01T10:00:00Z", at_source: "record.created_at",
        details: { actions: ["add_emergency_guidance"], reason_types: ["EMERGENCY"], severity: "high" } },
      { kind: "escalation_decision", at: "2026-10-01T10:00:00Z", at_source: "record.created_at",
        details: { required: true, reasons: ["emergency_signal"] } },
      { kind: "webhook_delivery", at: "2026-10-01T10:00:01Z", at_source: "webhook_deliveries.created_at",
        details: { event_type: "intake.escalated", status: "failed", attempts: 3, last_error: "timeout" } },
      { kind: "staff_transition", at: "2026-10-01T10:05:00Z", at_source: "review_events.created_at",
        details: { actor_id: "admin-a", from_status: "needs_review", to_status: "escalated" } },
    ],
    notes: [],
    ...over,
  };
}

const FHIR_BUNDLE = {
  resourceType: "Bundle",
  type: "collection",
  entry: [{ fullUrl: "urn:uuid:1", resource: { resourceType: "Task", status: "ready", intent: "order" } }],
};

const ok = <T,>(data: T): StaffResult<T> => ({ ok: true, data });
const fail = (kind: keyof typeof STAFF_MESSAGES, status?: number): StaffResult<never> => ({
  ok: false,
  kind,
  status,
  message: STAFF_MESSAGES[kind],
});

function deferred<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => (resolve = r));
  return { promise, resolve };
}

function makeApi(over: Partial<Record<keyof StaffApi, unknown>> = {}) {
  return {
    fetchStaffMe: vi.fn().mockResolvedValue(ok(ME)),
    listIntakes: vi.fn().mockResolvedValue(ok([summary("flagged-0001", "needs_review", "emergency_signal")])),
    getIntake: vi.fn().mockResolvedValue(ok(detail())),
    transitionIntake: vi.fn(),
    getIntakeTimeline: vi.fn().mockResolvedValue(ok(timeline())),
    exportIntakeFhir: vi.fn().mockResolvedValue(ok(FHIR_BUNDLE)),
    ...over,
  } as unknown as StaffApi & Record<keyof StaffApi, ReturnType<typeof vi.fn>>;
}

async function signIn(api: StaffApi, token = TOKEN) {
  const user = userEvent.setup();
  render(<StaffReview api={api} />);
  await user.type(screen.getByLabelText("Access token"), token);
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  return user;
}

async function openFirst(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole("button", { name: /^Open / }));
  return screen.findByRole("heading", { name: /^Intake / });
}

describe("StaffReview sign-in", () => {
  it("signs in with the staff token and loads the own-clinic needs_review queue", async () => {
    const api = makeApi();
    await signIn(api);

    expect(api.fetchStaffMe).toHaveBeenCalledWith(TOKEN);
    expect(await screen.findByText("staff-a@example.test")).toBeInTheDocument();
    expect(api.listIntakes).toHaveBeenCalledWith(TOKEN, "default", "needs_review");
    const rows = within(await screen.findByRole("table")).getAllByRole("row");
    expect(rows).toHaveLength(2); // header + one intake
    expect(rows[1]).toHaveTextContent("Needs review");
    expect(rows[1]).toHaveTextContent("emergency_signal");
    // The token is never rendered back into the page
    expect(document.body.innerHTML).not.toContain(TOKEN);
  });

  it("shows an error and stays signed out for an invalid token", async () => {
    const api = makeApi({ fetchStaffMe: vi.fn().mockResolvedValue(fail("unauthorized", 401)) });
    await signIn(api, "bad-token");

    expect(await screen.findByRole("alert")).toHaveTextContent(STAFF_MESSAGES.unauthorized);
    expect(screen.getByRole("heading", { name: "Staff sign-in" })).toBeInTheDocument();
    expect(api.listIntakes).not.toHaveBeenCalled();
  });

  it("rejects an account without clinic membership", async () => {
    const api = makeApi({ fetchStaffMe: vi.fn().mockResolvedValue(ok({ ...ME, memberships: [] })) });
    await signIn(api);
    expect(await screen.findByRole("alert")).toHaveTextContent(/no clinic membership/);
    expect(api.listIntakes).not.toHaveBeenCalled();
  });

  it("returns to sign-in when the session expires during use", async () => {
    const api = makeApi({ listIntakes: vi.fn().mockResolvedValue(fail("unauthorized", 401)) });
    await signIn(api);
    expect(await screen.findByRole("heading", { name: "Staff sign-in" })).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(STAFF_MESSAGES.unauthorized);
  });
});

describe("StaffReview queue", () => {
  it("filters by review status through the API", async () => {
    const api = makeApi();
    const user = await signIn(api);
    await screen.findByRole("table");

    api.listIntakes.mockResolvedValueOnce(ok([summary("done-0002", "reviewed", "low_confidence")]));
    await user.selectOptions(screen.getByLabelText("Status"), "reviewed");
    expect(api.listIntakes).toHaveBeenLastCalledWith(TOKEN, "default", "reviewed");
    expect(await screen.findByText("low_confidence")).toBeInTheDocument();

    api.listIntakes.mockResolvedValueOnce(ok([]));
    await user.selectOptions(screen.getByLabelText("Status"), "escalated");
    expect(api.listIntakes).toHaveBeenLastCalledWith(TOKEN, "default", "escalated");

    api.listIntakes.mockResolvedValueOnce(ok([]));
    await user.selectOptions(screen.getByLabelText("Status"), "All");
    expect(api.listIntakes).toHaveBeenLastCalledWith(TOKEN, "default", null);
  });

  it("shows an empty state", async () => {
    const api = makeApi({ listIntakes: vi.fn().mockResolvedValue(ok([])) });
    await signIn(api);
    expect(await screen.findByText("No intakes with this status.")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("shows loading, then an error with retry", async () => {
    const pending = deferred<StaffResult<IntakeSummary[]>>();
    const api = makeApi({ listIntakes: vi.fn().mockReturnValueOnce(pending.promise) });
    const user = await signIn(api);

    expect(await screen.findByText("Loading intakes…")).toBeInTheDocument();
    pending.resolve(fail("network"));
    expect(await screen.findByRole("alert")).toHaveTextContent(STAFF_MESSAGES.network);

    api.listIntakes.mockResolvedValueOnce(ok([summary("flagged-0001", "needs_review", "emergency_signal")]));
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByRole("table")).toBeInTheDocument();
  });

  it("shows a forbidden error without leaving the session", async () => {
    const api = makeApi({ listIntakes: vi.fn().mockResolvedValue(fail("forbidden", 403)) });
    await signIn(api);
    expect(await screen.findByRole("alert")).toHaveTextContent(STAFF_MESSAGES.forbidden);
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
  });
});

describe("StaffReview detail and transitions", () => {
  it("opens an intake and renders summary, report, safety and escalation reason", async () => {
    const api = makeApi();
    const user = await signIn(api);
    await openFirst(user);

    expect(api.getIntake).toHaveBeenCalledWith(TOKEN, "default", "flagged-0001");
    expect(screen.getByTestId("detail-status")).toHaveTextContent("Needs review");
    expect(screen.getAllByText("emergency_signal").length).toBeGreaterThan(0);
    expect(screen.getByText("Short history of chest pain.")).toBeInTheDocument();
    expect(screen.getByText("Pre-visit intake received.")).toBeInTheDocument();
    expect(screen.getByText("Seek urgent care if severe.")).toBeInTheDocument();
    expect(screen.getByText("add_emergency_guidance")).toBeInTheDocument();
    expect(screen.getByText("high")).toBeInTheDocument();
  });

  it("shows a detail fetch error", async () => {
    const api = makeApi({ getIntake: vi.fn().mockResolvedValue(fail("not_found", 404)) });
    const user = await signIn(api);
    await user.click(await screen.findByRole("button", { name: /^Open / }));
    expect(await screen.findByRole("alert")).toHaveTextContent(STAFF_MESSAGES.not_found);
  });

  it.each([
    ["reviewed", "Mark reviewed", "Reviewed"],
    ["escalated", "Mark escalated", "Escalated"],
  ] as const)("transitions needs_review -> %s and cannot transition again", async (target, button, label) => {
    const pending = deferred<StaffResult<IntakeDetail>>();
    const api = makeApi({ transitionIntake: vi.fn().mockReturnValue(pending.promise) });
    const user = await signIn(api);
    await openFirst(user);
    const listCalls = api.listIntakes.mock.calls.length;

    await user.click(screen.getByRole("button", { name: button }));
    expect(screen.getByText("Updating status…")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Mark reviewed" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Mark escalated" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: button }));
    expect(api.transitionIntake).toHaveBeenCalledTimes(1);
    expect(api.transitionIntake).toHaveBeenCalledWith(TOKEN, "default", "flagged-0001", target);

    api.listIntakes.mockResolvedValueOnce(ok([]));
    pending.resolve(ok(detail({ review_status: target })));

    expect(await screen.findByText(`Marked ${target}.`)).toBeInTheDocument();
    expect(screen.getByTestId("detail-status")).toHaveTextContent(label);
    // Queue is refetched so the resolved intake leaves the needs_review list
    await waitFor(() => expect(api.listIntakes.mock.calls.length).toBe(listCalls + 1));
    expect(await screen.findByText("No intakes with this status.")).toBeInTheDocument();
    // No further transition is offered
    expect(screen.queryByRole("button", { name: "Mark reviewed" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Mark escalated" })).not.toBeInTheDocument();
  });

  it("shows a transition error and keeps the intake transitionable", async () => {
    const api = makeApi({ transitionIntake: vi.fn().mockResolvedValue(fail("network")) });
    const user = await signIn(api);
    await openFirst(user);

    await user.click(screen.getByRole("button", { name: "Mark reviewed" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(STAFF_MESSAGES.network);
    expect(screen.getByTestId("detail-status")).toHaveTextContent("Needs review");
    expect(screen.getByRole("button", { name: "Mark reviewed" })).toBeEnabled();
  });

  it("reloads the intake after a 409 conflict and hides the transition buttons", async () => {
    const api = makeApi({ transitionIntake: vi.fn().mockResolvedValue(fail("conflict", 409)) });
    const user = await signIn(api);
    await openFirst(user);

    api.getIntake.mockResolvedValueOnce(ok(detail({ review_status: "escalated" })));
    await user.click(screen.getByRole("button", { name: "Mark reviewed" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(STAFF_MESSAGES.conflict);
    await waitFor(() => expect(screen.getByTestId("detail-status")).toHaveTextContent("Escalated"));
    expect(screen.queryByRole("button", { name: "Mark reviewed" })).not.toBeInTheDocument();
  });

  it("does not offer transitions for an intake that is not in needs_review", async () => {
    const api = makeApi({ getIntake: vi.fn().mockResolvedValue(ok(detail({ review_status: "reviewed" }))) });
    const user = await signIn(api);
    await openFirst(user);
    expect(screen.queryByRole("button", { name: "Mark reviewed" })).not.toBeInTheDocument();
    expect(screen.getByText(/Only intakes that need review/)).toBeInTheDocument();
  });
});

describe("staffApi client", () => {
  it("sends the bearer token and maps HTTP errors", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValueOnce(new Response("[]", { status: 200 }))
      .mockResolvedValueOnce(new Response('{"detail":"x"}', { status: 409 }))
      .mockRejectedValueOnce(new TypeError("Failed to fetch"));
    const options = { baseUrl: "http://api.test/", fetchImpl };

    expect(await listIntakes(TOKEN, "default", "needs_review", options)).toEqual({ ok: true, data: [] });
    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe("http://api.test/api/clinics/default/intakes?review_status=needs_review");
    expect(init.headers).toEqual({ Authorization: `Bearer ${TOKEN}` });
    expect(init.credentials).toBeUndefined();

    const conflict = await transitionIntake(TOKEN, "default", "i-1", "reviewed", options);
    expect(conflict).toMatchObject({ ok: false, kind: "conflict", status: 409 });
    const [turl, tinit] = fetchImpl.mock.calls[1];
    expect(turl).toBe("http://api.test/api/clinics/default/intakes/i-1/transition");
    expect(tinit.method).toBe("POST");
    expect(JSON.parse(tinit.body)).toEqual({ review_status: "reviewed" });

    expect(await listIntakes(TOKEN, "default", null, options)).toMatchObject({ ok: false, kind: "network" });
  });
});

// Client code must hold no server secrets or privileged credentials
describe("client bundle hygiene", () => {
  function sources(dir: string): string[] {
    return readdirSync(dir).flatMap((name) => {
      const path = join(dir, name);
      if (statSync(path).isDirectory()) return sources(path);
      return /\.(ts|tsx|mjs|js)$/.test(name) ? [path] : [];
    });
  }

  it("contains no auth secrets, persisted tokens or extra NEXT_PUBLIC variables", () => {
    const root = join(__dirname, "..");
    const files = ["components", "pages", "services"].flatMap((d) => sources(join(root, d)));
    files.push(join(root, "next.config.mjs"));
    const code = files.map((f) => readFileSync(f, "utf8")).join("\n");

    expect(code).not.toMatch(/AUTH_TOKEN_SECRET|OPENAI_API_KEY|DATABASE_URL/);
    expect(code).not.toMatch(/localStorage|sessionStorage|document\.cookie/);
    // NEXT_PUBLIC_DEMO_MODE (#43) is a display-only boolean, never a credential
    expect(new Set(code.match(/NEXT_PUBLIC_[A-Z_]+/g))).toEqual(
      new Set(["NEXT_PUBLIC_API_BASE_URL", "NEXT_PUBLIC_DEMO_MODE"]),
    );
    expect(code).not.toMatch(/v1\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}/); // no embedded bearer tokens
  });
});

describe("StaffReview evidence & timeline (#41)", () => {
  it("shows the triggered rule, highlights only recorded matches found in the input, and labels extracted fields", async () => {
    const api = makeApi();
    const user = await signIn(api);
    await openFirst(user);

    const rules = await screen.findByTestId("escalation-rules");
    expect(rules).toHaveTextContent("Emergency or crisis language");
    expect(rules).toHaveTextContent("emergency_signal");
    expect(api.getIntakeTimeline).toHaveBeenCalledWith(TOKEN, "default", "flagged-0001");

    const marks = within(screen.getByTestId("original-input")).getAllByTestId("recorded-match");
    expect(marks.map((m) => m.textContent)).toEqual(["Chest pain"]);
    expect(screen.getByText(/not the input\): report only/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Extracted fields \(derived, not recorded matches\)/ })).toBeInTheDocument();
    expect(within(screen.getByTestId("provenance")).getByText("deterministic_rule_based_baseline_v1")).toBeInTheDocument();
  });

  it("renders the timeline in the order returned, including webhook delivery and staff actions", async () => {
    const user = await signIn(makeApi());
    await openFirst(user);

    const items = within(await screen.findByTestId("timeline")).getAllByRole("listitem");
    expect(items.map((li) => li.getAttribute("data-kind"))).toEqual([
      "submitted", "processed", "safety_evaluated", "escalation_decision", "webhook_delivery", "staff_transition",
    ]);
    expect(items[4]).toHaveTextContent("failed after 3 attempt(s)");
    expect(items[4]).toHaveTextContent("timeout");
    expect(items[5]).toHaveTextContent("admin-a: needs_review → escalated");
  });

  it("shows loading, then an error state when the timeline cannot be loaded", async () => {
    const pending = deferred<StaffResult<IntakeTimeline>>();
    const api = makeApi({ getIntakeTimeline: vi.fn().mockReturnValueOnce(pending.promise) });
    const user = await signIn(api);
    await openFirst(user);

    expect(await screen.findByText("Loading evidence and timeline…")).toBeInTheDocument();
    pending.resolve(fail("not_found", 404));
    expect(await screen.findByTestId("timeline-error")).toHaveTextContent(STAFF_MESSAGES.not_found);
  });

  it("handles missing data without inventing values", async () => {
    const data = timeline({
      evidence: {
        original_input: null,
        extracted: {},
        recorded_matches: [],
        escalation_rules: [],
        provenance: { execution_mode: null, model_version: null, prompt_version: null, pipeline_version: "v0.0.1", run_id: "r" },
      },
      events: [],
      notes: ["Model and prompt version were not recorded for this intake."],
    });
    const user = await signIn(makeApi({ getIntakeTimeline: vi.fn().mockResolvedValue(ok(data)) }));
    await openFirst(user);

    expect(await screen.findByTestId("no-escalation")).toBeInTheDocument();
    expect(screen.getByText("Original input is not available for this intake.")).toBeInTheDocument();
    expect(screen.getByText("No events have been recorded for this intake.")).toBeInTheDocument();
    expect(within(screen.getByTestId("provenance")).getAllByText("Not recorded")).toHaveLength(3);
    expect(screen.getByTestId("timeline-note")).toHaveTextContent("not recorded");
  });

  it("does not render another clinic's evidence when the server denies access", async () => {
    const api = makeApi({ getIntakeTimeline: vi.fn().mockResolvedValue(fail("forbidden", 403)) });
    const user = await signIn(api);
    await openFirst(user);

    expect(await screen.findByTestId("timeline-error")).toHaveTextContent(STAFF_MESSAGES.forbidden);
    expect(screen.queryByTestId("original-input")).not.toBeInTheDocument();
    expect(screen.queryByTestId("timeline")).not.toBeInTheDocument();
  });
});

describe("StaffReview FHIR export (#42)", () => {
  it("is labelled synthetic, loads on demand, previews and downloads the Bundle", async () => {
    const api = makeApi();
    const user = await signIn(api);
    await openFirst(user);

    expect(await screen.findByTestId("fhir-label")).toHaveTextContent("FHIR R4 — Synthetic Demo Data");
    expect(screen.getByText("No export loaded yet.")).toBeInTheDocument();
    expect(api.exportIntakeFhir).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Load FHIR export" }));
    expect(api.exportIntakeFhir).toHaveBeenCalledWith(TOKEN, "default", "flagged-0001");
    expect(await screen.findByTestId("fhir-preview")).toHaveTextContent('"resourceType": "Bundle"');

    const createObjectURL = vi.fn(() => "blob:fhir");
    const revokeObjectURL = vi.fn();
    Object.assign(URL, { createObjectURL, revokeObjectURL });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    await user.click(screen.getByRole("button", { name: "Download JSON" }));
    expect(createObjectURL).toHaveBeenCalledOnce();
    expect(click).toHaveBeenCalledOnce();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:fhir");
    click.mockRestore();
  });

  it("shows loading and then an error state without a preview", async () => {
    const pending = deferred<StaffResult<Record<string, unknown>>>();
    const api = makeApi({ exportIntakeFhir: vi.fn().mockReturnValueOnce(pending.promise) });
    const user = await signIn(api);
    await openFirst(user);

    await user.click(await screen.findByRole("button", { name: "Load FHIR export" }));
    expect(screen.getByText("Building FHIR export…")).toBeInTheDocument();
    pending.resolve(fail("forbidden", 403));
    expect(await screen.findByTestId("fhir-error")).toHaveTextContent(STAFF_MESSAGES.forbidden);
    expect(screen.queryByTestId("fhir-preview")).not.toBeInTheDocument();
  });

  it("shows an empty state for a Bundle without entries", async () => {
    const api = makeApi({ exportIntakeFhir: vi.fn().mockResolvedValue(ok({ resourceType: "Bundle", type: "collection" })) });
    const user = await signIn(api);
    await openFirst(user);

    await user.click(await screen.findByRole("button", { name: "Load FHIR export" }));
    expect(await screen.findByText("The export contains no resources.")).toBeInTheDocument();
  });
});
