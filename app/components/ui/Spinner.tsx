// Loading indicators (#68). Decorative only: the surrounding text carries the role="status".
export function Spinner() {
  return <span className="spinner" aria-hidden="true" />;
}

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="skeleton" aria-hidden="true" data-testid="skeleton">
      {Array.from({ length: lines }, (_, i) => (
        <span key={i} className="skeleton-line" />
      ))}
    </div>
  );
}

export function LoadingMessage({ children }: { children: string }) {
  return (
    <p className="status-loading" role="status">
      <Spinner /> {children}
    </p>
  );
}
