import { test, expect } from "@playwright/test";

test("sign-up, team administration, seven deliverables, revisions, approval, and exports", async ({
  page,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const suffix = `${testInfo.project.name}-${Date.now()}`;
  const email = `test-${suffix}@example.com`;
  await page.goto("/signup");
  await page.getByLabel("Full name").fill("Pilot Reviewer");
  await page.getByLabel("Email address").fill(email);
  await page
    .getByLabel("Password", { exact: true })
    .fill("browser-test-password-123");
  await page.getByLabel("Confirm password").fill("does-not-match");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(page.locator(".auth-error")).toContainText("matching passwords");
  await page.getByLabel("Confirm password").fill("browser-test-password-123");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await page.waitForURL("/dashboard");
  await page.reload();
  await page.goto("/workspaces");
  await page
    .getByLabel("Workspace name", { exact: true })
    .fill(`Pilot ${suffix}`);
  await page
    .getByLabel("Organization", { exact: true })
    .fill("Test organization");
  await page
    .getByRole("button", { name: "Create workspace", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Workspace health" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Microsoft Planner connection" }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Create team project", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Simplify invoice processing" })
    .click();
  await page.getByRole("button", { name: "Start discovery" }).click();
  await page.waitForURL(/\/project\/[a-f0-9]{24}$/);
  const projectPath = new URL(page.url()).pathname;
  const pid = projectPath.split("/").pop();
  await page.getByRole("button", { name: "Begin the conversation" }).click();
  await expect(page.locator(".ready-banner")).toBeVisible();
  // Advance the same authenticated account through the real API and graph with a test provider.
  const analysis = await page.request.post(
    `http://localhost:8011/api/projects/${pid}/analysis/run`,
    { headers: { Origin: "http://localhost:3011" } },
  );
  expect(analysis.status()).toBe(202);
  await page.goto(projectPath + "/deliverables");
  await page
    .getByRole("button", { name: "Generate complete pack", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Generate pack", exact: true })
    .click();
  await expect(page.locator(".deliverable-tabs small")).toHaveCount(7);
  await expect(
    page.getByRole("heading", { name: "Invoice transformation design" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Edit draft", exact: true }).click();
  await page
    .getByLabel("Deliverable Summary", { exact: true })
    .fill("Revised after stakeholder feedback.");
  if (testInfo.project.name === "mobile")
    await page.getByRole("button", { name: "Toggle navigation" }).click();
  await page
    .locator(".sidebar")
    .getByRole("link", { name: "Discovery", exact: true })
    .click();
  await expect(
    page
      .getByRole("dialog")
      .getByRole("heading", { name: "Leave unsaved deliverable?" }),
  ).toBeVisible();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Cancel", exact: true })
    .click();
  if (testInfo.project.name === "mobile")
    await page.getByRole("button", { name: "Toggle navigation" }).click();
  await page.getByLabel("Revision note").fill("Stakeholder workshop");
  await page
    .getByRole("button", { name: "Save new version", exact: true })
    .click();
  await expect(
    page.getByText("Revised after stakeholder feedback.", { exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Review note")
    .fill("Validated workflow and pilot assumptions.");
  await page.getByRole("button", { name: "Approved", exact: true }).click();
  await expect(
    page.getByText("Approved · Pilot Reviewer", { exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Comment or feedback")
    .fill("Remember to validate accounting access.");
  await page.getByRole("button", { name: "Post comment" }).click();
  await expect(page.locator(".team-comment")).toContainText(
    "Remember to validate accounting access.",
  );
  await page.getByRole("button", { name: "Version history" }).click();
  await expect(page.locator(".version-list button")).toHaveCount(2);
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "DOCX", exact: true }).click();
  expect((await download).suggestedFilename()).toMatch(/\.docx$/);
  await page
    .locator(".deliverable-tabs button")
    .filter({ hasText: "Architecture design" })
    .click();
  await expect(page.locator(".diagram-figure")).toHaveCount(6);
  await page
    .locator(".deliverable-tabs button")
    .filter({ hasText: "Experience design" })
    .click();
  await expect(page.locator(".wireframe")).toHaveCount(3);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  expect(await page.evaluate(() => innerWidth)).toBe(
    page.viewportSize()!.width,
  );
  await page.screenshot({
    path: `test-results/studio-${testInfo.project.name}.png`,
    fullPage: true,
  });
  await page.goto("/transformation");
  await expect(
    page.getByRole("heading", { name: "Transformation dashboard" }),
  ).toBeVisible();
  await page.getByLabel("Interface language").selectOption("hi");
  await expect(page.locator("html")).toHaveAttribute("lang", "hi");
  expect(errors).toEqual([]);
});
