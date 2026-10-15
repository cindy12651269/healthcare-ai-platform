import Link from "next/link";
import AppShell from "./AppShell";
import { PageHeader } from "./ui";

// Styled error page (#72): shared by the 404/500 routes and the route-level error boundary.
export default function ErrorPage({ code, title, message }: { code: string; title: string; message: string }) {
  return (
    <AppShell title={title} current="">
      <PageHeader title={title} description={`Error ${code}`} />
      <p>{message}</p>
      <p>
        <Link href="/">Return to the dashboard</Link>
      </p>
    </AppShell>
  );
}
