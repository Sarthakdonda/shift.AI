import { test, expect } from "@playwright/test";

test("landing, discovery, documents, no-AI analysis, reviewed blueprint, and deletion", async ({
  page,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /Big possibilities/ }),
  ).toBeVisible();
  await expect(page.locator("body")).not.toHaveJSProperty("scrollWidth", 0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: `test-results/landing-${testInfo.project.name}.png`,
    fullPage: true,
  });
  await page.getByRole("link", { name: "Find your next shift" }).click();
  await page
    .getByRole("button", { name: "Simplify invoice processing" })
    .click();
  await expect(page.getByLabel("Project name")).toHaveValue(
    "Simplify invoice processing",
  );
  await page
    .getByLabel("Project name")
    .fill(`Invoice pilot ${testInfo.project.name}`);
  await page.getByRole("button", { name: "Start discovery" }).click();
  await page.waitForURL(/\/project\/[a-f0-9]{24}$/);
  const projectPath = new URL(page.url()).pathname;
  await page.getByRole("button", { name: "Begin the conversation" }).click();
  await expect(
    page
      .locator(".ready-banner")
      .getByText("Discovery complete. Your context is saved.", {
        exact: true,
      }),
  ).toBeVisible();
  await page
    .getByRole("textbox", { name: "Your message" })
    .fill(
      "We manually review each invoice, then import records. Fixed rules cover all fields.",
    );
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByRole("textbox", { name: "Your message" })).toHaveValue(
    "",
  );
  await page.reload();
  await expect(
    page.getByText(
      "We manually review each invoice, then import records. Fixed rules cover all fields.",
      { exact: true },
    ),
  ).toBeVisible();
  await page.screenshot({
    path: `test-results/discovery-${testInfo.project.name}.png`,
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.goto(`${projectPath}/documents`);
  await page.locator("input[type=file]").setInputFiles({
    name: "workflow.txt",
    mimeType: "text/plain",
    buffer: Buffer.from(
      "Invoices arrive by email and staff enter data in a shared spreadsheet.",
    ),
  });
  await expect(page.getByText("Processed", { exact: true })).toBeVisible();
  await expect(
    page.getByText("Invoice processing uses email and a shared spreadsheet.", {
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: /Remove/ }).click();
  await expect(
    page
      .getByRole("dialog")
      .getByRole("heading", { name: "Remove this document?" }),
  ).toBeVisible();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Cancel" })
    .click();
  await expect(page.getByText("Processed", { exact: true })).toBeVisible();
  await page.goto(projectPath);
  await expect(
    page.getByRole("link", { name: "View analysis", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "View blueprint" })).toBeVisible({
    timeout: 30000,
  });
  await page.goto(`${projectPath}/analysis`);
  await expect(
    page.getByRole("heading", { name: "Automation sufficient", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "How work happens today" }),
  ).toBeVisible();
  await page.goto(`${projectPath}/solution`);
  await expect(
    page.getByRole("heading", { name: "A simpler invoice workflow" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "An independent second look" }),
  ).toBeVisible();
  await page.goto(`${projectPath}/blueprint`);
  await expect(
    page.getByRole("heading", { name: "Final recommendation" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Business value", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download", exact: true }).click();
  expect((await download).suggestedFilename()).toContain("blueprint.md");
  await page.screenshot({
    path: `test-results/blueprint-${testInfo.project.name}.png`,
    fullPage: true,
  });
  await page.goto("/dashboard");
  await page
    .getByRole("textbox", { name: "Search projects" })
    .fill(`Invoice pilot ${testInfo.project.name}`);
  await expect(
    page.getByRole("heading", {
      name: `Invoice pilot ${testInfo.project.name}`,
      exact: true,
    }),
  ).toBeVisible();
  await page.screenshot({
    path: `test-results/dashboard-${testInfo.project.name}.png`,
    fullPage: true,
  });
  await page.goto(projectPath);
  await page.getByRole("button", { name: /Run analysis|Run again/ }).click();
  await expect(
    page
      .getByRole("dialog")
      .getByRole("heading", { name: "Run a fresh analysis?" }),
  ).toBeVisible();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Cancel" })
    .click();
  // Destructive project actions now live behind the header's project menu.
  const openProjectMenu = () =>
    page.getByRole("button", { name: "Project actions" }).click();
  await openProjectMenu();
  await page
    .getByRole("button", { name: "Delete project", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Cancel" })
    .click();
  await openProjectMenu();
  await page
    .getByRole("button", { name: "Delete project", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Delete", exact: true })
    .click();
  await page.waitForURL("/dashboard");
  expect(errors).toEqual([]);
});

test("service errors stay user-facing and removed settings redirect", async ({
  page,
}) => {
  await page.route("**/api/projects", (route) =>
    route.fulfill({
      status: 503,
      json: {
        detail: "Add MONGODB_URI to backend/.env and restart the backend.",
      },
    }),
  );
  await page.goto("/dashboard");
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "temporarily unavailable",
  );
  await expect(page.getByText("MONGODB_URI")).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: /settings|connections/i }),
  ).toHaveCount(0);
  await page.goto("/settings");
  await page.waitForURL("/dashboard");
  await page.goto("/login");
  await expect(
    page.getByRole("heading", { name: "Welcome back." }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Continue locally" }),
  ).toHaveCount(0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});
