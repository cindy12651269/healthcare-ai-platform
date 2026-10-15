// One date/time format for staff views (#71): explicit locale and timezone, so every reviewer sees the
// same unambiguous value whatever the browser's locale. Unparseable values are shown as received.
const STAFF_DATE_TIME = new Intl.DateTimeFormat("en-US", {
  timeZone: "UTC",
  year: "numeric",
  month: "short",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

export function formatStaffDateTime(iso: string | null | undefined, missing = "—"): string {
  if (!iso) return missing;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : `${STAFF_DATE_TIME.format(d)} UTC`;
}

// Readable reference for an intake id (#84). Hash-like ids (32-hex or UUID) are shortened to their
// first 8 characters (#2f005d14); any other id, such as the seeded "demo-intake-b2", is shown in full,
// because a prefix of it is shared by every seeded record. Display only: API calls, data attributes and
// the detail view always use the full id.
const HASH_LIKE_ID = /^(?:[0-9a-f]{32}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/i;

export const intakeRef = (id: string) => `#${HASH_LIKE_ID.test(id) ? id.slice(0, 8) : id}`;
