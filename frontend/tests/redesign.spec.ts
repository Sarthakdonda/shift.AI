import { test, expect } from "@playwright/test";

test("landing preview, navigation, FAQs, and brand fit desktop and mobile", async ({
  page,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /Big possibilities/ }),
  ).toBeVisible();
  await page.getByRole("tab", { name: /Diagnose/ }).click();
  await expect(page.getByRole("tabpanel")).toContainText(
    "Follow the evidence.",
  );
  await page.getByRole("tab", { name: /Diagnose/ }).press("ArrowRight");
  await expect(page.getByRole("tab", { name: /Challenge/ })).toBeFocused();
  await expect(page.getByRole("tabpanel")).toContainText(
    "Give the plan a second look.",
  );
  await page.getByRole("tab", { name: /Discover/ }).click();
  const logo = page.locator(".nav-inner .logo");
  const logoBox = await logo.boundingBox();
  const markBox = await logo.locator("img").boundingBox();
  expect(logoBox).toBeTruthy();
  expect(markBox).toBeTruthy();
  expect(markBox!.height).toBeLessThanOrEqual(logoBox!.height);
  if (testInfo.project.name === "mobile") {
    await page.getByRole("button", { name: "Open menu" }).click();
    await page
      .locator(".nav-drawer")
      .getByRole("link", { name: "How it works" })
      .click();
    await expect(page.locator(".nav-drawer")).toHaveCount(0);
  }
  const faq = page.locator("details").first();
  await faq.locator("summary").click();
  await expect(faq).toHaveAttribute("open", "");
  await expect(faq.locator("p")).toBeVisible();
  await page.evaluate(() =>
    document
      .querySelectorAll(".reveal")
      .forEach((el) => el.classList.add("is-visible")),
  );
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: `test-results/redesign-landing-${testInfo.project.name}.png`,
    fullPage: true,
    animations: "disabled",
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  expect(errors).toEqual([]);
});

test("login validates inline, toggles password, and never fakes authentication", async ({
  page,
}, testInfo) => {
  let credentialRequests = 0;
  page.on("request", (request) => {
    if (request.url().includes("/auth/login") && request.method() === "POST")
      credentialRequests++;
  });
  page.on("dialog", () => {
    throw new Error("Native browser dialogs must not be used.");
  });
  await page.goto("/login");
  const submit = page.getByRole("button", { name: "Sign in", exact: true });
  await expect(submit).toBeEnabled();
  await submit.click();
  await expect(page.getByText("Enter a valid email address.")).toBeVisible();
  await expect(page.getByLabel("Email address")).toBeFocused();
  await page.getByLabel("Email address").fill("hello@example.com");
  await page.getByLabel("Password", { exact: true }).fill("example-password");
  await page.getByRole("button", { name: "Show password" }).click();
  await expect(page.getByLabel("Password", { exact: true })).toHaveAttribute(
    "type",
    "text",
  );
  await page.getByRole("button", { name: "Hide password" }).click();
  await submit.click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "Email or password is incorrect.",
  );
  expect(credentialRequests).toBe(1);
  await expect(page).toHaveURL(/\/login$/);
  await page.screenshot({
    path: `test-results/redesign-login-${testInfo.project.name}.png`,
    fullPage: true,
    animations: "disabled",
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});

test("logout requires confirmation, supports cancellation, and keeps errors in the dialog", async ({
  page,
}, testInfo) => {
  let logoutRequests = 0;
  let failLogout = true;
  await page.route("**/api/auth/me", (route) =>
    route.fulfill({
      json: {
        id: "test-user",
        name: "Alex Morgan",
        email: "alex@example.com",
        local: false,
      },
    }),
  );
  await page.route("**/api/auth/logout", (route) => {
    logoutRequests++;
    return route.fulfill({
      status: failLogout ? 503 : 200,
      json: failLogout ? { detail: "Unavailable" } : { ok: true },
    });
  });
  page.on("dialog", () => {
    throw new Error("Native browser dialogs must not be used.");
  });
  await page.goto("/dashboard");
  if (testInfo.project.name === "mobile")
    await page.getByRole("button", { name: "Toggle navigation" }).click();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("heading", { name: "Sign out of your workspace?" }),
  ).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Cancel" })).toBeFocused();
  await dialog.getByRole("button", { name: "Cancel" }).click();
  expect(logoutRequests).toBe(0);
  if (testInfo.project.name === "mobile")
    await page.getByRole("button", { name: "Toggle navigation" }).click();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await dialog.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText(
    "temporarily unavailable",
  );
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.screenshot({
    path: `test-results/redesign-confirm-${testInfo.project.name}.png`,
    fullPage: true,
    animations: "disabled",
  });
  failLogout = false;
  await dialog.getByRole("button", { name: "Sign out", exact: true }).click();
  await page.waitForURL("/login");
  expect(logoutRequests).toBe(2);
});

test("drafts are protected when replacing details and navigating away", async ({
  page,
}) => {
  await page.goto("/project/new");
  await page.getByLabel("Project name").fill("My important draft");
  await page
    .getByRole("button", { name: "Simplify invoice processing" })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("heading", { name: "Replace your project details?" }),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByLabel("Project name")).toHaveValue(
    "My important draft",
  );
  await page
    .getByRole("button", { name: "Simplify invoice processing" })
    .click();
  await dialog.getByRole("button", { name: "Use example" }).click();
  await expect(page.getByLabel("Project name")).toHaveValue(
    "Simplify invoice processing",
  );
  await page.getByRole("link", { name: "Cancel", exact: true }).click();
  await expect(
    dialog.getByRole("heading", { name: "Leave this draft?" }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByLabel("Project name")).toHaveValue(
    "Simplify invoice processing",
  );
  await page.getByRole("link", { name: "Cancel", exact: true }).click();
  await dialog.getByRole("button", { name: "Discard draft" }).click();
  await page.waitForURL("/dashboard");
});

test("reduced motion keeps landing content visible", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /Big possibilities/ }),
  ).toBeVisible();
  await expect(page.locator(".home-final h2")).toHaveCSS("opacity", "1");
  await expect(page.locator(".orbit-one")).toHaveCSS(
    "animation-duration",
    "1e-06s",
  );
});
