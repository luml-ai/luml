import { test, expect } from './fixtures/test'
import { USER_FIXTURE } from './fixtures/data'

test('Jupyter Lite keeps notebook navigation and stored instances', async ({ page, apiMocks }) => {
  await apiMocks.get('**/v1/auth/users/me', USER_FIXTURE)
  await apiMocks.get('**/v1/users/me/organizations', [])
  await apiMocks.get('**/v1/users/me/invitations', [])

  await page.goto('/express-tasks')
  const card = page
    .locator('.card')
    .filter({ has: page.getByText('Jupyter Lite', { exact: true }) })
  await expect(card).toBeVisible()
  await card.getByRole('button', { name: 'Next', exact: true }).click()
  await expect(page).toHaveURL('/notebooks')
  await expect(page.getByRole('heading', { name: 'Jupyter Lite', exact: true })).toBeVisible()
  await expect(
    page.getByText('You don’t have any notebook instances yet.', { exact: false }),
  ).toBeVisible()

  await page.getByRole('button', { name: 'Create instance', exact: true }).click()
  await page.getByRole('textbox', { name: 'Name', exact: true }).fill('Saved notebook')
  await page.getByRole('button', { name: 'Create', exact: true }).click()
  await expect(page.getByRole('cell', { name: 'Saved notebook', exact: true })).toBeVisible()
  const notebookLink = page.getByRole('link', { name: 'JupyterLab' })
  await expect(notebookLink).toHaveAttribute('href', /^\/jupyter\/lab\/index\.html\?instanceId=jl_/)
  const href = await notebookLink.getAttribute('href')

  await page.reload()
  await expect(page.getByRole('heading', { name: 'Jupyter Lite', exact: true })).toBeVisible()
  await expect(page.getByRole('cell', { name: 'Saved notebook', exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: 'JupyterLab' })).toHaveAttribute('href', href!)
})
