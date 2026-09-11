import { test, expect } from "@playwright/test";
import path from "node:path";

test("complete scenario report, Word download and readable PDF", async ({
  page,
  request,
}, testInfo) => {
  const api = process.env.SHIFT_REPORT_TEST_API || "http://localhost:8011/api";
  const response = await request.post(`${api}/projects`, {
    data: {
      name: "Synthetic invoice pilot — report example",
      initial_problem:
        "Operations staff retype structured invoice rows; we need validated imports with human review.",
      industry: "Business operations",
    },
  });
  expect(response.ok()).toBeTruthy();
  const { id } = await response.json();
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  try {
    const start = await request.post(`${api}/projects/${id}/discovery/next`);
    expect(start.ok()).toBeTruthy();
    await page.goto(`/project/${id}/blueprint`);
    await expect(page.locator(".implementation-chapter")).toHaveCount(34);
    await expect(page.locator("#report-options")).toContainText(
      "Balanced import workflow",
    );
    await expect(page.locator("#report-matrix")).toContainText("88");
    await expect(page.locator("#report-data_model")).toContainText(
      "invoice_id",
    );
    await expect(page.locator("#report-journeys .report-screen")).toHaveCount(
      3,
    );
    await expect(page.locator(".implementation-report")).not.toContainText(
      /hospital|HIPAA|FHIR|patient/i,
    );
    await expect(page.locator(".blueprint-metadata")).toContainText(
      "Version 1",
    );
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBeTruthy();
    const download = page.waitForEvent("download");
    await page.getByRole("link", { name: "Word", exact: true }).click();
    expect((await download).suggestedFilename()).toBe(
      "shift-ai-deliverable-v1.docx",
    );
    await page
      .locator("#report-matrix")
      .screenshot({ path: testInfo.outputPath("matrix.png") });
    await page.emulateMedia({ media: "print" });
    await page.evaluate(() => document.fonts.ready);
    // Test at A4 printable width, independent of mobile emulation.
    await page.setViewportSize({ width: 680, height: 1000 });
    const overflows = await page
      .locator(
        ".implementation-report td, .report-flow-node, .report-screen-control",
      )
      .evaluateAll((elements) =>
        elements
          .filter((e) => e.scrollWidth > e.clientWidth + 2)
          .map((e) => e.textContent?.slice(0, 80)),
      );
    expect(overflows).toEqual([]);
    if (testInfo.project.name === "desktop") {
      await page.pdf({
        path: path.resolve("../tmp/report-review/shiftAI-synthetic-report.pdf"),
        format: "A4",
        printBackground: true,
        preferCSSPageSize: true,
        displayHeaderFooter: true,
        headerTemplate: "<div></div>",
        footerTemplate:
          '<div style="font-size:9px;width:100%;text-align:center;color:#687583">shift.AI · Synthetic verification example · <span class="pageNumber"></span> / <span class="totalPages"></span></div>',
      });
    }
    expect(errors).toEqual([]);
  } finally {
    await request.delete(`${api}/projects/${id}`);
  }
});
