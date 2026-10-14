import { ComponentPropsWithoutRef, ElementType } from "react";

type CardTag = "section" | "article" | "div" | "form" | "aside";

export type CardProps<T extends CardTag = "section"> = { as?: T } & ComponentPropsWithoutRef<T>;

// Surface container (#68)
export default function Card<T extends CardTag = "section">({ as, className, ...rest }: CardProps<T>) {
  const Tag = (as ?? "section") as ElementType;
  return <Tag className={["card", className].filter(Boolean).join(" ")} {...rest} />;
}
