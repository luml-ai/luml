import { test, expect } from './fixtures/test'
import { USER_FIXTURE, makeInvitation, makeOrganization } from './fixtures/data'

test.describe('Invitation links', () => {
  test('redirects unauthenticated users to sign in and preserves the invitation route', async ({
    page,
    apiMocks,
  }) => {
    await apiMocks.get('**/v1/auth/users/me', {
      status: 401,
      body: { detail: 'Not authenticated' },
    })

    await page.goto('/invitations')

    await expect(page).toHaveURL(/\/sign-in\?redirect=%2Finvitations$/)
  })

  test('shows the invitation page to authenticated users', async ({ page, apiMocks }) => {
    const organization = makeOrganization()
    const invitation = makeInvitation({ organization })

    await apiMocks.get('**/v1/auth/users/me', USER_FIXTURE)
    await apiMocks.get('**/v1/users/me/organizations', [organization])
    await apiMocks.get('**/v1/users/me/invitations', [invitation])

    await page.goto('/invitations')

    await expect(page).toHaveURL(/\/invitations$/)
    await expect(page.getByRole('heading', { name: 'Invitation center' })).toBeVisible()
    await expect(page.getByText('Acme Corp')).toBeVisible()
  })
})
