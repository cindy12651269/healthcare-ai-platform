import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Dashboard from "../pages/index";
import SystemCardPage from "../pages/system-card";
import SystemStatus from "../components/SystemStatus";
import { WaitForApiOptions, waitForApi } from "../services/api";
import { CAPABILITIES, REPO_URL, WEBHOOK_BRANCH, WORKFLOW } from "../services/evidence";

// Product dashboard (#69): live /health status on the #67 cold-start states, workflow, real-vs-mock
// panel, capability evidence and demo-mode gating.

const BASE = "https://api.example.test";
const REPO_ROOT = join(__dirname, "..", "..");
const noSleep = vi.fn(async () => {});
const health = (body: Record<string, unknown>, status = 200) => new Response(JSON.stringify(body), { status });
const apiReady = async () => "ready" as const;

// The component's wait function: the real waitForApi against a mocked fetch, without real delays
function waitWith(fetchImpl: typeof fetch, extra: Partial<WaitForApiOptions> = {}) {
  return (opts: Pick<WaitForApiOptions, "signal" | "onAttempt" | "onHealth">) =>
    waitForApi({ baseUrl: BASE, fetchImpl, sleep: noSleep, ...extra, ...opts });
}

describe("waitForApi health info", () => {
  it("reports environment and llm_mode from a healthy /health, and nothing otherwise", async () => {
    const onHealth = vi.fn();
    const ok = vi.fn().mockResolvedValue(health({ status: "ok", environment: "demo", llm_mode: "mock" }));
    expect(await waitForApi({ baseUrl: BASE, fetchImpl: ok, sleep: noSleep, onHealth })).toBe("ready");
    expect(onHealth).toHaveBeenCalledWith({ environment: "demo", llmMode: "mock" });

    onHealth.mockClear();
    const notOk = vi.fn().mockResolvedValue(health({ status: "degraded", llm_mode: "mock" }));
    expect(await waitForApi({ baseUrl: BASE, fetchImpl: notOk, sleep: noSleep, onHealth, maxAttempts: 2 })).toBe(
      "unavailable",
    );
    expect(onHealth).not.toHaveBeenCalled();
  });
});

describe("SystemStatus (live /health)", () => {
  it("healthy mock: reachable, environment and the reported mode", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(health({ status: "ok", environment: "demo", llm_mode: "mock" }));
    render(<SystemStatus wait={waitWith(fetchImpl)} />);
    expect(await screen.findByTestId("status-api")).toHaveTextContent("Reachable");
    await waitFor(() => expect(screen.getByTestId("status-environment")).toHaveTextContent("demo"));
    expect(screen.getByTestId("status-llm-mode")).toHaveTextContent("mock");
    expect(screen.getByTestId("status-mode-note")).toHaveTextContent("Mock mode");
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it("healthy real: shows real as reported and says the public demo and CI run mock", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(health({ status: "ok", environment: "local", llm_mode: "real" }));
    render(<SystemStatus wait={waitWith(fetchImpl)} />);
    await waitFor(() => expect(screen.getByTestId("status-llm-mode")).toHaveTextContent("real"));
    expect(screen.getByTestId("status-environment")).toHaveTextContent("local");
    expect(screen.getByTestId("status-mode-note")).toHaveTextContent(/opt-in OpenAI/);
    expect(screen.getByTestId("status-mode-note")).toHaveTextContent(/hosted demo and CI run in mock mode/);
  });

  it("does not invent fields /health did not report", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(health({ status: "ok" }));
    render(<SystemStatus wait={waitWith(fetchImpl)} />);
    await waitFor(() => expect(screen.getByTestId("status-api")).toHaveTextContent("Reachable"));
    expect(screen.getByTestId("status-environment")).toHaveTextContent("Not reported");
    expect(screen.getByTestId("status-llm-mode")).toHaveTextContent("Not reported");
    expect(screen.queryByTestId("status-mode-note")).not.toBeInTheDocument();
  });

  it("unreachable: never claims healthy, offers a retry that recovers", async () => {
    const fetchImpl = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    render(<SystemStatus wait={waitWith(fetchImpl, { maxAttempts: 2 })} />);
    await waitFor(() => expect(screen.getByTestId("status-api")).toHaveTextContent("Unreachable"));
    expect(screen.getByRole("status")).toHaveTextContent("did not respond");
    expect(screen.getByTestId("status-environment")).toHaveTextContent("Unknown");
    expect(screen.getByTestId("status-llm-mode")).toHaveTextContent("Unknown");
    expect(screen.queryByText("Reachable")).not.toBeInTheDocument();

    fetchImpl.mockResolvedValue(health({ status: "ok", environment: "demo", llm_mode: "mock" }));
    await userEvent.setup().click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(screen.getByTestId("status-api")).toHaveTextContent("Reachable"));
    expect(screen.getByTestId("status-llm-mode")).toHaveTextContent("mock");
  });

  it("cold start: shows the waking state with the attempt count, then ready", async () => {
    let answer!: (r: Response) => void;
    const second = new Promise<Response>((r) => (answer = r));
    const fetchImpl = vi
      .fn()
      .mockResolvedValueOnce(new Response("<html>502</html>", { status: 502 })) // sleeping instance
      .mockReturnValueOnce(second);
    render(<SystemStatus wait={waitWith(fetchImpl, { maxAttempts: 3 })} />);

    expect(await screen.findByText(/attempt 2 of 3/)).toBeInTheDocument();
    expect(screen.getByText(/Waking the demo server/)).toBeInTheDocument();
    expect(screen.getByTestId("status-api")).toHaveTextContent("Checking");
    answer(health({ status: "ok", environment: "demo", llm_mode: "mock" }));
    await waitFor(() => expect(screen.getByTestId("status-api")).toHaveTextContent("Reachable"));
    expect(screen.getByTestId("status-environment")).toHaveTextContent("demo");
  });

  it("shows the waking notice when the first check is slow", async () => {
    render(<SystemStatus wait={() => new Promise(() => {})} slowAfterMs={0} />);
    expect(await screen.findByText(/Waking the demo server/)).toBeInTheDocument();
    expect(screen.getByText(/attempt 1 of 6/)).toBeInTheDocument();
    expect(screen.getByTestId("status-api")).toHaveTextContent("Checking");
  });
});

describe("Dashboard", () => {
  it("polls /health once (status card only) and offers the two calls to action", async () => {
    const checkApi = vi.fn(apiReady);
    render(<Dashboard checkApi={checkApi} demoMode={false} />);
    await waitFor(() => expect(screen.getByTestId("status-api")).toHaveTextContent("Reachable"));
    expect(checkApi).toHaveBeenCalledTimes(1);
    expect(screen.queryByTestId("api-status")).not.toBeInTheDocument(); // no second #67 banner poller

    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("link", { name: "Try Patient Intake" })).toHaveAttribute("href", "/intake");
    expect(screen.getByRole("link", { name: "Explore Staff Workflow" })).toHaveAttribute("href", "/staff");
    expect(screen.getByTestId("staff-cta-note")).toHaveTextContent("issued on request by the demo operator");
  });

  it("shows the seven workflow stages in order, with the webhook as a conditional branch of escalation", () => {
    render(<Dashboard checkApi={apiReady} demoMode={false} />);
    const flow = screen.getByTestId("workflow");
    const steps = within(flow).getAllByRole("listitem");
    expect(steps.map((li) => li.getAttribute("data-stage"))).toEqual([
      "intake", "structuring", "report", "escalation", "queue", "timeline", "fhir",
    ]);
    expect(steps.map((li) => within(li).getByRole("heading").textContent)).toEqual([
      "Patient intake", "Structuring", "Report + safety guard", "Escalation rules", "Clinic review queue",
      "Evidence timeline", "FHIR R4 export",
    ]);
    // The webhook is not a step; it hangs off the escalation step and is labelled conditional
    expect(steps.map((li) => li.getAttribute("data-stage"))).not.toContain("webhook");
    const branch = screen.getByTestId("webhook-branch");
    expect(branch.closest("li")).toHaveAttribute("data-stage", WEBHOOK_BRANCH.after);
    expect(branch).toHaveTextContent("Conditional branch");
    expect(branch).toHaveTextContent("only when a receiver is configured");
    expect(branch).toHaveTextContent("Disabled on the hosted demo");
    // Every stage carries a maturity label; structuring is mock on this demo
    for (const li of steps) expect(li.querySelector(".tag")).not.toBeNull();
    expect(steps[1]).toHaveTextContent("Mock mode");
    expect(steps[1]).toHaveTextContent("not an LLM");
  });

  it("explains what is real and what is mock, and claims nothing it should not", () => {
    render(<Dashboard checkApi={apiReady} demoMode={false} />);
    const panel = screen.getByTestId("real-vs-mock");
    for (const text of [
      "Hosted demo runs in mock mode",
      "Structuring is rule-based, not an LLM",
      "not exercised in CI or on the hosted demo",
      "RAG is not connected to the API",
      "Embeddings are mock vectors",
      "Safety rules and staff review are implemented",
    ]) {
      expect(panel).toHaveTextContent(text);
    }
    const notClaimed = screen.getByTestId("not-claimed");
    expect(notClaimed).toHaveTextContent("Not clinically validated");
    expect(notClaimed).toHaveTextContent("no HIPAA or other compliance claim");
    expect(notClaimed).toHaveTextContent("not production-ready");

    // No metrics or positive compliance/accuracy claims on the dashboard itself (numbers live on the system card)
    const page = document.body.textContent!;
    expect(page).not.toMatch(/\d+(\.\d+)?\s?%|\b\d\.\d\d\b/);
    expect(page).not.toMatch(/HIPAA[- ]compliant|clinically (proven|validated and)|production[- ]ready (platform|system)|FDA/i);
  });

  it("never presents the webhook as unconditional", () => {
    render(<Dashboard checkApi={apiReady} demoMode={false} />);
    const card = screen.getByRole("heading", { name: "Signed webhook", level: 3 }).closest("li")!;
    expect(card).toHaveTextContent("When a receiver is configured");
    expect(card).toHaveTextContent("Disabled on the hosted demo");
    expect(card).toHaveTextContent("not a delivery guarantee");
    expect(document.body.textContent).not.toMatch(/webhook delivery and/i);
  });

  it("renders every capability card with evidence links", () => {
    render(<Dashboard checkApi={apiReady} demoMode={false} />);
    const cards = within(screen.getByTestId("capabilities")).getAllByRole("listitem").filter((li) => li.dataset.capability);
    expect(cards.map((c) => within(c).getByRole("heading").textContent)).toEqual([
      "Clinic-scoped RBAC", "Rule-based safety guard", "Escalation and human review", "Evidence timeline",
      "FHIR R4 export", "Signed webhook", "CI-gated evaluation",
    ]);
    for (const card of cards) {
      const links = within(card).getAllByRole("link");
      expect(links.length).toBeGreaterThan(0);
      for (const a of links) {
        const target = a.getAttribute("data-evidence")!;
        expect(a.getAttribute("href")).toBe(target.startsWith("/") ? target : `${REPO_URL}/blob/main/${target}`);
      }
    }
  });
});

// GitHub's heading anchor: lower-case, drop punctuation except hyphens, spaces to hyphens
const slug = (heading: string) =>
  heading.trim().toLowerCase().replace(/[^\w\- ]/g, "").replace(/ /g, "-");

describe("capability evidence exists", () => {
  const links = CAPABILITIES.flatMap((c) => c.evidence.map((e) => e.href));

  it.each(links.filter((h) => !h.startsWith("/")))("repository evidence %s exists", (href) => {
    const [path, anchor] = href.split("#");
    expect(existsSync(join(REPO_ROOT, path))).toBe(true);
    if (anchor) {
      const headings = readFileSync(join(REPO_ROOT, path), "utf8")
        .split("\n")
        .filter((l) => /^#{1,6} /.test(l))
        .map((l) => slug(l.replace(/^#+ /, "")));
      expect(headings).toContain(anchor);
    }
  });

  it("system-card evidence anchors exist on the system card", async () => {
    const card = {
      execution_mode: "mock",
      pipeline_stages: [],
      safety_rules: [],
      escalation_rules: [],
      low_confidence_threshold: 0.5,
      evaluation: {},
      known_limitations: [],
    };
    render(<SystemCardPage checkApi={apiReady} load={vi.fn().mockResolvedValue(card)} />);
    await screen.findByTestId("execution-mode");
    for (const href of links.filter((h) => h.startsWith("/system-card#"))) {
      expect(document.getElementById(href.split("#")[1])).not.toBeNull();
    }
  });

  it("workflow and capability copy covers each stage once", () => {
    expect(new Set(WORKFLOW.map((s) => s.id)).size).toBe(WORKFLOW.length);
    expect(new Set(CAPABILITIES.map((c) => c.id)).size).toBe(CAPABILITIES.length);
  });
});

describe("Demo access policy", () => {
  it("keeps the #67 wording and shows staff identities only behind the demo flag, never a token", () => {
    const { unmount } = render(<Dashboard checkApi={apiReady} demoMode={false} />);
    const policy = screen.getByTestId("access-policy");
    expect(policy).toHaveTextContent("Tokens are issued on request by the demo operator and are never published");
    expect(policy).toHaveTextContent("there is no public sign-up, guest login or shared password");
    expect(screen.queryByTestId("demo-staff")).not.toBeInTheDocument();
    unmount();

    render(<Dashboard checkApi={apiReady} demoMode />);
    const panel = screen.getByTestId("demo-staff");
    expect(panel).toHaveTextContent("demo-staff-a");
    expect(panel).toHaveTextContent("demo-clinic-b");
    expect(document.body.textContent).not.toMatch(/v1\.[A-Za-z0-9_-]{20,}/);
  });
});
