import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  timeout: 90000,
  expect: { timeout: 15000 },
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://localhost:3011",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "desktop",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 1000 },
      },
    },
    {
      name: "mobile",
      use: { ...devices["iPhone 13"], defaultBrowserType: "chromium" },
    },
  ],
  webServer: [
    {
      command: "npm run dev -- --port 3011",
      env: {
        SHIFT_TEST_BUILD_DIR: ".next-e2e",
        NEXT_PUBLIC_API_BASE_URL: "http://localhost:8011",
      },
      url: "http://localhost:3011",
      reuseExistingServer: false,
      timeout: 120000,
    },
    {
      command:
        process.platform === "win32"
          ? "..\\backend\\.venv\\Scripts\\python.exe -m uvicorn tests.e2e_server:app --app-dir ../backend --port 8011"
          : "../backend/.venv/bin/python -m uvicorn tests.e2e_server:app --app-dir ../backend --port 8011",
      url: "http://localhost:8011/api/health",
      env: {
        CORS_ORIGINS: "http://localhost:3011",
        SESSION_SECRET: "isolated-browser-test-session-secret-only",
      },
      reuseExistingServer: false,
      timeout: 60000,
    },
  ],
});
