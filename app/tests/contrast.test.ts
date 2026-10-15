import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

// WCAG 2.2 1.4.3 / 1.4.11 contrast check of the design tokens (#72), in both themes.
const css = readFileSync(join(__dirname, "../styles/tokens.css"), "utf8");
const darkStart = css.indexOf("prefers-color-scheme: dark");

function tokens(block: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const m of block.matchAll(/--(color-[\w-]+):\s*(#[0-9a-fA-F]{6})/g)) out[m[1]] = m[2];
  return out;
}

const light = tokens(css.slice(0, darkStart));
const dark = { ...light, ...tokens(css.slice(darkStart)) };

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function ratio(a: string, b: string): number {
  const [x, y] = [luminance(a), luminance(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
}

// [foreground, background, minimum ratio]
const PAIRS: Array<[string, string, number]> = [
  ["color-text", "color-bg", 4.5],
  ["color-text", "color-surface", 4.5],
  ["color-text", "color-surface-sunken", 4.5],
  ["color-text-muted", "color-bg", 4.5],
  ["color-text-muted", "color-surface", 4.5],
  ["color-text-muted", "color-surface-sunken", 4.5],
  ["color-link", "color-surface", 4.5],
  ["color-link", "color-bg", 4.5],
  ["color-on-primary", "color-primary", 4.5],
  ["color-on-primary", "color-primary-hover", 4.5],
  ["color-on-danger", "color-danger", 4.5],
  ["color-danger", "color-surface", 4.5],
  ["color-text", "color-highlight", 4.5],
  ["color-focus", "color-bg", 3],
  ["color-focus", "color-surface", 3],
  ["color-border-strong", "color-surface", 3],
];

describe.each([
  ["light", light],
  ["dark", dark],
] as const)("%s theme token contrast", (_name, t) => {
  it.each(PAIRS)("%s on %s meets %s:1", (fg, bg, min) => {
    expect(t[fg], fg).toBeDefined();
    expect(t[bg], bg).toBeDefined();
    expect(ratio(t[fg], t[bg])).toBeGreaterThanOrEqual(min);
  });
});
