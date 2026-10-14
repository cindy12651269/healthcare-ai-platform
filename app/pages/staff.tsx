import ApiStatus from "../components/ApiStatus";
import AppShell from "../components/AppShell";
import { PageHeader } from "../components/ui";
import StaffReview from "../components/StaffReview";
import { waitForApi } from "../services/api";

// Staff review workspace (Issue #31). Separate from the patient intake page at "/intake".
export default function StaffPage({ checkApi = waitForApi }: { checkApi?: typeof waitForApi }) {
  return (
    <AppShell title="Staff Review" current="/staff" width="workspace">
        <ApiStatus wait={checkApi} />
        <PageHeader
          title="Clinic review queue"
          description="Review intakes flagged by the escalation rules and mark them reviewed or escalated."
        />
        <StaffReview />
    </AppShell>
  );
}
