import { Head, Html, Main, NextScript } from "next/document";

// Document shell (#72): page language for assistive technology (WCAG 3.1.1), a site description and an
// inline icon so browsers do not request a missing /favicon.ico (Lighthouse findings, 2026-10-15).
const ICON =
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect x='1' y='1' width='22' height='22' rx='6' fill='%230f6e78'/%3E%3Cpath d='M12 6v12M6 12h12' stroke='white' stroke-width='2.6' stroke-linecap='round'/%3E%3C/svg%3E";

export default function Document() {
  return (
    <Html lang="en">
      <Head>
        <meta
          name="description"
          content="Portfolio demo of a pre-visit healthcare intake: synthetic data, mock-mode AI structuring, safety checks and a staff review workspace."
        />
        <link rel="icon" href={ICON} />
      </Head>
      <body>
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}
