import { test, expect, type Page } from "@playwright/test";

/** Browser coverage for the conversational Discovery workspace. */

async function startProject(page: Page, name: string, problem: string) {
  await page.goto("/project/new");
  await page.getByLabel("Project name").fill(name);
  await page.getByLabel(/business problem|challenge/i).fill(problem);
  await page.getByRole("button", { name: "Start discovery" }).click();
  await page.waitForURL(/\/project\/[a-f0-9]{24}$/);
}

const modelChip = (page: Page) => page.getByRole("button", { name: /^Model:/ });
const modeChip = (page: Page) =>
  page.getByRole("button", { name: /^Response mode:/ });

test("assistant replies and activity keep the brand mark with fading status text", async ({ page }) => {
  await startProject(page, "Live activity", "Staff copy invoice records between email and spreadsheets every day.");
  const pid = page.url().split("/").at(-1);
  let status = "DISCOVERY";
  let pending = true;
  let release!: () => void;
  const providerWait = new Promise<void>((resolve) => { release = resolve; });
  await page.route(`**/api/projects/${pid}`, async (route) => {
    const response = await route.fetch();
    await route.fulfill({ response, json: { ...await response.json(), ...(pending ? { busy: true, status } : {}) } });
  });
  await page.route(`**/api/projects/${pid}/chat`, async (route) => {
    await providerWait;
    await route.continue();
  });
  try {
    await page.getByLabel("Your message").fill("Can you help us simplify this process?");
    await page.getByLabel("Your message").press("Enter");
    const activity = page.locator(".dx-typing");
    await expect(activity).toContainText("Thinking");
    await expect(activity.locator("img")).toBeVisible();
    await expect(activity.locator("strong, svg, .dx-dots")).toHaveCount(0);
    await expect(activity).not.toContainText("shift.AI");
    for (const [stage, label] of [
      ["SYSTEM_ANALYSIS", "Analyzing your workflow"],
      ["AI_NECESSITY", "Evaluating whether AI is needed"],
      ["SOLUTION_GENERATION", "Developing your solution"],
      ["RED_TEAM_REVIEW", "Reviewing risks and assumptions"],
      ["BUSINESS_VALUE", "Assessing business value"],
    ]) {
      status = stage;
      await expect(activity).toContainText(label);
    }
    await page.screenshot({ path: "test-results/brand-activity-desktop.png" });
    pending = false;
    release();
    const assistant = page.getByRole("article", { name: "Assistant response" }).first();
    await expect(assistant).toBeVisible();
    await expect(activity).toBeHidden();
    const header = assistant.locator(".dx-msg-head");
    await expect(header.locator("img")).toBeVisible();
    await expect(header.locator("strong, svg, .dx-msg-stage")).toHaveCount(0);
    await expect(header).not.toContainText("shift.AI");
    const markHeight = await header.locator("img").evaluate(el => el.getBoundingClientRect().height);
    expect(markHeight).toBeLessThanOrEqual(22);
    await page.screenshot({ path: "test-results/brand-response-desktop.png" });
  } finally { pending = false; release(); }
});

for (const stopWith of ["button", "Escape"] as const) {
  test(`submission moves into chat immediately and ${stopWith} cancels the server response`, async ({ page }) => {
    await startProject(page, `Cancel with ${stopWith}`, "The team copies invoice records between two systems every day.");
    const input = page.getByRole("textbox", { name: "Your message" });
    const content = `Cancellation test: hello using ${stopWith}`;
    await input.fill(content);
    await input.press("Enter");
    await expect(input).toHaveValue("", { timeout: 1000 });
    await expect(page.locator(".dx-msg-user").filter({ hasText: content })).toBeVisible({ timeout: 1000 });
    await expect(page.getByRole("button", { name: "Stop response" })).toBeEnabled();
    // Wait for persistence, so this exercises cancelling an in-flight provider call.
    const pid = page.url().split("/").at(-1);
    await expect.poll(async () => {
      const response = await page.request.get(`http://localhost:8011/api/projects/${pid}/messages`);
      return (await response.json()).some((m: { content: string }) => m.content === content);
    }).toBeTruthy();
    if (stopWith === "Escape") await page.keyboard.press("Escape");
    else await page.getByRole("button", { name: "Stop response" }).click();
    await expect(page.getByText("Response stopped. You can continue whenever you’re ready.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Stop response" })).toBeHidden();
    // Allow the detached provider response to return: it must not enter the chat.
    await page.waitForTimeout(3200);
    await page.reload();
    await expect(page.locator(".dx-msg-assistant")).toHaveCount(0);
    await expect(page.locator(".dx-msg-user").filter({ hasText: content })).toHaveCount(1);
    await input.fill("Please continue with the invoice workflow.");
    await input.press("Enter");
    await expect(page.locator(".dx-msg-assistant").first()).toBeVisible();
  });
}

test("quota errors stay specific and retry sends the original prompt once", async ({ page }) => {
  await startProject(page, "Quota recovery", "Our team retypes customer records into two separate systems.");
  let calls = 0;
  await page.route(/\/api\/projects\/[^/]+\/chat$/, async (route) => {
    calls++;
    if (calls === 1) await route.fulfill({ status: 429, json: { code: "rate_limited", detail: "The selected model has reached its available API quota. Retry shortly." } });
    else await route.continue();
  });
  const model = await modelChip(page).innerText();
  const content = "Records are copied manually every morning.";
  await page.getByLabel("Your message").fill(content);
  await page.getByLabel("Your message").press("Enter");
  await expect(page.locator(".dx-alert")).toContainText("available API quota");
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await expect(page.locator(".dx-msg-assistant").first()).toBeVisible();
  await expect(page.locator(".dx-msg-user").filter({ hasText: content })).toHaveCount(1);
  await expect(modelChip(page)).toHaveText(model);
  expect(calls).toBe(2);
});

test("usage displays known availability and cooldown without invented quotas", async ({ page }) => {
  await page.route(/\/api\/projects\/[^/]+\/usage$/, (route) => route.fulfill({ json: {
    configured_connections: 9, available_connections: 0, status: "rate_limited", retry_at: new Date(Date.now() + 120000).toISOString(),
    remaining_requests: null, request_limit: null, reset_at: null, quota_note: "Exact remaining requests and quota resets are not reported by this API.",
  } }));
  await startProject(page, "Usage display", "Our team needs a faster process for matching customer records.");
  const usage = page.getByRole("button", { name: "Usage and limits" });
  await expect(usage).toContainText("Retry in");
  await usage.click();
  const panel = page.getByRole("menu", { name: "Usage and limits" });
  await expect(panel).toContainText("0 / 9");
  await expect(panel).toContainText("Not reported");
  await expect(panel).toContainText("not a guaranteed quota refill");
  await expect(panel.getByRole("link", { name: /View provider usage/ })).toHaveAttribute("href", "https://aistudio.google.com/usage?tab=rate-limit");
});

/** Minimal stand-in for the browser speech engine, controlled from the test. */
function installSpeech(page: Page) {
  return page.addInitScript(() => {
    const scope = window as unknown as Record<string, unknown>;
    class FakeRecognition {
      lang = "";
      continuous = false;
      interimResults = false;
      maxAlternatives = 1;
      onstart: (() => void) | null = null;
      onresult: ((event: unknown) => void) | null = null;
      onerror: ((event: { error: string }) => void) | null = null;
      onend: (() => void) | null = null;
      start() {
        scope.__voice = this;
        this.onstart?.();
      }
      stop() {
        this.onend?.();
      }
      abort() {}
    }
    scope.SpeechRecognition = FakeRecognition;
    scope.webkitSpeechRecognition = FakeRecognition;
  });
}

type Engine = {
  onresult?: (event: unknown) => void;
  onerror?: (event: { error: string }) => void;
};

const dictate = (page: Page, transcript: string, final = true) =>
  page.evaluate(
    ([text, isFinal]) => {
      const engine = (window as unknown as Record<string, Engine>).__voice;
      engine?.onresult?.({
        resultIndex: 0,
        results: {
          length: 1,
          0: {
            isFinal: isFinal === "true",
            length: 1,
            0: { transcript: text },
          },
        },
      });
    },
    [transcript, String(final)],
  );

test("the composer keeps model and response mode selection", async ({
  page,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await startProject(
    page,
    `Charger visibility ${testInfo.project.name}`,
    "Drivers cannot tell which charging points are free during peak hours, so they queue.",
  );

  // Model lives in its own popover, listing what the configured keys can use.
  await expect(modelChip(page)).toBeVisible();
  await modelChip(page).click();
  const models = page.getByRole("menu", { name: "Model" });
  await expect(models).toBeVisible();
  const box = await models.boundingBox();
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.y).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(page.viewportSize()!.width);
  expect(box!.y + box!.height).toBeLessThanOrEqual(page.viewportSize()!.height);
  const options = models.getByRole("menuitemradio");
  expect(await options.count()).toBeGreaterThan(1);
  const chosen = (await options.nth(1).locator("strong").innerText()).trim();
  await options.nth(1).click();
  await expect(models).toBeHidden();
  await expect(modelChip(page)).toContainText(chosen);
  await page.reload();
  await expect(modelChip(page)).toContainText(chosen);

  // Response mode is the project's reasoning effort, saved the same way.
  await modeChip(page).click();
  const modes = page.getByRole("menu", { name: "Response mode" });
  expect(await modes.getByRole("menuitemradio").count()).toBe(4);
  await modes.getByRole("menuitemradio").filter({ hasText: "Instant" }).click();
  await expect(modeChip(page)).toContainText("Instant");
  await page.reload();
  await expect(modeChip(page)).toContainText("Instant");

  // Keyboard: arrow opens, Escape closes and restores focus.
  await modeChip(page).press("ArrowDown");
  await expect(page.getByRole("menu", { name: "Response mode" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("menu", { name: "Response mode" })).toBeHidden();
  await expect(modeChip(page)).toBeFocused();

  await page.screenshot({
    path: `test-results/composer-${testInfo.project.name}.png`,
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("the conversation scrolls inside the workspace while the composer stays put", async ({
  page,
}, testInfo) => {
  // A long saved transcript tests layout independently of provider latency.
  await page.route(/\/api\/projects\/[^/]+\/messages$/, async (route) => {
    const original = await route.fetch();
    const messages = await original.json();
    await route.fulfill({
      response: original,
      json: [
        ...messages,
        ...Array.from({ length: 24 }, (_, i) => ({
          id: `layout-message-${i}`,
          role: i % 2 ? "user" : "assistant",
          created_at: new Date().toISOString(),
          content: `Workflow detail ${i + 1}: reception enters the registration information in two systems, creating delays during the morning queue.`,
        })),
      ],
    });
  });
  await startProject(
    page,
    `Scroll check ${testInfo.project.name}`,
    "Patient registration queues grow because records are entered twice into separate systems.",
  );
  await expect(page.locator(".dx-msg")).toHaveCount(25);

  // The page itself never scrolls: the stream owns its scroll region.
  expect(
    await page.evaluate(
      () => document.documentElement.scrollHeight <= innerHeight + 2,
    ),
  ).toBeTruthy();
  const stream = page.locator(".dx-stream");
  await expect(stream).toBeVisible();
  const landed = await stream.evaluate((el) => el.scrollTop);
  expect(landed).toBeGreaterThan(50);

  // Wheel over the conversation moves the transcript, not the window.
  const area = await stream.boundingBox();
  await page.mouse.move(area!.x + area!.width / 2, area!.y + area!.height / 2);
  await page.mouse.wheel(0, -400);
  await expect
    .poll(() => stream.evaluate((el) => el.scrollTop))
    .toBeLessThan(landed - 100);
  expect(await page.evaluate(() => scrollY)).toBe(0);

  // The composer and header remain on screen the whole time.
  await expect(
    page.getByRole("textbox", { name: "Your message" }),
  ).toBeVisible();
  await expect(page.locator(".dx-header")).toBeVisible();
  const composer = await page.locator(".dx-composer").boundingBox();
  expect(composer!.y + composer!.height).toBeLessThanOrEqual(
    page.viewportSize()!.height + 1,
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: `test-results/conversation-${testInfo.project.name}.png`,
  });
});

test("the sidebar lists conversations, filters them, and collapses", async ({
  page,
  isMobile,
}, testInfo) => {
  const name = `Charging history ${testInfo.project.name}`;
  await startProject(
    page,
    name,
    "Drivers queue because charger availability is invisible during peak hours.",
  );
  if (isMobile)
    await page.getByRole("button", { name: "Toggle navigation" }).click();
  const sidebar = page.locator(".sidebar");
  await expect(
    sidebar.getByRole("link", { name: "New conversation" }),
  ).toBeVisible();
  const active = sidebar.locator(".dx-chat-item.is-active");
  await expect(active).toHaveCount(1);
  await expect(active).toContainText(name);
  // Project tools stay reachable next to the conversation list.
  await expect(
    sidebar.getByRole("link", { name: "Discovery", exact: true }),
  ).toBeVisible();

  // Search filters the conversations already loaded in the client.
  await sidebar.getByRole("button", { name: /Search conversations/ }).click();
  const field = sidebar.getByRole("textbox", { name: "Search conversations" });
  await field.fill("zzz-no-such-project");
  await expect(
    sidebar.getByText("No conversation matches that search."),
  ).toBeVisible();
  await field.fill(name);
  await expect(sidebar.locator(".dx-chat-item")).toHaveCount(1);
  await field.press("Escape");

  if (isMobile) {
    await page.keyboard.press("Escape");
    await expect(sidebar).not.toHaveClass(/is-open/);
    return;
  }

  // Desktop keeps a collapsible rail, remembered across reloads.
  const width = async () => (await sidebar.boundingBox())!.width;
  expect(await width()).toBeGreaterThan(200);
  await page.getByRole("button", { name: "Collapse sidebar" }).click();
  await expect.poll(width).toBeLessThan(90);
  await expect(
    sidebar.getByRole("link", { name: "New conversation" }),
  ).toBeVisible();
  await page.reload();
  await expect.poll(width).toBeLessThan(90);
  await page.getByRole("button", { name: "Expand sidebar" }).click();
  await expect.poll(width).toBeGreaterThan(200);
  await page.screenshot({
    path: `test-results/sidebar-${testInfo.project.name}.png`,
    fullPage: true,
  });
});

test("context opens in a panel with the saved discovery scores", async ({
  page,
  isMobile,
}, testInfo) => {
  await startProject(
    page,
    `Evidence panel ${testInfo.project.name}`,
    "Invoices are retyped into two systems, so month-end reporting is late.",
  );
  const trigger = page
    .locator(".dx-header")
    .getByRole("button", { name: /Context/ });
  await expect(trigger).toBeVisible();
  await trigger.click();
  const panel = page.locator(".dx-context");
  await expect(panel).toBeVisible();
  await expect(
    panel.getByRole("heading", { name: "Understanding" }),
  ).toBeVisible();
  await expect(panel.getByText("Workflow", { exact: true })).toBeVisible();
  await expect(panel.locator(".dx-score")).toHaveCount(10);
  await expect(panel).toContainText("Supporting documents");
  await page.screenshot({
    path: `test-results/context-${testInfo.project.name}.png`,
  });
  if (isMobile) {
    // On narrow screens the panel is a drawer, so Escape must dismiss it.
    await page.keyboard.press("Escape");
  } else {
    await panel.getByRole("button", { name: "Close context panel" }).click();
  }
  await expect(panel).toBeHidden();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});

test("voice input dictates into the composer without sending", async ({
  page,
}, testInfo) => {
  let chatRequests = 0;
  page.on("request", (request) => {
    if (request.url().includes("/chat") && request.method() === "POST")
      chatRequests++;
  });
  await installSpeech(page);
  await startProject(
    page,
    `Voice input ${testInfo.project.name}`,
    "Support agents copy answers between three tools for every ticket.",
  );
  const field = page.getByRole("textbox", { name: "Your message" });
  const mic = page.getByRole("button", { name: "Start voice input" });
  await expect(mic).toBeVisible();
  await mic.click();
  const stop = page.getByRole("button", { name: "Stop voice input" });
  await expect(stop).toBeVisible();
  await expect(page.getByText("Listening…")).toBeVisible();
  await dictate(page, "agents copy answers between three tools", false);
  await expect(field).toHaveValue("agents copy answers between three tools");
  await stop.click();
  await expect(mic).toBeVisible();

  // The transcript is editable and nothing is sent automatically.
  await field.click();
  await page.keyboard.press("Control+End");
  await page.keyboard.type(" for every ticket");
  await expect(field).toHaveValue(
    "agents copy answers between three tools for every ticket",
  );
  expect(chatRequests).toBe(0);

  // A blocked microphone explains itself instead of failing silently.
  await mic.click();
  await page.evaluate(() => {
    const engine = (window as unknown as Record<string, Engine>).__voice;
    engine?.onerror?.({ error: "not-allowed" });
  });
  await expect(page.locator(".dx-composer-alert")).toContainText(
    "Microphone access was blocked",
  );
  await page.screenshot({
    path: `test-results/voice-${testInfo.project.name}.png`,
  });
});

test("browsers without speech recognition disable voice input gracefully", async ({
  page,
}, testInfo) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, "SpeechRecognition", {
      value: undefined,
      configurable: true,
    });
    Object.defineProperty(window, "webkitSpeechRecognition", {
      value: undefined,
      configurable: true,
    });
  });
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await startProject(
    page,
    `No speech ${testInfo.project.name}`,
    "Warehouse pickers walk the same aisle twice for most orders.",
  );
  const unavailable = page.getByRole("button", {
    name: "Voice input is unavailable",
  });
  await expect(unavailable).toBeVisible();
  await expect(unavailable).toBeDisabled();
  await expect(unavailable).toHaveAttribute(
    "title",
    "Speech input isn’t supported in this browser.",
  );
  expect(errors).toEqual([]);
});

test("the conversation reaches every workflow stage and keeps retry available", async ({
  page,
  isMobile,
}, testInfo) => {
  await startProject(
    page,
    `Workflow stages ${testInfo.project.name}`,
    "Reception enters patient details twice, so the morning queue grows.",
  );
  // The compact stage indicator replaces the full-width tracker. Narrow screens
  // give the space to the project name and navigate stages from the drawer.
  if (!isMobile) {
    await page.getByRole("button", { name: /^Stage 1 of 5/ }).click();
    const workflow = page.getByRole("menu", { name: "Workflow stages" });
    await expect(workflow.getByRole("link")).toHaveCount(5);
    await workflow.getByRole("link", { name: "Blueprint" }).click();
    await page.waitForURL(/\/blueprint$/);
    await page.goBack();
  } else {
    await page.getByRole("button", { name: "Toggle navigation" }).click();
    await page
      .locator(".sidebar")
      .getByRole("link", { name: "Blueprint", exact: true })
      .click();
    await page.waitForURL(/\/blueprint$/);
    await page.goBack();
  }

  await page.getByRole("button", { name: "Begin the conversation" }).click();
  await expect(page.locator(".ready-banner")).toBeVisible();
  const field = page.getByRole("textbox", { name: "Your message" });
  await field.fill(
    "We review each invoice by hand, then retype it into the ledger.",
  );
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(field).toHaveValue("");
  const lastUser = page.locator(".dx-msg-user").last();
  await expect(lastUser).toContainText("We review each invoice by hand");

  // Message actions replace the large links that used to sit under the composer.
  await lastUser.hover();
  await expect(
    lastUser.getByRole("button", { name: "Copy message" }),
  ).toBeVisible();
  const retry = lastUser.getByRole("button", {
    name: "Retry response to your saved answer",
  });
  // Retry only applies while the newest message is still the user's answer.
  if (await retry.count()) await expect(retry).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: `test-results/stages-${testInfo.project.name}.png`,
  });
});
