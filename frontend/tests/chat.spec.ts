import { test, expect } from "@playwright/test";

/** Model and effort selection in the composer, plus the conversation layout fixes. */
test("model and effort selection persists and the conversation layout is unclipped", async ({
  page,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/project/new");
  await page
    .getByLabel("Project name")
    .fill(`Charger visibility ${testInfo.project.name}`);
  await page
    .getByLabel(/business problem|challenge/i)
    .fill(
      "Drivers cannot tell which charging points are free during peak hours, so they queue.",
    );
  await page.getByRole("button", { name: "Start discovery" }).click();
  await page.waitForURL(/\/project\/[a-f0-9]{24}$/);

  const trigger = page.getByRole("button", { name: /Model|Gemini/ }).first();
  await expect(trigger).toBeVisible();

  // The picker lists selectable models and marks the current one.
  await trigger.click();
  const menu = page.getByRole("menu", { name: "Model and effort" });
  await expect(menu).toBeVisible();
  const options = menu.getByRole("menuitemradio");
  expect(await options.count()).toBeGreaterThan(1);

  // Switch to a different model and confirm it is saved on the project.
  const second = options.nth(1);
  const chosen = (await second.locator("strong").innerText()).trim();
  await second.click();
  await expect(menu).toBeHidden();
  await expect(trigger).toContainText(chosen);
  await page.reload();
  await expect(
    page.getByRole("button", { name: /Model|Gemini/ }).first(),
  ).toContainText(chosen);

  // Effort lives behind its own step, like the model list.
  await page.getByRole("button", { name: /Model|Gemini/ }).first().click();
  await page.getByRole("button", { name: /Effort/ }).click();
  const efforts = page
    .getByRole("menu", { name: "Model and effort" })
    .getByRole("menuitemradio");
  await expect(efforts.first()).toBeVisible();
  expect(await efforts.count()).toBe(4);
  await efforts.filter({ hasText: "Instant" }).click();
  await expect(
    page.getByRole("button", { name: /Model|Gemini/ }).first(),
  ).toContainText("Instant");
  await page.reload();
  await expect(
    page.getByRole("button", { name: /Model|Gemini/ }).first(),
  ).toContainText("Instant");

  // Escape closes the menu without changing the selection.
  const reopened = page.getByRole("button", { name: /Model|Gemini/ }).first();
  await reopened.click();
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("menu", { name: "Model and effort" }),
  ).toBeHidden();

  await page.screenshot({
    path: `test-results/model-picker-${testInfo.project.name}.png`,
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("the sidebar project name is fully visible and the message area is tall", async ({
  page,
  isMobile,
}, testInfo) => {
  test.skip(!!isMobile, "The persistent sidebar is desktop-only.");
  await page.goto("/project/new");
  await page
    .getByLabel("Project name")
    .fill(`Layout check ${testInfo.project.name}`);
  await page
    .getByLabel(/business problem|challenge/i)
    .fill(
      "Peak hour queueing at charging points because availability is not visible to drivers.",
    );
  await page.getByRole("button", { name: "Start discovery" }).click();
  await page.waitForURL(/\/project\/[a-f0-9]{24}$/);

  // The section label and the project name must not overlap.
  const label = page.locator(".sidebar .nav-label").first();
  const name = page.locator(".sidebar .sidebar-project").first();
  const labelBox = await label.boundingBox();
  const nameBox = await name.boundingBox();
  expect(labelBox).not.toBeNull();
  expect(nameBox).not.toBeNull();
  expect(nameBox!.y).toBeGreaterThanOrEqual(labelBox!.y + labelBox!.height - 1);

  // The name is not visually cut off: its box fits the text it renders.
  const clipped = await name.evaluate(
    (el) => el.scrollHeight > el.clientHeight + 1,
  );
  expect(clipped).toBeFalsy();

  // The conversation area uses the available height instead of a small fixed cap.
  const messages = await page.locator(".messages").boundingBox();
  expect(messages!.height).toBeGreaterThan(320);

  await page.screenshot({
    path: `test-results/discovery-layout-${testInfo.project.name}.png`,
    fullPage: true,
  });
});
