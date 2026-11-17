import { defineConfig, devices } from '@playwright/test'

// Full-stack suites; run through run.sh, which starts the stack and sets the E2E_* variables.
const suite = process.env.E2E_SUITE ?? 'all'
const specs = { platform: /platform\.spec\.ts/, flow: /flow\.spec\.ts/, all: /\.spec\.ts/ }

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
      ]
    : [['list']],
  use: {
    trace: 'retain-on-failure',
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
