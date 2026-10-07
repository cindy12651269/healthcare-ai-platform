import Head from "next/head";
import StaffReview from "../components/StaffReview";

// Staff review workspace (Issue #31). Separate from the patient intake page at "/".
export default function StaffPage() {
  return (
    <>
      <Head>
        <title>Staff Review | Healthcare AI Platform</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      <header className="site-header">
        <div className="container">
          <span className="brand">Healthcare AI Platform · Staff</span>
          <span className="badges">
            <span className="badge">Demo · synthetic data only</span>
          </span>
        </div>
      </header>

      <main className="container">
        <section className="intro">
          <h1>Clinic review queue</h1>
          <p>Review intakes flagged by the escalation rules and mark them reviewed or escalated.</p>
        </section>
        <StaffReview />
      </main>

      <footer className="site-footer container">
        Portfolio demonstration. Not a medical device; not for real patient data.
      </footer>
    </>
  );
}
