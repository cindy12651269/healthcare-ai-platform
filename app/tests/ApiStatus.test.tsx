import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ApiStatus from "../components/ApiStatus";
import { WaitForApiOptions, waitForApi } from "../services/api";

// Cold-start handling (#67): GET /health polled with bounded retry, mocked here.

const BASE = "https://api.example.test";
const noSleep = vi.fn(async () => {});

function healthOk() {
  return new Response(JSON.stringify({ status: "ok", llm_mode: "mock" }), { status: 200 });
}
// What a sleeping free instance returns while it starts: a gateway error page, not JSON
function gatewayError() {
  return new Response("<html>502 Bad Gateway</html>", { status: 502 });
}

function deferred<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => (resolve = r));
  return { promise, resolve };
}

// The component's wait function: the real waitForApi against a mocked fetch, without real delays
function waitWith(fetchImpl: typeof fetch, extra: Partial<WaitForApiOptions> = {}) {
  return (opts: Pick<WaitForApiOptions, "signal" | "onAttempt">) =>
    waitForApi({ baseUrl: BASE, fetchImpl, sleep: noSleep, ...extra, ...opts });
}

describe("waitForApi", () => {
  it("retries /health until it answers ok (slow, then OK)", async () => {
    const fetchImpl = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce(gatewayError())
      .mockResolvedValueOnce(healthOk());
    const onAttempt = vi.fn();

    const result = await waitForApi({ baseUrl: BASE, fetchImpl, sleep: noSleep, onAttempt, maxAttempts: 5 });

    expect(result).toBe("ready");
    expect(fetchImpl).toHaveBeenCalledTimes(3);
    expect(fetchImpl.mock.calls.every(([url]) => url === `${BASE}/health`)).toBe(true);
    expect(onAttempt.mock.calls).toEqual([[1, 5], [2, 5], [3, 5]]);
  });

  it("gives up after the bounded number of attempts (slow, then fail)", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(gatewayError());
    const sleep = vi.fn(async () => {});

    const result = await waitForApi({ baseUrl: BASE, fetchImpl, sleep, maxAttempts: 4, retryDelayMs: 3000 });

    expect(result).toBe("unavailable");
    expect(fetchImpl).toHaveBeenCalledTimes(4);
    expect(sleep).toHaveBeenCalledTimes(3);
    expect(sleep).toHaveBeenCalledWith(3000, undefined);
  });

  it("times out an attempt that hangs and counts it as failed", async () => {
    const hanging = vi.fn(
      (_url: string, init?: RequestInit) =>
        new Promise<Response>((_, reject) =>
          init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError"))),
        ),
    );
    const result = await waitForApi({
      baseUrl: BASE,
      fetchImpl: hanging as unknown as typeof fetch,
      sleep: noSleep,
      maxAttempts: 2,
      attemptTimeoutMs: 5,
    });
    expect(result).toBe("unavailable");
    expect(hanging).toHaveBeenCalledTimes(2);
  });

  it("does not treat a 200 without status ok as ready", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "starting" }), { status: 200 }));
    expect(await waitForApi({ baseUrl: BASE, fetchImpl, sleep: noSleep, maxAttempts: 2 })).toBe("unavailable");
  });

  it("stops when cancelled", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(gatewayError());
    const controller = new AbortController();
    controller.abort();
    expect(await waitForApi({ baseUrl: BASE, fetchImpl, signal: controller.signal })).toBe("unavailable");
    expect(fetchImpl).not.toHaveBeenCalled();
  });
});

describe("ApiStatus", () => {
  it("renders nothing when the API answers quickly", async () => {
    const wait = vi.fn().mockResolvedValue("ready");
    render(<ApiStatus wait={wait} />);
    await waitFor(() => expect(wait).toHaveBeenCalledTimes(1));
    expect(screen.queryByTestId("api-status")).not.toBeInTheDocument();
  });

  it("shows a waking state while /health is slow, then confirms the server is awake", async () => {
    const second = deferred<Response>();
    const fetchImpl = vi.fn().mockResolvedValueOnce(gatewayError()).mockReturnValueOnce(second.promise);
    render(<ApiStatus wait={waitWith(fetchImpl, { maxAttempts: 6 })} />);

    const waking = await screen.findByTestId("api-status");
    expect(waking).toHaveTextContent("Waking the demo server (can take up to a minute)");
    expect(waking).toHaveTextContent("attempt 2 of 6");

    second.resolve(healthOk());
    await waitFor(() => expect(screen.getByTestId("api-status")).toHaveTextContent("Demo server is awake"));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows the waking state when the first check is still pending after the slow threshold", async () => {
    const first = deferred<Response>();
    const fetchImpl = vi.fn().mockReturnValueOnce(first.promise);
    render(<ApiStatus wait={waitWith(fetchImpl)} slowAfterMs={5} />);

    expect(await screen.findByTestId("api-status")).toHaveTextContent("Waking the demo server");
    first.resolve(healthOk());
    await waitFor(() => expect(screen.getByTestId("api-status")).toHaveTextContent("Demo server is awake"));
  });

  it("shows an actionable failure after bounded retries (slow, then fail), and can try again", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(gatewayError());
    render(<ApiStatus wait={waitWith(fetchImpl, { maxAttempts: 3 })} />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("The demo server did not respond");
    expect(alert).toHaveTextContent("Try again in a minute");
    expect(alert).toHaveTextContent("contact the person who shared this demo");
    expect(fetchImpl).toHaveBeenCalledTimes(3);

    fetchImpl.mockResolvedValue(healthOk());
    await userEvent.setup().click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(screen.getByTestId("api-status")).toHaveTextContent("Demo server is awake"));
    expect(fetchImpl).toHaveBeenCalledTimes(4);
  });

  it("stops polling when the page is left", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(gatewayError());
    const sleep = vi.fn((_ms: number, signal?: AbortSignal) => new Promise<void>((r) => signal?.addEventListener("abort", () => r())));
    const { unmount } = render(<ApiStatus wait={waitWith(fetchImpl, { sleep })} />);
    await waitFor(() => expect(sleep).toHaveBeenCalledTimes(1));
    unmount();
    await new Promise((r) => setTimeout(r, 0));
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });
});
