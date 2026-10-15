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

// Readable short reference for an intake id (full id stays available in the detail view)
export const intakeRef = (id: string) => `#${id.slice(0, 8)}`;
