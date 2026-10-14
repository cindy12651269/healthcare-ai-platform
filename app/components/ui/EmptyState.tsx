import { ReactNode } from "react";

export default function EmptyState({ title, description, action }: { title: string; description?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty-state">
      <svg className="empty-icon" viewBox="0 0 24 24" width="28" height="28" aria-hidden="true">
        <path d="M4 7h16v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7Zm0 0 2-3h12l2 3M9 12h6" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <p className="empty-title">{title}</p>
      {description && <p className="empty-description">{description}</p>}
      {action}
    </div>
  );
}
