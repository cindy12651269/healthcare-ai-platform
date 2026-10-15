import { ButtonHTMLAttributes, Ref } from "react";

export type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: "md" | "sm";
  ref?: Ref<HTMLButtonElement>; // e.g. to focus a confirmation button (#71)
}

// Shared button (#68). Defaults to type="button" so it never submits a form by accident.
export default function Button({ variant = "secondary", size = "md", type = "button", className, ...rest }: ButtonProps) {
  const classes = ["btn", `btn-${variant}`, size === "sm" ? "btn-sm" : "", className ?? ""].filter(Boolean).join(" ");
  return <button type={type} className={classes} {...rest} />;
}
