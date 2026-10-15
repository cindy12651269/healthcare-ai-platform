import { HTMLAttributes, ReactNode, Ref } from "react";

export type AlertVariant = "info" | "success" | "warning" | "error" | "urgent";

export interface AlertProps extends Omit<HTMLAttributes<HTMLDivElement>, "title"> {
  variant?: AlertVariant;
  title?: ReactNode;
  ref?: Ref<HTMLDivElement>; // e.g. to move focus to an error (#70)
}

// Errors and urgent notices are announced (role="alert"); others are polite status messages.
// Callers can override the role (e.g. role="note" for static notices).
export default function Alert({ variant = "info", title, role, className, children, ...rest }: AlertProps) {
  const defaultRole = variant === "error" || variant === "urgent" ? "alert" : "status";
  return (
    <div role={role ?? defaultRole} className={["alert", `alert-${variant}`, className].filter(Boolean).join(" ")} {...rest}>
      {title && <strong className="alert-title">{title}</strong>}
      {children}
    </div>
  );
}
