import { defineConfig, devices } from '@playwright/test'

// Full-stack suites; run through run.sh, which starts the stack and sets the E2E_* variables.
const suite = process.env.E2E_SUITE ?? 'all'
// The error guard's own tests run with each suite.
const specs = {
  platform: /(platform|error_guard)\.spec\.ts/,
  flow: /(flow|error_guard)\.spec\.ts/,
  all: /\.spec\.ts/,
}
// run.sh reads the results to fail a run with skipped or flaky tests (E2E_STRICT=1).
const results = process.env.E2E_RESULTS
  ? [['json', { outputFile: process.env.E2E_RESULTS }] as const]
  : []

export default defineConfig({
  testDir: '.',
  globalSetup: './global-setup.ts',
  testMatch: specs[suite as keyof typeof specs] ?? specs.all,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  fullyParallel: false,
  timeout: 180_000,
  outputDir: `${process.env.E2E_LOGS ?? 'test-results'}/playwright`,
  reporter: process.env.CI
    ? [
        ['github'],
        ['list'],
        ['html', { open: 'never', outputFolder: `${process.env.E2E_LOGS}/report` }],
        ...results,
      ]
    : [['list'], ...results],
  use: {
    // A trace holds every request's URL and headers (signed storage URLs, cookies), and CI
    // uploads the logs of a failed run: no traces there.
    trace: process.env.CI ? 'off' : 'retain-on-failure',
    screenshot: 'only-on-failure',
    actionTimeout: 15_000,
    navigationTimeout: 60_000,
    viewport: { width: 1440, height: 1000 },
  },
  expect: { timeout: 30_000 },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 1000 } },
    },
  ],
})
