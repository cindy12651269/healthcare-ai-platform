import { Wait, useApiReadiness } from "./ApiStatus";
import { Button, Card, Spinner, Tag } from "./ui";
import { waitForApi } from "../services/api";

// Live system status for the dashboard (#69). It is the page's only /health poller: it uses the #67
// readiness states (checking → waking → ready / unavailable) and shows environment and llm_mode exactly
// as /health reports them. Nothing is shown as healthy unless /health answered "ok".
export default function SystemStatus({ wait = waitForApi, slowAfterMs = 1500 }: { wait?: Wait; slowAfterMs?: number }) {
  const { state, retry } = useApiReadiness(wait, slowAfterMs);
  const health = state.status === "ready" ? state.health : null;
  const reported = (v: string | null | undefined) => v ?? "Not reported";

  return (
    <Card as="aside" className="system-status" aria-labelledby="system-status-heading" data-testid="system-status">
      <h2 id="system-status-heading">Live system status</h2>
      <div role="status" aria-live="polite" data-state={state.status}>
        {state.status === "checking" && (
          <p className="status-line">
            <Spinner /> Checking the demo API…
          </p>
        )}
        {state.status === "waking" && (
          <>
            <p className="status-line">
              <Tag tone="warning">Waking</Tag> Waking the demo server (can take up to a minute).
            </p>
            <p className="muted small">
              The free hosted demo sleeps when idle. Checking again… (attempt {state.attempt} of {state.maxAttempts})
            </p>
          </>
        )}
        {state.status === "ready" && (
          <p className="status-line">
            <Tag tone="success">Reachable</Tag> The demo API answered <code>GET /health</code>.
          </p>
        )}
        {state.status === "unavailable" && (
          <p className="status-line">
            <Tag tone="emergency">Unavailable</Tag> The demo API did not respond to <code>GET /health</code>.
          </p>
        )}
      </div>

      <dl className="kv status-facts">
        <dt>API</dt>
        <dd data-testid="status-api">
          {state.status === "ready" ? "Reachable" : state.status === "unavailable" ? "Unreachable" : "Checking…"}
        </dd>
        <dt>Environment</dt>
        <dd data-testid="status-environment">{state.status === "ready" ? reported(health?.environment) : "Unknown"}</dd>
        <dt>LLM mode</dt>
        <dd data-testid="status-llm-mode">
          {state.status === "ready" ? <code>{reported(health?.llmMode)}</code> : "Unknown"}
        </dd>
      </dl>

      {health?.llmMode === "mock" && (
        <p className="muted small" data-testid="status-mode-note">
          Mock mode: deterministic rule-based processing, no model calls.
        </p>
      )}
      {health?.llmMode === "real" && (
        <p className="muted small" data-testid="status-mode-note">
          Real mode: this API calls the opt-in OpenAI integration. The public hosted demo and CI run in mock mode.
        </p>
      )}
      {state.status === "unavailable" && (
        <>
          <p className="muted small">
            It may still be starting, being redeployed or offline. Environment and mode are unknown until it answers.
          </p>
          <Button onClick={retry}>Try again</Button>
        </>
      )}
    </Card>
  );
}
