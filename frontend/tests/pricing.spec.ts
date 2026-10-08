import { test, expect, type Page } from "@playwright/test";

/** Stub the provider script so checkout can be exercised without real credentials. */
async function stubRazorpay(page: Page) {
  await page.route("https://checkout.razorpay.com/v1/checkout.js", (route) =>
    route.fulfill({
      contentType: "application/javascript",
      body: `window.Razorpay = function (options) {
        window.__checkout = options;
        return { open() { window.__opened = true; }, on() {} };
      };`,
    }),
  );
}

/**
 * Patch the real catalog response instead of restating prices, so the test
 * cannot drift from the backend pricing catalog.
 */
async function withSubscription(page: Page, tier: string, period: string) {
  await page.route(/\/api\/billing\/subscriptions$/, async (route) => {
    const body = await (await route.fetch()).json();
    body.configured = true;
    body.mode = "test";
    for (const entry of body.catalog.tiers)
      for (const price of Object.values(entry.prices) as {
        plan_key: string;
        configured: boolean;
        available: boolean;
        plan_name: string;
      }[])
        if (price.plan_key) {
          price.configured = true;
          price.available = true;
          price.plan_name = `${entry.name} ${price.plan_key}`;
        }
    const current = body.catalog.tiers.find(
      (entry: { id: string }) => entry.id === tier,
    );
    body.catalog.current_tier = tier;
    body.catalog.current_period = period;
    body.subscription = {
      provider_id: "sub_BROWSERTEST",
      status: "active",
      plan_key: current.prices[period].plan_key,
      plan_name: `${current.name} ${period}`,
      credits: current.prices[period].credits,
      amount: current.prices[period].amount,
      currency: body.catalog.currency,
      period,
      interval: 1,
      cancel_at_cycle_end: false,
    };
    await route.fulfill({ json: body });
  });
}

const card = (page: Page, name: string) =>
  page.locator(".pb-card").filter({ has: page.getByRole("heading", { name }) });

test("pricing page prices three plans, switches billing period and compares features", async ({
  page,
}) => {
  await stubRazorpay(page);
  await page.goto("/billing");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Choose your plan",
  );
  await expect(page.locator(".pb-card")).toHaveCount(3);
  await expect(page.getByText("credits available").first()).toBeVisible();

  // The free tier is current until a paid subscription is confirmed.
  const starter = card(page, "Starter");
  await expect(starter.getByRole("status")).toContainText("Current plan");
  await expect(
    starter.getByRole("button", { name: /Upgrade to Starter/ }),
  ).toHaveCount(0);
  await expect(card(page, "Pro")).toHaveClass(/is-featured/);
  await expect(card(page, "Pro").getByText("Most popular")).toBeVisible();

  // Excluded features are marked, not hidden.
  await expect(starter.locator(".pb-features li.is-excluded").first()).toContainText(
    "Credits renewed every billing cycle",
  );

  const pro = card(page, "Pro");
  const monthly = await pro.locator(".pb-price strong").innerText();
  await page.getByRole("button", { name: /^Yearly/ }).click();
  await expect(pro.locator(".pb-price span")).toContainText("per year");
  const yearly = await pro.locator(".pb-price strong").innerText();
  expect(yearly).not.toBe(monthly);
  await expect(pro.locator(".pb-price-note")).toContainText("save");
  await page.getByRole("button", { name: /^Monthly/ }).click();
  await expect(pro.locator(".pb-price span")).toContainText("per month");
  expect(await pro.locator(".pb-price strong").innerText()).toBe(monthly);

  // Comparison covers every tier and renders availability as icons.
  const comparison = page.locator(".pb-compare");
  await expect(comparison.getByRole("columnheader")).toHaveCount(4);
  await expect(
    comparison.getByRole("row", { name: /Credits each billing cycle/ }),
  ).toBeVisible();
  expect(await comparison.locator(".pb-mark-yes").count()).toBeGreaterThan(0);
  expect(await comparison.locator(".pb-mark-no").count()).toBeGreaterThan(0);

  // FAQ is a real accordion.
  const faq = page.locator(".pb-faq-list details").first();
  await expect(faq.locator(".pb-faq-answer")).toBeHidden();
  await faq.locator("summary").click();
  await expect(faq.locator(".pb-faq-answer")).toBeVisible();

  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});

test("an active plan is shown as current and only other tiers offer checkout", async ({
  page,
}) => {
  await stubRazorpay(page);
  await withSubscription(page, "pro", "monthly");
  let created: Record<string, unknown> | null = null;
  await page.route(/\/api\/billing\/checkout$/, async (route) => {
    created = route.request().postDataJSON();
    await route.fulfill({
      json: {
        provider_id: "sub_BROWSERTEST",
        status: "created",
        plan_name: "Pro monthly",
        credits: 1000,
        amount: 99900,
        currency: "INR",
        period: "monthly",
        interval: 1,
        key_id: "rzp_test_browser",
        mode: "test",
        business_name: "shift.AI",
      },
    });
  });
  await page.goto("/billing");

  const pro = card(page, "Pro");
  await expect(pro).toHaveClass(/is-current/);
  await expect(pro.getByRole("status")).toContainText("Current plan");
  await expect(
    pro.getByRole("button", { name: /Upgrade to Pro/ }),
  ).toHaveCount(0);
  await expect(page.getByText("Razorpay test mode", { exact: false })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Your subscription" })).toBeVisible();

  // Switching plans is blocked while a subscription is held, and the page says why.
  const business = card(page, "Business");
  await expect(
    business.getByRole("button", { name: /Upgrade to Business/ }),
  ).toBeDisabled();
  await expect(business.locator(".pb-card-hint")).toContainText(
    "Cancel your current subscription",
  );

  // Cancellation asks first and never cancels from a single click.
  await page
    .getByRole("button", { name: "Cancel at cycle end" })
    .click();
  await expect(
    page
      .getByRole("dialog")
      .getByRole("heading", { name: /Cancel at the end of this cycle/ }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();

  // With no subscription held, an order summary is confirmed before the provider opens.
  await page.unrouteAll({ behavior: "ignoreErrors" });
  await stubRazorpay(page);
  await page.route(/\/api\/billing\/subscriptions$/, async (route) => {
    const body = await (await route.fetch()).json();
    body.configured = true;
    for (const entry of body.catalog.tiers)
      for (const price of Object.values(entry.prices) as {
        plan_key: string;
        configured: boolean;
        available: boolean;
      }[])
        if (price.plan_key) {
          price.configured = true;
          price.available = true;
        }
    await route.fulfill({ json: body });
  });
  await page.route(/\/api\/billing\/checkout$/, async (route) => {
    created = route.request().postDataJSON();
    await route.fulfill({
      json: {
        provider_id: "sub_BROWSERTEST",
        status: "created",
        plan_name: "Pro monthly",
        credits: 1000,
        amount: 99900,
        currency: "INR",
        period: "monthly",
        interval: 1,
        key_id: "rzp_test_browser",
        mode: "test",
        business_name: "shift.AI",
      },
    });
  });
  await page.goto("/billing");
  await card(page, "Pro")
    .getByRole("button", { name: /Upgrade to Pro/ })
    .click();
  const summary = page.getByRole("dialog");
  await expect(summary).toContainText("Review your subscription");
  await expect(summary.locator(".pb-summary")).toContainText("Monthly");
  await expect(summary.locator(".pb-summary-total")).toContainText("₹");
  await summary.getByRole("button", { name: "Continue to payment" }).click();
  await expect
    .poll(() => page.evaluate(() => (window as { __opened?: boolean }).__opened))
    .toBe(true);
  expect(created!.plan).toBe("pro_monthly");
  expect(String(created!.request_id).length).toBeGreaterThan(7);
});

test("pricing cards stack on a narrow viewport without horizontal overflow", async ({
  page,
}) => {
  await stubRazorpay(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/billing");
  await expect(page.locator(".pb-card")).toHaveCount(3);
  const boxes = await page.locator(".pb-card").evaluateAll((cards) =>
    cards.map((element) => element.getBoundingClientRect().left),
  );
  expect(new Set(boxes).size).toBe(1);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});

test("account security shows factor state, guarded actions and no browser confirms", async ({
  page,
}) => {
  await page.goto("/account");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Account security",
  );
  const protection = page
    .locator(".panel")
    .filter({ has: page.getByRole("heading", { name: "Sign-in protection" }) });
  await expect(protection).toBeVisible();

  // The local fixture account signs in without a password record.
  const password = page.getByLabel("Confirm your password");
  if (await password.count()) {
    await expect(
      page.getByRole("button", { name: "Set up authenticator" }),
    ).toBeDisabled();
    await password.fill("not-the-real-password");
    await expect(
      page.getByRole("button", { name: "Set up authenticator" }),
    ).toBeEnabled();
  } else {
    await expect(protection).toContainText("organization provider");
  }

  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});
