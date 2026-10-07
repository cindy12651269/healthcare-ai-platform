// Thin client for the staff endpoints: GET /api/staff/me (#28) and the clinic-scoped
// records & review-queue API (#30). The only credential is the staff member's own
// operator-issued bearer token, which the caller passes in and keeps in memory.
// The backend is the authorization boundary; this client never decides access itself.
import { API_BASE_URL } from "./api";

type JsonObject = Record<string, unknown>;

export type ReviewStatus = "submitted" | "needs_review" | "reviewed" | "escalated";
export type TransitionTarget = "reviewed" | "escalated";

export interface Membership {
  clinic_id: string;
  role: string;
}

export interface StaffMe {
  user_id: string;
  email: string;
  memberships: Membership[];
}

export interface IntakeSummary {
  id: string;
  trace_id: string;
  review_status: ReviewStatus;
  escalation_reason: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface IntakeDetail extends IntakeSummary {
  clinic_id: string;
  structured: JsonObject;
  report: JsonObject;
  safety: JsonObject;
}

export type StaffErrorKind =
  | "unauthorized" // 401: missing, invalid or expired token
  | "forbidden" // 403: not staff of this clinic
  | "not_found" // 404
  | "conflict" // 409: e.g. intake no longer needs review
  | "invalid" // 422
  | "unavailable" // 503: staff auth not configured on the server
  | "failure" // other HTTP errors
  | "network"; // no readable response

export type StaffResult<T> =
  | { ok: true; data: T }
  | { ok: false; kind: StaffErrorKind; status?: number; message: string };

export const STAFF_MESSAGES: Record<StaffErrorKind, string> = {
  unauthorized: "Your sign-in token is invalid or has expired. Please sign in again.",
  forbidden: "You do not have staff access to this clinic.",
  not_found: "This intake could not be found.",
  conflict: "This intake is no longer waiting for review. It has been reloaded.",
  invalid: "The request was not accepted.",
  unavailable: "Staff sign-in is not available on this server.",
  failure: "Something went wrong. Please try again.",
  network: "We couldn't reach the staff service. Please try again.",
};

function kindFor(status: number): StaffErrorKind {
  switch (status) {
    case 401:
      return "unauthorized";
    case 403:
      return "forbidden";
    case 404:
      return "not_found";
    case 409:
      return "conflict";
    case 422:
      return "invalid";
    case 503:
      return "unavailable";
    default:
      return "failure";
  }
}

export interface StaffClientOptions {
  baseUrl?: string;
  fetchImpl?: typeof fetch;
}

async function request<T>(
  token: string,
  path: string,
  init: RequestInit = {},
  { baseUrl = API_BASE_URL, fetchImpl = fetch }: StaffClientOptions = {},
): Promise<StaffResult<T>> {
  let response: Response;
  try {
    response = await fetchImpl(`${baseUrl.replace(/\/$/, "")}${path}`, {
      ...init,
      headers: {
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        Authorization: `Bearer ${token}`,
      },
    });
  } catch {
    return { ok: false, kind: "network", message: STAFF_MESSAGES.network };
  }

  if (!response.ok) {
    const kind = kindFor(response.status);
    return { ok: false, kind, status: response.status, message: STAFF_MESSAGES[kind] };
  }
  try {
    return { ok: true, data: (await response.json()) as T };
  } catch {
    return { ok: false, kind: "failure", status: response.status, message: STAFF_MESSAGES.failure };
  }
}

const clinicPath = (clinicId: string) => `/api/clinics/${encodeURIComponent(clinicId)}/intakes`;

export function fetchStaffMe(token: string, options?: StaffClientOptions) {
  return request<StaffMe>(token, "/api/staff/me", {}, options);
}

export function listIntakes(
  token: string,
  clinicId: string,
  reviewStatus: ReviewStatus | null,
  options?: StaffClientOptions,
) {
  const query = reviewStatus ? `?review_status=${encodeURIComponent(reviewStatus)}` : "";
  return request<IntakeSummary[]>(token, `${clinicPath(clinicId)}${query}`, {}, options);
}

export function getIntake(token: string, clinicId: string, intakeId: string, options?: StaffClientOptions) {
  return request<IntakeDetail>(
    token,
    `${clinicPath(clinicId)}/${encodeURIComponent(intakeId)}`,
    {},
    options,
  );
}

export function transitionIntake(
  token: string,
  clinicId: string,
  intakeId: string,
  target: TransitionTarget,
  options?: StaffClientOptions,
) {
  return request<IntakeDetail>(
    token,
    `${clinicPath(clinicId)}/${encodeURIComponent(intakeId)}/transition`,
    { method: "POST", body: JSON.stringify({ review_status: target }) },
    options,
  );
}

export type StaffApi = {
  fetchStaffMe: typeof fetchStaffMe;
  listIntakes: typeof listIntakes;
  getIntake: typeof getIntake;
  transitionIntake: typeof transitionIntake;
};

export const staffApi: StaffApi = { fetchStaffMe, listIntakes, getIntake, transitionIntake };
