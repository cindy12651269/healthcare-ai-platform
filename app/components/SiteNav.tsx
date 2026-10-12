import Link from "next/link";

// Navigation between the guided demo sections (#43)
const LINKS: Array<[string, string]> = [
  ["/", "Guided demo"],
  ["/intake", "Patient intake"],
  ["/staff", "Staff review"],
  ["/system-card", "System card"],
];

export default function SiteNav({ current }: { current: string }) {
  return (
    <nav className="site-nav" aria-label="Demo sections">
      {LINKS.map(([href, label]) => (
        <Link key={href} href={href} aria-current={href === current ? "page" : undefined}>
          {label}
        </Link>
      ))}
    </nav>
  );
}
