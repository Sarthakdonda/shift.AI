import { test, expect } from "@playwright/test";

for (const mode of ["login", "signup"] as const) {
  test(`${mode} waits for a sleeping backend and submits only once`, async ({
    page,
  }, testInfo) => {
    const email = `startup-${mode}-${testInfo.project.name}-${Date.now()}@example.com`;
    const password = "startup-test-passphrase-123";
    if (mode === "login") {
      const response = await page.request.post(
        "http://localhost:8011/api/auth/signup",
        {
          data: { name: "Startup Reviewer", email, password },
          headers: { Origin: "http://localhost:3011" },
        },
      );
      expect(response.status()).toBe(201);
      await page.context().clearCookies();
    }
    await page.goto(`/${mode}`);
    const submit = page.getByRole("button", {
      name: mode === "login" ? "Sign in" : "Create account",
      exact: true,
    });
    await expect(submit).toBeEnabled();
    let probes = 0;
    let submissions = 0;
    await page.route("**/api/health", async (route) => {
      probes++;
      if (probes <= 2) {
        await route.fulfill({
          status: probes === 1 ? 502 : 200,
          contentType: "text/html",
          body: "<html><body>Starting service</body></html>",
        });
      } else await route.continue();
    });
    await page.route(`**/api/auth/${mode}`, async (route) => {
      submissions++;
      expect(probes).toBeGreaterThanOrEqual(3);
      await route.continue();
    });
    if (mode === "signup") {
      await page.getByLabel("Full name").fill("Startup Reviewer");
      await page.getByLabel("Confirm password", { exact: true }).fill(password);
    }
    await page.getByLabel("Email address").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await submit.click();
    await expect(
      page
        .getByRole("status")
        .filter({ hasText: "Your workspace is starting" }),
    ).toBeVisible();
    expect(submissions).toBe(0);
    await expect(
      page.getByRole("button", { name: /Signing in|Creating your account/ }),
    ).toBeDisabled();
    await page.waitForURL("**/dashboard");
    await expect(
      page.getByRole("heading", { name: "Welcome back, Startup." }),
    ).toBeVisible();
    expect(submissions).toBe(1);
  });
}

test("incorrect credentials are reported without retrying login", async ({
  page,
}) => {
  await page.goto("/login");
  let submissions = 0;
  await page.route("**/api/auth/login", async (route) => {
    submissions++;
    await route.fulfill({
      status: 401,
      json: { detail: "Email or password is incorrect." },
    });
  });
  await page.getByLabel("Email address").fill("invalid-startup@example.com");
  await page.getByLabel("Password", { exact: true }).fill("incorrect-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("main").getByRole("alert")).toHaveText(
    "Email or password is incorrect.",
  );
  await expect(
    page.getByRole("button", { name: "Sign in", exact: true }),
  ).toBeEnabled();
  expect(submissions).toBe(1);
});

test("a persistent startup outage times out without submitting credentials", async ({
  page,
}) => {
  await page.goto("/login");
  await expect(
    page.getByRole("button", { name: "Sign in", exact: true }),
  ).toBeEnabled();
  await page.clock.install();
  let submissions = 0;
  await page.route("**/api/health", (route) =>
    route.fulfill({ status: 504, body: "Gateway timeout" }),
  );
  await page.route("**/api/auth/login", (route) => {
    submissions++;
    return route.abort();
  });
  await page.getByLabel("Email address").fill("startup-timeout@example.com");
  await page
    .getByLabel("Password", { exact: true })
    .fill("test-passphrase-123");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Your workspace is starting" }),
  ).toBeVisible();
  await page.clock.fastForward(121_000);
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "taking longer than usual to start",
  );
  await expect(
    page.getByRole("button", { name: "Sign in", exact: true }),
  ).toBeEnabled();
  expect(submissions).toBe(0);
});
