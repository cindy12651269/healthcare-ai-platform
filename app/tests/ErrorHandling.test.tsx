import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import ErrorBoundary from "../components/ErrorBoundary";
import NotFound from "../pages/404";
import ServerError from "../pages/500";

function Boom(): never {
  throw new Error("render failure");
}

describe("error handling (#72)", () => {
  it("renders a styled 404 page inside the app shell", () => {
    render(<NotFound />);
    expect(screen.getByRole("heading", { level: 1, name: "Page not found" })).toBeInTheDocument();
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Return to the dashboard" })).toHaveAttribute("href", "/");
  });

  it("renders a styled 500 page", () => {
    render(<ServerError />);
    expect(screen.getByRole("heading", { level: 1, name: "Server error" })).toBeInTheDocument();
  });

  it("catches a render error and shows the fallback without leaking the message", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    expect(screen.getByRole("heading", { level: 1, name: "Something went wrong" })).toBeInTheDocument();
    expect(screen.queryByText(/render failure/)).not.toBeInTheDocument();
    spy.mockRestore();
  });
});
