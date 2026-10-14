import { useCallback, useEffect, useState } from "react";
import { ApiReadiness, WAKE_POLICY, WaitForApiOptions, waitForApi } from "../services/api";

// Cold-start notice (#67). The hosted demo runs on free instances that sleep when idle, so the first
// request can take up to about a minute. This polls GET /health (bounded) and explains the wait
// instead of leaving the visitor with a silent page or a generic error. It renders nothing once the
// server answers quickly.

type Wait = (options: Pick<WaitForApiOptions, "signal" | "onAttempt">) => Promise<ApiReadiness>;

type State =
  | { status: "checking" }
  | { status: "waking"; attempt: number; maxAttempts: number }
  | { status: "ready"; afterWake: boolean }
  | { status: "unavailable" };

interface ApiStatusProps {
  wait?: Wait; // injectable for tests
  slowAfterMs?: number; // show the waking notice if the first check has not answered by then
}

export default function ApiStatus({ wait = waitForApi, slowAfterMs = 1500 }: ApiStatusProps) {
  const [state, setState] = useState<State>({ status: "checking" });
  const [run, setRun] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    // After a visible failure, a successful retry is confirmed rather than silently cleared
    let woke = run > 0;
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
    }).then((result) => {
      clearTimeout(slowTimer);
      if (controller.signal.aborted) return;
      setState(result === "ready" ? { status: "ready", afterWake: woke } : { status: "unavailable" });
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

  if (state.status === "checking" || (state.status === "ready" && !state.afterWake)) return null;

  if (state.status === "waking") {
    return (
      <div className="alert alert-warn" role="status" data-testid="api-status">
        <strong>Waking the demo server (can take up to a minute).</strong>
        <p>
          This free hosted demo sleeps when nobody is using it. Checking again… (attempt {state.attempt} of{" "}
          {state.maxAttempts})
        </p>
      </div>
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
    <div className="alert alert-error" role="alert" data-testid="api-status">
      <strong>The demo server did not respond.</strong>
      <p>
        We kept checking for over a minute without an answer. It may still be starting, being redeployed,
        or offline for maintenance. Try again in a minute; if it keeps failing, contact the person who shared this demo.
      </p>
      <button type="button" className="secondary" onClick={retry}>
        Try again
      </button>
    </div>
  );
}
