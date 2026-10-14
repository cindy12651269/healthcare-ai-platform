import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AppShell, { DEMO_INDICATOR } from "../components/AppShell";
import {
  Alert,
  Button,
  Card,
  DataTable,
  EmptyState,
  LoadingMessage,
  PageHeader,
  ReasonLabel,
  ReasonList,
  Skeleton,
  StatusBadge,
} from "../components/ui";

describe("Button", () => {
  it.each(["primary", "secondary", "danger", "ghost"] as const)("renders the %s variant with its accessible name", (variant) => {
    const onClick = vi.fn();
    render(<Button variant={variant} onClick={onClick}>Save</Button>);
    const button = screen.getByRole("button", { name: "Save" });
    expect(button).toHaveClass("btn", `btn-${variant}`);
    expect(button).toHaveAttribute("type", "button");
    button.click();
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("keeps an explicit submit type and the disabled state", () => {
    render(<Button type="submit" disabled>Send</Button>);
    expect(screen.getByRole("button", { name: "Send" })).toHaveAttribute("type", "submit");
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });
});

describe("Card, PageHeader, Alert", () => {
  it("renders a card as the requested element", () => {
    render(<Card as="article" aria-label="Detail">x</Card>);
    expect(screen.getByRole("article", { name: "Detail" })).toHaveClass("card");
  });

  it("renders the page title as the level-1 heading", () => {
    render(<PageHeader title="Queue" description="Flagged intakes" />);
    expect(screen.getByRole("heading", { level: 1, name: "Queue" })).toBeInTheDocument();
    expect(screen.getByText("Flagged intakes")).toBeInTheDocument();
  });

  it.each([
    ["error", "alert"],
    ["urgent", "alert"],
    ["warning", "status"],
    ["success", "status"],
    ["info", "status"],
  ] as const)("announces a %s alert as role=%s", (variant, role) => {
    render(<Alert variant={variant} title="Heads up">Body</Alert>);
    const el = screen.getByRole(role);
    expect(el).toHaveClass(`alert-${variant}`);
    expect(el).toHaveTextContent("Heads upBody");
  });

  it("lets the caller override the role", () => {
    render(<Alert variant="urgent" role="note">Static</Alert>);
    expect(screen.getByRole("note")).toHaveTextContent("Static");
  });
});

describe("StatusBadge and ReasonLabel", () => {
  it.each([
    ["submitted", "Submitted", "tone-info"],
    ["needs_review", "Needs review", "tone-warning"],
    ["reviewed", "Reviewed", "tone-success"],
    ["escalated", "Escalated", "tone-escalated"],
    ["archived", "archived", "tone-neutral"],
  ])("shows %s as %s", (status, label, tone) => {
    render(<StatusBadge status={status} />);
    const badge = screen.getByText(label);
    expect(badge).toHaveClass("status-badge", tone);
    expect(badge).toHaveAttribute("data-status", status);
  });

  it.each([
    ["emergency_signal", "Emergency signal", "tone-emergency"],
    ["blocked_diagnosis", "Blocked: diagnostic language", "tone-blocked"],
    ["blocked_prescription", "Blocked: prescription or dosing", "tone-blocked"],
    ["low_confidence", "Low structuring confidence", "tone-warning"],
  ])("labels %s and keeps the code visible", (code, label, tone) => {
    render(<ReasonLabel code={code} />);
    expect(screen.getByText(label)).toBeInTheDocument();
    expect(screen.getByText(code).tagName).toBe("CODE");
    expect(screen.getByText(code).closest(".reason")).toHaveClass(tone);
  });

  it("shows an unknown code as-is", () => {
    render(<ReasonLabel code="new_rule" />);
    expect(screen.getByText("new_rule").closest(".reason")).toHaveClass("tone-neutral");
  });

  it("splits stored comma-separated reasons and shows a fallback when empty", () => {
    const { rerender, container } = render(<ReasonList reasons="emergency_signal,low_confidence" />);
    expect(container.querySelectorAll(".reason")).toHaveLength(2);
    rerender(<ReasonList reasons={null} empty="None" />);
    expect(container).toHaveTextContent("None");
  });
});

describe("DataTable", () => {
  const rows = [{ id: "a", n: 1 }, { id: "b", n: 2 }];
  it("renders headers, cells and a labelled, focusable scroll region", () => {
    render(
      <DataTable
        label="Numbers"
        testId="nums"
        rows={rows}
        rowKey={(r) => r.id}
        columns={[
          { key: "id", header: "Id", render: (r) => r.id },
          { key: "n", header: "Count", numeric: true, render: (r) => r.n },
        ]}
      />,
    );
    const region = screen.getByRole("region", { name: "Numbers" });
    expect(region).toHaveAttribute("tabindex", "0");
    const table = within(region).getByTestId("nums");
    expect(within(table).getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["Id", "Count"]);
    expect(within(table).getAllByRole("row")).toHaveLength(3);
    expect(within(table).getByText("2")).toHaveAttribute("data-label", "Count");
  });
});

describe("EmptyState, LoadingMessage, Skeleton", () => {
  it("renders an empty state with title and action", () => {
    render(<EmptyState title="Nothing here" description="Try another filter" action={<Button>Reset</Button>} />);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reset" })).toBeInTheDocument();
  });

  it("announces loading text with a decorative spinner, and hides the skeleton from assistive tech", () => {
    render(
      <>
        <LoadingMessage>Loading…</LoadingMessage>
        <Skeleton lines={2} />
      </>,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Loading…");
    expect(screen.getByRole("status").querySelector(".spinner")).toHaveAttribute("aria-hidden", "true");
    expect(screen.getByTestId("skeleton")).toHaveAttribute("aria-hidden", "true");
  });
});

describe("AppShell", () => {
  it("renders brand, four nav links with the current page, the demo indicator, main and footer", () => {
    render(
      <AppShell title="Staff Review" current="/staff" width="workspace">
        <p>content</p>
      </AppShell>,
    );
    expect(screen.getByRole("link", { name: "Healthcare AI Platform" })).toHaveAttribute("href", "/");
    const nav = screen.getByRole("navigation", { name: "Demo sections" });
    expect(within(nav).getAllByRole("link")).toHaveLength(4);
    expect(within(nav).getByRole("link", { name: "Staff review" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByTestId("demo-indicator")).toHaveTextContent(DEMO_INDICATOR);
    expect(DEMO_INDICATOR).toBe("Demo · synthetic data · mock mode");
    expect(screen.getByRole("main")).toHaveClass("container-workspace");
    expect(screen.getByRole("contentinfo")).toHaveTextContent("Not a medical device");
    expect(screen.getByRole("link", { name: "Skip to main content" })).toHaveAttribute("href", "#main");
  });

  it("uses the narrow reading width by default", () => {
    render(<AppShell title="Intake" current="/intake">x</AppShell>);
    expect(screen.getByRole("main")).toHaveClass("container-reading");
  });

  it("toggles the mobile menu with the keyboard and closes it on Escape", async () => {
    const user = userEvent.setup();
    render(<AppShell title="Intake" current="/intake">x</AppShell>);
    const toggle = screen.getByRole("button", { name: "Menu" });
    const nav = screen.getByRole("navigation", { name: "Demo sections" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(toggle).toHaveAttribute("aria-controls", nav.id);

    toggle.focus();
    await user.keyboard("{Enter}");
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(nav).toHaveAttribute("data-open", "true");

    await user.tab();
    expect(within(nav).getAllByRole("link")[0]).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(toggle).toHaveFocus();
  });
});
