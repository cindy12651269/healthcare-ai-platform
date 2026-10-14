import { ReactNode } from "react";

export default function PageHeader({
  title,
  description,
  children,
}: {
  title: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <header className="page-header">
      <h1>{title}</h1>
      {description && <p className="page-description">{description}</p>}
      {children}
    </header>
  );
}
