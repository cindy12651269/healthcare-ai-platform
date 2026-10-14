import Head from "next/head";
import Link from "next/link";
import { KeyboardEvent, ReactNode, useRef, useState } from "react";

// Shared layout (#68): brand, primary navigation, persistent demo indicator and footer for every page.
const LINKS: Array<[string, string]> = [
  ["/", "Guided demo"],
  ["/intake", "Patient intake"],
  ["/staff", "Staff review"],
  ["/system-card", "System card"],
];

export const DEMO_INDICATOR = "Demo · synthetic data · mock mode";

interface AppShellProps {
  title: string; // document title, before " | Healthcare AI Platform"
  current: string; // path of the current page, for aria-current
  width?: "reading" | "workspace";
  indicators?: ReactNode; // extra header badges (e.g. the intake page's live LLM mode)
  children: ReactNode;
}

export default function AppShell({ title, current, width = "reading", indicators, children }: AppShellProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const toggleRef = useRef<HTMLButtonElement>(null);

  function onNavKeyDown(e: KeyboardEvent) {
    if (e.key === "Escape" && menuOpen) {
      setMenuOpen(false);
      toggleRef.current?.focus();
    }
  }

  return (
    <>
      <Head>
        <title>{`${title} | Healthcare AI Platform`}</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>
      <a className="skip-link" href="#main">
        Skip to main content
      </a>
      <header className="site-header">
        <div className="shell-bar container-workspace">
          <Link href="/" className="brand">
            <svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true" className="brand-mark">
              <rect x="1" y="1" width="22" height="22" rx="6" fill="currentColor" />
              <path d="M12 6v12M6 12h12" stroke="var(--color-on-primary)" strokeWidth="2.6" strokeLinecap="round" />
            </svg>
            <span>Healthcare AI Platform</span>
          </Link>
          <button
            ref={toggleRef}
            type="button"
            className="nav-toggle"
            aria-expanded={menuOpen}
            aria-controls="site-nav"
            onClick={() => setMenuOpen((o) => !o)}
          >
            <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
              <path d={menuOpen ? "M6 6l12 12M18 6L6 18" : "M4 7h16M4 12h16M4 17h16"} stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
            Menu
          </button>
          <nav id="site-nav" className="site-nav" aria-label="Demo sections" data-open={menuOpen} onKeyDown={onNavKeyDown}>
            {LINKS.map(([href, label]) => (
              <Link key={href} href={href} aria-current={href === current ? "page" : undefined} onClick={() => setMenuOpen(false)}>
                {label}
              </Link>
            ))}
          </nav>
        </div>
        <div className="demo-bar">
          <div className="container-workspace demo-bar-inner">
            <span className="demo-indicator" data-testid="demo-indicator">
              {DEMO_INDICATOR}
            </span>
            {indicators}
          </div>
        </div>
      </header>
      <main id="main" tabIndex={-1} className={width === "workspace" ? "container-workspace" : "container-reading"}>
        {children}
      </main>
      <footer className="site-footer">
        <div className="container-workspace">Portfolio demonstration. Not a medical device; not for real patient data.</div>
      </footer>
    </>
  );
}
