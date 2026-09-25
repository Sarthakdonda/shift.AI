import { test, expect } from "@playwright/test";

test("application approval, generation failure refund, history and source export", async ({ page }) => {
  const headers = { Origin: "http://localhost:3011" };
  const endpoint = "http://localhost:8011/api";
  const response = await page.request.post(endpoint + "/projects", { headers, data: { name: "Builder acceptance", initial_problem: "We manually copy invoice fields from email to spreadsheets and need to reduce duplicate entry." } });
  expect(response.status()).toBe(201);
  const project = await response.json();
  const base = `/projects/${project.id}`;
  try {
    const chat = await page.request.post(endpoint + base + "/discovery/next", { headers });
    expect(chat.ok(), await chat.text()).toBeTruthy();
    // Discovery automatically starts analysis once the evidence is sufficient.
    await expect.poll(async () => (await (await page.request.get(endpoint + base)).json()).status, { timeout: 30000 }).toBe("BLUEPRINT_READY");
    // The invoice fixture intentionally leaves an integration risk open. Exercise
    // the normal review gate and explicitly accept that synthetic risk first.
    const blocked = await page.request.post(endpoint + base + "/application/plan", { headers, data: { base_version: 0, instructions: "" } });
    expect(blocked.status()).toBe(409);
    const blueprint = await (await page.request.get(endpoint + base + "/blueprint")).json();
    const finding = blueprint.content.review_ledger.find((item: { severity: string }) => item.severity === "HIGH");
    expect(finding).toBeTruthy();
    const review = await page.request.post(endpoint + base + "/red-team/revise", { headers, data: {
      version: blueprint.version, action: "accept_risk", finding_id: finding.id,
      response: "For this isolated acceptance test, accept the accounting integration risk. No external accounting service will be connected or deployed.",
    } });
    expect(review.ok(), await review.text()).toBeTruthy();
    await expect.poll(async () => (await (await page.request.get(endpoint + base)).json()).busy, { timeout: 30000 }).toBeFalsy();
    await page.goto(`/project/${project.id}/application`);
    await expect(page.getByRole("heading", { name: "Application studio" })).toBeVisible();
    await page.getByRole("button", { name: "Create application specification", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Recruitment workspace", exact: true })).toBeVisible();
    const generate = page.getByRole("button", { name: "Generate & validate", exact: false });
    await expect(generate).toBeDisabled();
    await page.getByLabel(/I reviewed this blueprint version/).check();
    await page.getByRole("button", { name: "Approve blueprint & application scope", exact: true }).click();
    await expect(generate).toBeEnabled();
    await generate.click();
    await expect(page.getByText("validation required", { exact: true })).toBeVisible();
    await expect(page.getByText(/Docker unavailable in the isolated browser fixture/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Start 15-minute preview", exact: true })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Deploy to Render", exact: true })).toBeDisabled();
    const balance = await (await page.request.get(endpoint + "/billing")).json();
    expect(balance.account.balance).toBe(100);
    const downloadEvent = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download source ZIP", exact: true }).click();
    expect((await downloadEvent).suggestedFilename()).toMatch(/application-.*\.zip/);
    await page.getByLabel("Application requirements or changes").fill("Change the dashboard theme and preserve existing modules.");
    await page.getByRole("button", { name: "Draft changes", exact: true }).click();
    await expect(page.getByLabel("Application version")).toHaveValue("2");
    await expect(generate).toBeDisabled();
    const overflows = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    expect(overflows).toBeFalsy();
  } finally {
    await page.request.delete(endpoint + base, { headers });
  }
});
