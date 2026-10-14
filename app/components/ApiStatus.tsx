import { useCallback, useEffect, useState } from "react";
import { Alert, Button } from "./ui";
import { ApiReadiness, HealthInfo, WAKE_POLICY, WaitForApiOptions, waitForApi } from "../services/api";

// Cold-start notice (#67). The hosted demo runs on free instances that sleep when idle, so the first
// request can take up to about a minute. This polls GET /health (bounded) and explains the wait
// instead of leaving the visitor with a silent page or a generic error. It renders nothing once the
// server answers quickly.

export type Wait = (options: Pick<WaitForApiOptions, "signal" | "onAttempt" | "onHealth">) => Promise<ApiReadiness>;

export type ApiState =
  | { status: "checking" }
  | { status: "waking"; attempt: number; maxAttempts: number }
  | { status: "ready"; afterWake: boolean; health: HealthInfo | null }
  | { status: "unavailable" };

interface ApiStatusProps {
  wait?: Wait; // injectable for tests
  slowAfterMs?: number; // show the waking notice if the first check has not answered by then
}

// The #67 readiness state machine, shared by this notice and the dashboard's system status (#69) so a
// page polls /health once. "ready" carries the healthy /health body when the wait reported it.
export function useApiReadiness(wait: Wait = waitForApi, slowAfterMs = 1500) {
  const [state, setState] = useState<ApiState>({ status: "checking" });
  const [run, setRun] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    // After a visible failure, a successful retry is confirmed rather than silently cleared
    let woke = run > 0;
    let health: HealthInfo | null = null;
    const showWaking = (attempt: number, maxAttempts: number) => {
      woke = true;
      setState({ status: "waking", attempt, maxAttempts });
    };
    let attemptInfo: { attempt: number; maxAttempts: number } = { attempt: 1, maxAttempts: WAKE_POLICY.maxAttempts };
    const slowTimer = setTimeout(() => showWaking(attemptInfo.attempt, attemptInfo.maxAttempts), slowAfterMs);

    wait({
      signal: controller.signal,
      onAttempt: (attempt, maxAttempts) => {
        attemptInfo = { attempt, maxAttempts };
        if (attempt > 1) showWaking(attempt, maxAttempts);
      },
      onHealth: (h) => {
        health = h;
      },
    }).then((result) => {
      clearTimeout(slowTimer);
      if (controller.signal.aborted) return;
      setState(result === "ready" ? { status: "ready", afterWake: woke, health } : { status: "unavailable" });
    });
    return () => {
      clearTimeout(slowTimer);
      controller.abort();
    };
  }, [wait, slowAfterMs, run]);

  const retry = useCallback(() => {
    setState({ status: "checking" });
    setRun((n) => n + 1);
  }, []);

  return { state, retry };
}

export default function ApiStatus({ wait = waitForApi, slowAfterMs = 1500 }: ApiStatusProps) {
  const { state, retry } = useApiReadiness(wait, slowAfterMs);

  if (state.status === "checking" || (state.status === "ready" && !state.afterWake)) return null;

  if (state.status === "waking") {
    return (
      <Alert variant="warning" data-testid="api-status" title="Waking the demo server (can take up to a minute).">
        <p>
          This free hosted demo sleeps when nobody is using it. Checking again… (attempt {state.attempt} of{" "}
          {state.maxAttempts})
        </p>
      </Alert>
    );
  }

  if (state.status === "ready") {
    return (
      <p className="muted small" role="status" data-testid="api-status">
        Demo server is awake.
      </p>
    );
  }

  return (
    <Alert variant="error" data-testid="api-status" title="The demo server did not respond.">
      <p>
        We kept checking for over a minute without an answer. It may still be starting, being redeployed,
        or offline for maintenance. Try again in a minute; if it keeps failing, contact the person who shared this demo.
      </p>
      <Button onClick={retry}>Try again</Button>
    </Alert>
  );
}
