import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

process.env.SHIFT_REPORT_TEST_API = "http://localhost:8023/api";
export default defineConfig({
  ...base,
  testMatch: "final-report.spec.ts",
  outputDir: "../tmp/report-review/browser-results",
  use: { ...base.use, baseURL: "http://localhost:3023" },
  webServer: [
    {
      command: "npm run dev -- --port 3023",
      env: {
        SHIFT_TEST_BUILD_DIR: ".next-report-check",
        NEXT_PUBLIC_API_BASE_URL: "http://localhost:8023",
      },
      url: "http://localhost:3023",
      reuseExistingServer: false,
      timeout: 120000,
    },
    {
      command:
        process.platform === "win32"
          ? "..\\backend\\.venv\\Scripts\\python.exe -m uvicorn tests.e2e_server:app --app-dir ../backend --port 8023"
          : "../backend/.venv/bin/python -m uvicorn tests.e2e_server:app --app-dir ../backend --port 8023",
      url: "http://localhost:8023/api/health",
      env: {
        CORS_ORIGINS: "http://localhost:3023",
        SESSION_SECRET: "isolated-report-browser-test-session-secret",
      },
      reuseExistingServer: false,
      timeout: 60000,
    },
  ],
});
