import { test, expect } from './fixtures/test'
import { USER_FIXTURE } from './fixtures/data'

for (const path of ['/sign-in', '/classification', '/runtime']) {
  test(`does not request Pyodide or wheels at ${path} before use`, async ({ page, apiMocks }) => {
    await apiMocks.get(
      '**/v1/auth/users/me',
      path === '/sign-in' ? { status: 401, body: {} } : USER_FIXTURE,
    )
    await apiMocks.get('**/v1/users/me/organizations', [])
    await apiMocks.get('**/v1/users/me/invitations', [])
    const requests: string[] = []
    await page.route(/webworker\.js|pyodide|\.whl(?:\?|$)/, (route) => {
      requests.push(route.request().url())
      return route.abort()
    })
    await page.goto(path)
    await expect(
      page
        .getByRole('heading', {
          name:
            path === '/sign-in'
              ? 'Sign in'
              : path === '/runtime'
                ? 'Upload your model'
                : 'Upload your data for model training',
        })
        .first(),
    ).toBeVisible()
    if (path === '/sign-in') {
      await page.reload()
      await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
    } else {
      await page
        .getByRole('button', { name: path === '/runtime' ? 'Express tasks' : 'Back', exact: true })
        .click()
      await expect(page).toHaveURL('/')
    }
    expect(requests).toEqual([])
  })
}

test('blocked Pyodide CDN shows a toast, clears training, and permits retry', async ({
  page,
  context,
  apiMocks,
}) => {
  await apiMocks.get('**/v1/auth/users/me', USER_FIXTURE)
  await apiMocks.get('**/v1/users/me/organizations', [])
  await apiMocks.get('**/v1/users/me/invitations', [])
  let downloads = 0
  await context.route('https://cdn.jsdelivr.net/pyodide/**', (route) => {
    downloads++
    return route.abort('failed')
  })
  await page.goto('/regression')
  await page.getByRole('button', { name: /use sample/i }).click()
  await expect(page.getByText(/insurance\.csv/i)).toBeVisible()
  await page.getByRole('button', { name: /continue/i }).click()
  for (let attempt = 1; attempt <= 2; attempt++) {
    await page.getByRole('button', { name: /continue/i }).click()
    const toast = page.getByRole('alert').last()
    await expect(toast).toContainText('Error', { timeout: 10_000 })
    await expect(toast).toContainText(/importScripts|Webworker|fetch/i)
    await expect(page.getByRole('heading', { name: 'Training in progress...' })).toBeHidden()
    await expect(page.getByRole('button', { name: /continue/i })).toBeEnabled()
    expect(downloads).toBe(attempt)
    await toast.getByRole('button', { name: /close/i }).click()
  }
})
