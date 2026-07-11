import { test, expect } from './fixtures/test'
import { USER_FIXTURE } from './fixtures/data'
import { injectConnectedProviders } from './fixtures/worker-fixtures'
import type { Page } from '@playwright/test'

const PAGE_URL = '/prompt-fusion'

const taskDescriptionTextarea = (page: Page) =>
  page.getByRole('textbox', { name: /provide a short task description/i })

const openModelSelect = async (page: Page, type: 'teacher-model' | 'student-model') => {
  await page.locator(`.${type} .p-select`).click()
}

const pickModelOption = async (page: Page, modelName: string) => {
  await page
    .getByRole('listbox')
    .last()
    .getByRole('option', { name: modelName, exact: true })
    .click()
}

test.describe('Prompt Fusion — Free-form (UI & validation)', () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.get('**/v1/auth/users/me', USER_FIXTURE)
    await apiMocks.get('**/v1/users/me/organizations', [])
    await apiMocks.get('**/v1/users/me/invitations', [])
  })

  test('disables optimization button when no providers connected', async ({ page }) => {
    await page.goto(PAGE_URL)

    await expect(page.getByText('Input', { exact: true }).first()).toBeVisible({
      timeout: 15000,
    })

    await expect(page.getByRole('button', { name: /optimization/i })).toBeDisabled()
  })

  test('renders pipeline editor with default Input/Output nodes', async ({ page }) => {
    await injectConnectedProviders(page)
    await page.goto(PAGE_URL)

    await expect(page.getByText('Input', { exact: true }).first()).toBeVisible({
      timeout: 15000,
    })
    await expect(page.getByText('Output', { exact: true }).first()).toBeVisible()

    await expect(page.getByRole('button', { name: /optimization/i })).toBeEnabled()
  })

  test('opens optimization sidebar and selects models', async ({ page }) => {
    await injectConnectedProviders(page)
    await page.goto(PAGE_URL)

    await expect(page.getByText('Input', { exact: true }).first()).toBeVisible({
      timeout: 15000,
    })

    await page.getByRole('button', { name: /optimization/i }).click()
    await expect(page.getByText(/optimization settings/i)).toBeVisible()

    await taskDescriptionTextarea(page).fill('Translate text and make it formal')

    await openModelSelect(page, 'teacher-model')
    await pickModelOption(page, 'gpt-4o')

    await openModelSelect(page, 'student-model')
    await pickModelOption(page, 'gpt-4o-mini')

    
    await expect(
      page.locator('.teacher-model .p-select-label'),
    ).toHaveText('gpt-4o')
    await expect(
      page.locator('.student-model .p-select-label'),
    ).toHaveText('gpt-4o-mini')
  })

  test('shows error when running optimization with empty pipeline', async ({ page }) => {
    await injectConnectedProviders(page)
    await page.goto(PAGE_URL)

    await expect(page.getByText('Input', { exact: true }).first()).toBeVisible({
      timeout: 15000,
    })

    await page.getByRole('button', { name: /optimization/i }).click()
    await taskDescriptionTextarea(page).fill('Some task')

    await openModelSelect(page, 'teacher-model')
    await pickModelOption(page, 'gpt-4o')
    await openModelSelect(page, 'student-model')
    await pickModelOption(page, 'gpt-4o-mini')

    await page.getByRole('button', { name: /run optimization/i }).click()

    await expect(
      page.getByText(/pipeline.*not connected|pipeline has no nodes/i),
    ).toBeVisible({ timeout: 5000 })
  })

  test('shows error when running optimization without task description', async ({
    page,
  }) => {
    await injectConnectedProviders(page)
    await page.goto(PAGE_URL)

    await expect(page.getByText('Input', { exact: true }).first()).toBeVisible({
      timeout: 15000,
    })

    await page.getByRole('button', { name: /optimization/i }).click()

    await openModelSelect(page, 'teacher-model')
    await pickModelOption(page, 'gpt-4o')
    await openModelSelect(page, 'student-model')
    await pickModelOption(page, 'gpt-4o-mini')

    await page.getByRole('button', { name: /run optimization/i }).click()

    await expect(page.getByText(/task description is required/i)).toBeVisible({
      timeout: 5000,
    })
  })

  test('predict button disabled until model is trained', async ({ page }) => {
    await injectConnectedProviders(page)
    await page.goto(PAGE_URL)

    await expect(page.getByText('Input', { exact: true }).first()).toBeVisible({
      timeout: 15000,
    })

    const playButton = page.locator('.content > button').last()

    await expect(playButton).toBeDisabled()
  })
})