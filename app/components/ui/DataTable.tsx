import { HTMLAttributes, ReactNode } from "react";

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  numeric?: boolean;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  label: string; // accessible name of the scroll region
  layout?: "scroll" | "stack"; // small screens: scroll inside the container, or stack rows as cards
  testId?: string;
  rowProps?: (row: T) => HTMLAttributes<HTMLTableRowElement>;
}

// Responsive table (#68). It never widens the page: it scrolls inside its own keyboard-focusable
// region or, with layout="stack", turns each row into a labelled block below 768px.
export default function DataTable<T>({ columns, rows, rowKey, label, layout = "scroll", testId, rowProps }: DataTableProps<T>) {
  return (
    <div className={`table-wrap table-${layout}`} role="region" aria-label={label} tabIndex={0}>
      <table className="data-table" data-testid={testId}>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} scope="col" className={c.numeric ? "num" : undefined}>
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)} {...rowProps?.(row)}>
              {columns.map((c) => (
                <td key={c.key} data-label={c.header} className={c.numeric ? "num" : undefined}>
                  {c.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
