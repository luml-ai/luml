import { chromium } from '@playwright/test'
import { join } from 'node:path'

/**
 * Signs in once for the platform suite and saves the session for every test: the backend
 * rate-limits sign-in attempts per account, so a sign-in per test would trip it.
 */
export default async function globalSetup(): Promise<void> {
  const frontend = process.env.E2E_FRONTEND_URL
  if (!frontend || !process.env.E2E_WORK_DIR) return
  const browser = await chromium.launch()
  try {
    const page = await browser.newPage()
    await page.goto(`${frontend}/sign-in`)
    await page.getByLabel('Email').fill(process.env.DEV_ADMIN_EMAIL ?? '')
    await page.locator('#password input').fill(process.env.DEV_ADMIN_PASSWORD ?? '')
    await page.getByRole('button', { name: 'Sign in', exact: true }).click()
    await page.waitForURL((url) => !url.pathname.startsWith('/sign-in'), { timeout: 60_000 })
    await page
      .context()
      .storageState({ path: join(process.env.E2E_WORK_DIR, 'browser-state.json') })
  } finally {
    await browser.close()
  }
}
