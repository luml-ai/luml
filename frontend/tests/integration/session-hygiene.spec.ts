import { test, expect } from './fixtures/test'
import { ORG_ID, ORBIT_ID, TRACK_ID } from './fixtures/data'

for (const target of [
  '/sign-in',
  `/organization/${ORG_ID}/orbit/${ORBIT_ID}/tracks/${TRACK_ID}?tab=details#selected`,
]) {
  test(`anonymous entry at ${target} stops after one session request`, async ({ page }) => {
    const requests: string[] = []
    const errors: string[] = []
    await page.route('**/v1/**', async (route) => {
      const request = route.request()
      requests.push(`${request.method()} ${new URL(request.url()).pathname}`)
      await route.fulfill({ status: 401, json: { detail: 'Not authenticated' } })
    })
    page.on('console', (message) => {
      if (/Token refresh failed|Logout error:/.test(message.text())) errors.push(message.text())
    })

    await page.goto(target)

    await expect(page.getByRole('heading', { name: 'Sign in', exact: true })).toBeVisible()
    const current = new URL(page.url())
    expect(current.pathname).toBe('/sign-in')
    expect(current.searchParams.get('redirect')).toBe(target === '/sign-in' ? null : target)
    expect(requests).toEqual(['GET /v1/auth/users/me'])
    expect(errors).toEqual([])
  })
}
