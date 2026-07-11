import { test, expect } from './fixtures/test'
import { USER_FIXTURE } from './fixtures/data'
import {
  makeClassificationTrainingResult,
  makeTrainingError,
} from './fixtures/worker-fixtures'
import { WEBWORKER_ROUTES_ENUM } from '../../src/lib/data-processing/interfaces'

const PAGE_URL = '/classification' 

test.describe('Tabular Classification', () => {
  test.beforeEach(async ({ apiMocks }) => {
    
    await apiMocks.get('**/v1/auth/users/me', USER_FIXTURE)
    await apiMocks.get('**/v1/users/me/organizations', [])
    await apiMocks.get('**/v1/users/me/invitations', [])
  })

  test('happy path: upload sample → train → see dashboard', async ({
  page,
  workerMocks,
}) => {
  await workerMocks.onRoute(
    WEBWORKER_ROUTES_ENUM.TABULAR_TRAIN,
    makeClassificationTrainingResult(),
  )

  await page.goto(PAGE_URL)

  await expect(
    page.getByRole('heading', { name: /upload your data/i }),
  ).toBeVisible({ timeout: 15000 })

  await page.getByRole('button', { name: /use sample/i }).click()
  await expect(page.getByText(/iris\.csv/i)).toBeVisible({ timeout: 10000 })
  await page.getByRole('button', { name: /continue/i }).click()
  await page.getByRole('button', { name: /continue/i }).click()

  await expect(
    page.getByRole('heading', { name: /model evaluation dashboard/i }),
  ).toBeVisible({ timeout: 15000 })

  
  await expect(page.getByRole('heading', { name: /top 5 features/i })).toBeVisible()

  
  await expect(page.getByRole('columnheader', { name: 'feature_a' })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: 'feature_b' })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: 'Prediction' })).toBeVisible()

  const calls = await workerMocks.getCalls()
  expect(calls).toEqual(
    expect.arrayContaining([
      expect.objectContaining({ route: WEBWORKER_ROUTES_ENUM.TABULAR_TRAIN }),
    ]),
  )
})

  test('shows error toast when training fails', async ({ page, workerMocks }) => {
    await workerMocks.onRoute(
      WEBWORKER_ROUTES_ENUM.TABULAR_TRAIN,
      makeTrainingError('Invalid data shape'),
    )

    await page.goto(PAGE_URL)
    await page.getByRole('button', { name: /use sample/i }).click()
    await expect(page.getByText(/iris\.csv/i)).toBeVisible({ timeout: 10000 })
    await page.getByRole('button', { name: /continue/i }).click()
    await page.getByRole('button', { name: /continue/i }).click()

    await expect(page.getByText(/invalid data shape/i)).toBeVisible({ timeout: 10000 })
  })
})