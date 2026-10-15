import type { AppProps } from "next/app";
import ErrorBoundary from "../components/ErrorBoundary";
import "../styles/tokens.css";
import "../styles/globals.css";

export default function App({ Component, pageProps, router }: AppProps) {
  // Keyed by route so navigating away from a failed page resets the boundary.
  return (
    <ErrorBoundary key={router.asPath}>
      <Component {...pageProps} />
    </ErrorBoundary>
  );
}
