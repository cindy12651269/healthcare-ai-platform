import { Component, ErrorInfo, ReactNode } from "react";
import ErrorPage from "./ErrorPage";

// Route-level error boundary (#72): a render error shows a styled page instead of a blank screen.
// No error details are rendered or sent anywhere; the error is only logged to the browser console.
export default class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Unhandled UI error", error, info.componentStack);
  }

  render() {
    if (this.state.failed) {
      return (
        <ErrorPage
          code="UI"
          title="Something went wrong"
          message="This page hit an unexpected error. Reload the page or return to the dashboard. No data was submitted."
        />
      );
    }
    return this.props.children;
  }
}
