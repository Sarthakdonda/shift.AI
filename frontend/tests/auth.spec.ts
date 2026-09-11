import { test, expect } from "@playwright/test";

test("account navigation and the new authentication layouts", async ({
  page,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  if (testInfo.project.name === "mobile")
    await page.getByRole("button", { name: "Open menu", exact: true }).click();
  await page
    .getByRole("link", { name: "Sign up", exact: true })
    .filter({ visible: true })
    .click();
  await expect(page).toHaveURL(/\/signup$/);
  await expect(
    page.getByRole("heading", { name: "Create your account." }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Continue locally" }),
  ).toHaveCount(0);
  await expect(page.getByLabel("Full name")).toBeVisible();
  const google = page.getByRole("button", { name: "Continue with Google" });
  await expect(google).toBeVisible();
  await expect(google).toBeDisabled();
  const switchLink = await page
    .getByRole("link", { name: "Sign in", exact: true })
    .boundingBox();
  const heading = await page
    .getByRole("heading", { name: "Create your account." })
    .boundingBox();
  const firstField = await page.getByLabel("Full name").boundingBox();
  expect(switchLink!.y).toBeLessThan(heading!.y);
  expect(switchLink!.y).toBeLessThan(firstField!.y);
  await page.screenshot({
    path: `test-results/auth-signup-${testInfo.project.name}.png`,
    fullPage: true,
  });
  await page.getByRole("link", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Welcome back." }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Sign in", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Continue with Google" }),
  ).toBeVisible();
  await page.screenshot({
    path: `test-results/auth-login-${testInfo.project.name}.png`,
    fullPage: true,
  });
  if (testInfo.project.name === "desktop") {
    for (const size of [
      { width: 1366, height: 768 },
      { width: 1280, height: 720 },
    ]) {
      await page.setViewportSize(size);
      for (const route of ["/login", "/signup", "/forgot-password"]) {
        await page.goto(route);
        await expect(page.getByRole("heading").first()).toBeVisible();
        expect(
          await page.evaluate(
            () => document.documentElement.scrollHeight <= innerHeight,
          ),
        ).toBeTruthy();
      }
    }
    await page.goto("/login");
    const back = await page
      .getByRole("link", { name: "Back to home" })
      .boundingBox();
    expect(back!.y).toBeLessThan(70);
    expect(back!.x).toBeLessThan(400);
  }
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.getByRole("link", { name: "Back to home" }).click();
  await expect(page).toHaveURL(/\/$/);
  expect(errors).toEqual([]);
});

test("signup validates each field and email login restores the real session", async ({
  page,
}, testInfo) => {
  const email = `auth-${testInfo.project.name}-${Date.now()}@example.com`;
  const password = "a-test-passphrase-123";
  await page.goto("/signup");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(page.getByLabel("Full name")).toBeFocused();
  await expect(page.getByLabel("Full name")).toHaveAttribute(
    "aria-invalid",
    "true",
  );
  await page.getByLabel("Full name").fill("Account Reviewer");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("short");
  await page.getByLabel("Confirm password", { exact: true }).fill("short");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(page.getByLabel("Password", { exact: true })).toBeFocused();
  await expect(
    page.getByText("Use at least 12 characters for your password."),
  ).toBeVisible();
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(
    page.getByLabel("Confirm password", { exact: true }),
  ).toBeFocused();
  await page.getByLabel("Confirm password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Show confirm password" }).click();
  await expect(
    page.getByLabel("Confirm password", { exact: true }),
  ).toHaveAttribute("type", "text");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await page.waitForURL("**/dashboard");
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Welcome back, Account." }),
  ).toBeVisible();
  await page.context().clearCookies();
  await page.goto("/login");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL("**/dashboard");
  await expect(
    page.getByRole("heading", { name: "Welcome back, Account." }),
  ).toBeVisible();
});

test("forgot password issues a single-use link that replaces the old password", async ({
  page,
}, testInfo) => {
  const email = `reset-${testInfo.project.name}-${Date.now()}@example.com`;
  const password = "first-test-passphrase-123";
  const replacement = "second-test-passphrase-456";
  await page.goto("/signup");
  await page.getByLabel("Full name").fill("Reset Reviewer");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm password", { exact: true }).fill(password);
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await page.waitForURL("**/dashboard");
  await page.context().clearCookies();
  await page.goto("/login");
  await page.getByRole("link", { name: "Forgot password?" }).click();
  await expect(page).toHaveURL(/\/forgot-password$/);
  await expect(
    page.getByRole("heading", { name: "Reset your password." }),
  ).toBeVisible();
  await page.getByLabel("Email address").fill(email);
  await page.getByRole("button", { name: "Send reset link" }).click();
  await expect(
    page.getByRole("heading", { name: "Check your email." }),
  ).toBeVisible();
  const link = page.getByRole("link", { name: /reset-password\?token=/ });
  await expect(link).toBeVisible();
  const target = new URL((await link.getAttribute("href")) as string);
  await page.goto(`${target.pathname}${target.search}`);
  await expect(
    page.getByRole("heading", { name: "Choose a new password." }),
  ).toBeVisible();
  await page.getByLabel("New password", { exact: true }).fill("short");
  await page
    .getByLabel("Confirm new password", { exact: true })
    .fill("shorter");
  await page.getByRole("button", { name: "Update password" }).click();
  await expect(
    page.getByText("Use at least 12 characters for your password."),
  ).toBeVisible();
  await page.getByLabel("New password", { exact: true }).fill(replacement);
  await page
    .getByLabel("Confirm new password", { exact: true })
    .fill(replacement);
  await page.getByRole("button", { name: "Update password" }).click();
  await page.waitForURL("**/login");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "Email or password is incorrect.",
  );
  await page.getByLabel("Password", { exact: true }).fill(replacement);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL("**/dashboard");
  await page.goto(`${target.pathname}${target.search}`);
  await expect(
    page.getByRole("heading", { name: "This link has expired." }),
  ).toBeVisible();
});
