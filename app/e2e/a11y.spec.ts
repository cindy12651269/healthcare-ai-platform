import { expect, Page, test } from "@playwright/test";

// Automated in-browser accessibility checks (#72). These cover part of WCAG 2.2 AA only; they are not
// a conformance claim. Manual observations are recorded separately in the Phase 8 journal.
const PAGES = [
  ["/", "Dashboard"],
  ["/intake", "Pre-visit symptom intake"],
  ["/staff", "Staff review"],
  ["/system-card", "System card"],
] as const;

// WebKit follows the macOS default where Tab skips links and buttons unless "Press Tab to highlight
// each item" is on; Option+Tab moves through every focusable element, as Safari keyboard users do.
let TAB = "Tab";
test.beforeEach(({ browserName }) => {
  TAB = browserName === "webkit" ? "Alt+Tab" : "Tab";
});

async function tabTo(page: Page, matches: () => Promise<boolean>, max = 60) {
  for (let i = 0; i < max; i++) {
    await page.keyboard.press(TAB);
    if (await matches()) return;
  }
  throw new Error("element not reachable with Tab");
}

for (const scheme of ["light", "dark"] as const) {
  test.describe(`${scheme} theme`, () => {
    test.use({ colorScheme: scheme });

    for (const [path] of PAGES) {
      test(`${path}: landmarks, one h1, skip link, visible focus`, async ({ page }) => {
        await page.goto(path);
        await expect(page.getByRole("banner")).toHaveCount(1);
        await expect(page.getByRole("main")).toHaveCount(1);
        await expect(page.getByRole("contentinfo")).toHaveCount(1);
        await expect(page.getByRole("navigation", { name: "Demo sections" })).toBeVisible();
        await expect(page.locator("h1")).toHaveCount(1);

        // 2.4.1: the first Tab stop is the skip link, it is visible when focused and moves focus to main
        await page.keyboard.press(TAB);
        const skip = page.getByRole("link", { name: "Skip to main content" });
        await expect(skip).toBeFocused();
        await expect(skip).toBeInViewport();
        await page.keyboard.press("Enter");
        await expect(page.locator("main#main")).toBeFocused();

        // 2.4.7: the next 15 keyboard focus stops all draw a visible focus indicator
        for (let i = 0; i < 15; i++) {
          await page.keyboard.press(TAB);
          const style = await page.evaluate(() => {
            const el = document.activeElement as HTMLElement | null;
            if (!el || el === document.body) return null;
            const s = getComputedStyle(el);
            return { tag: el.tagName, outline: s.outlineStyle, width: parseFloat(s.outlineWidth), shadow: s.boxShadow };
          });
          if (!style) break;
          const visible = (style.outline !== "none" && style.width >= 2) || style.shadow !== "none";
          expect(visible, `${style.tag} focus indicator`).toBe(true);
        }
      });

      test(`${path}: reflows at 320 CSS px (400% / 200% zoom equivalent)`, async ({ page }) => {
        await page.setViewportSize({ width: 320, height: 640 });
        await page.goto(path);
        await expect(page.locator("h1")).toBeVisible();
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
        expect(overflow).toBeLessThanOrEqual(0);
      });
    }
  });
}

test("reduced motion: no running animation or transition longer than 10 ms", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const [path] of PAGES) {
    await page.goto(path);
    const slow = await page.evaluate(() =>
      [...document.querySelectorAll<HTMLElement>("*")]
        .map((el) => getComputedStyle(el))
        .filter((s) => [s.animationDuration, s.transitionDuration].some((d) => d.split(",").some((v) => parseFloat(v) * (v.trim().endsWith("ms") ? 1 : 1000) > 10)))
        .length,
    );
    expect(slow, path).toBe(0);
  }
});

test("keyboard only: the intake form can be completed and submitted", async ({ page }) => {
  await page.goto("/intake");
  const textarea = page.getByLabel(/Your symptoms/);
  await tabTo(page, () => textarea.evaluate((el) => el === document.activeElement));
  await page.keyboard.type(`I have a stuffy nose since yesterday. Note ${Date.now().toString(36).replace(/[0-9]/g, "k")}.`);
  const consent = page.getByRole("checkbox", { name: /I consent/ });
  await tabTo(page, () => consent.evaluate((el) => el === document.activeElement), 10);
  await page.keyboard.press("Space");
  await expect(consent).toBeChecked();
  const submit = page.getByRole("button", { name: "Submit intake" });
  await tabTo(page, () => submit.evaluate((el) => el === document.activeElement), 10);
  await page.keyboard.press("Enter");
  await expect(page.getByRole("region", { name: "Your intake has been received" })).toBeVisible({ timeout: 30_000 });
});

test("keyboard only: an empty staff sign-in announces the error on the field", async ({ page }) => {
  await page.goto("/staff");
  const field = page.getByLabel("Access token");
  await tabTo(page, () => field.evaluate((el) => el === document.activeElement));
  await page.keyboard.press("Enter");
  await expect(field).toHaveAttribute("aria-invalid", "true");
});

test("mobile menu: Escape closes it and returns focus to the toggle", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 700 });
  await page.goto("/");
  const toggle = page.getByRole("button", { name: "Menu" });
  await toggle.focus();
  await page.keyboard.press("Enter");
  await expect(toggle).toHaveAttribute("aria-expanded", "true");
  await page.keyboard.press(TAB);
  await page.keyboard.press("Escape");
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await expect(toggle).toBeFocused();
});
