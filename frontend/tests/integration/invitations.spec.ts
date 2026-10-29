import { test, expect } from './fixtures/test'
import type { ApiMocks } from './fixtures/api-mocks'
import {
  INVITE_ID,
  ORG_ID,
  USER_FIXTURE,
  makeInvitation,
  makeOrbit,
  makeOrganization,
  makeOrganizationDetails,
} from './fixtures/data'

const SIGNIN_SUCCESS = {
  detail: 'ok',
  user_id: USER_FIXTURE.id,
}

async function mockAuthenticatedInvitationPage(apiMocks: ApiMocks) {
  const organization = makeOrganization()
  const invitation = makeInvitation({ organization })

  await apiMocks.get('**/v1/auth/users/me', USER_FIXTURE)
  await apiMocks.get('**/v1/users/me/organizations', [organization])
  await apiMocks.get('**/v1/users/me/invitations', [invitation])
  await apiMocks.get(`**/v1/organizations/${ORG_ID}/orbits`, [makeOrbit()])
  await apiMocks.get(`**/v1/organizations/${ORG_ID}`, makeOrganizationDetails())
}

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

    await expect(page).toHaveURL(/\/sign-in\?redirect=\/invitations$/)
  })

  test('returns to invitations after password sign-in', async ({ page, apiMocks }) => {
    let userRequests = 0
    await apiMocks.get('**/v1/auth/users/me', () => {
      userRequests += 1
      return userRequests === 1
        ? { status: 401, body: { detail: 'Not authenticated' } }
        : USER_FIXTURE
    })
    await apiMocks.post('**/v1/auth/signin', SIGNIN_SUCCESS)
    await apiMocks.get('**/v1/users/me/organizations', [makeOrganization()])
    await apiMocks.get('**/v1/users/me/invitations', [])

    await page.goto('/invitations')
    await page.getByLabel('Email').fill('invitee@example.com')
    await page.locator('#password input').fill('password123')
    await page.getByRole('button', { name: 'Sign in', exact: true }).click()

    await expect(page).toHaveURL(/\/invitations$/)
  })

  for (const [provider, label] of [
    ['google', 'Google'],
    ['microsoft', 'Microsoft'],
  ]) {
    test(`returns to invitations after ${label} sign-in`, async ({ page, apiMocks }) => {
      let userRequests = 0
      await apiMocks.get('**/v1/auth/users/me', () => {
        userRequests += 1
        return userRequests === 1
          ? { status: 401, body: { detail: 'Not authenticated' } }
          : USER_FIXTURE
      })
      await apiMocks.get(`**/v1/auth/${provider}/callback**`, SIGNIN_SUCCESS)
      await apiMocks.get('**/v1/users/me/organizations', [makeOrganization()])
      await apiMocks.get('**/v1/users/me/invitations', [])

      await page.goto('/invitations')
      const appOrigin = new URL(page.url()).origin
      const state = `${provider}.signed.state.token`
      await page.route(`**/v1/auth/${provider}/login`, async (route) => {
        await route.fulfill({
          status: 302,
          headers: { location: `${appOrigin}/sign-in?code=oauth-code&state=${state}` },
        })
      })
      const callback = page.waitForRequest(`**/v1/auth/${provider}/callback**`)
      await page.getByRole('button', { name: `Sign in with ${label}` }).click()

      const params = new URL((await callback).url()).searchParams
      expect(params.get('code')).toBe('oauth-code')
      expect(params.get('state')).toBe(state)
      await expect(page).toHaveURL(/\/invitations$/)
    })
  }

  test('preserves invitations through registration and email confirmation', async ({
    page,
    apiMocks,
  }) => {
    let userRequests = 0
    await apiMocks.get('**/v1/auth/users/me', () => {
      userRequests += 1
      return userRequests === 1
        ? { status: 401, body: { detail: 'Not authenticated' } }
        : USER_FIXTURE
    })
    await apiMocks.post('**/v1/auth/signup', { detail: 'Please confirm your email address' })
    await apiMocks.post('**/v1/auth/signin', SIGNIN_SUCCESS)
    await apiMocks.get('**/v1/users/me/organizations', [makeOrganization()])
    await apiMocks.get('**/v1/users/me/invitations', [])

    await page.goto('/invitations')
    await page.getByRole('link', { name: 'Sign up' }).click()
    await expect(page).toHaveURL(/\/sign-up\?redirect=\/invitations$/)

    await page.getByLabel('Name').fill('Invitee')
    await page.getByLabel('Email').fill('invitee@example.com')
    await page.locator('#password input').fill('password123')
    await page.getByRole('button', { name: 'Sign up', exact: true }).click()
    await expect(page).toHaveURL(/\/email-check\?redirect=\/invitations$/)

    await page.goto('/email-confirmed')
    await page.getByRole('button', { name: 'Go to account' }).click()
    await expect(page).toHaveURL(/\/sign-in\?redirect=\/invitations$/)

    await page.getByLabel('Email').fill('invitee@example.com')
    await page.locator('#password input').fill('password123')
    await page.getByRole('button', { name: 'Sign in', exact: true }).click()
    await expect(page).toHaveURL(/\/invitations$/)
  })

  test('opens the invitation dialog over the home page for authenticated users', async ({
    page,
    apiMocks,
  }) => {
    await mockAuthenticatedInvitationPage(apiMocks)

    await page.goto('/invitations')

    await expect(page).toHaveURL(/\/invitations$/)
    await expect(page.getByRole('heading', { name: 'Pick a Machine Learning Task' })).toBeVisible()
    await expect(
      page.getByRole('dialog').getByRole('heading', { name: 'invitation center' }),
    ).toBeVisible()
    await expect(page.getByRole('dialog').getByText('Acme Corp')).toBeVisible()
  })

  test('returns to the home route when the invitation dialog is closed', async ({
    page,
    apiMocks,
  }) => {
    await mockAuthenticatedInvitationPage(apiMocks)

    await page.goto('/invitations')
    await page.getByRole('dialog').getByRole('button', { name: 'Close' }).click()

    await expect(page.getByRole('dialog')).toBeHidden()
    await expect(page).toHaveURL(/\/$/)
  })

  test('opens the invitation dialog from the bell button', async ({ page, apiMocks }) => {
    await mockAuthenticatedInvitationPage(apiMocks)

    await page.goto('/')
    await page.getByRole('button', { name: 'Invitations' }).click()

    await expect(page.getByRole('dialog').getByText('Acme Corp')).toBeVisible()
    await expect(page).toHaveURL(/\/$/)
  })

  test('shows loading while invitations are being fetched', async ({ page, apiMocks }) => {
    let resolveInvitations: (value: unknown[]) => void = () => {}
    const invitations = new Promise<unknown[]>((resolve) => {
      resolveInvitations = resolve
    })

    await apiMocks.get('**/v1/auth/users/me', USER_FIXTURE)
    await apiMocks.get('**/v1/users/me/organizations', [makeOrganization()])
    await apiMocks.get('**/v1/users/me/invitations', () => invitations)

    await page.goto('/invitations')
    await expect(page.getByText('Loading invitations...')).toBeVisible()

    resolveInvitations([])
    await expect(
      page.getByText('There are currently no invitations awaiting response.'),
    ).toBeVisible()
  })

  test('shows an error and retries loading invitations', async ({ page, apiMocks }) => {
    let invitationRequests = 0
    await apiMocks.get('**/v1/auth/users/me', USER_FIXTURE)
    await apiMocks.get('**/v1/users/me/organizations', [makeOrganization()])
    await apiMocks.get('**/v1/users/me/invitations', () => {
      invitationRequests += 1
      return invitationRequests === 1
        ? { status: 500, body: { detail: 'Unavailable' } }
        : [makeInvitation({ organization: makeOrganization() })]
    })

    await page.goto('/invitations')
    await expect(page.getByText('Failed to load invitations.')).toBeVisible()
    await page.getByRole('button', { name: 'Retry' }).click()

    await expect(page.getByRole('dialog').getByText('Acme Corp')).toBeVisible()
  })

  test('accepts an invitation and shows success', async ({ page, apiMocks }) => {
    await mockAuthenticatedInvitationPage(apiMocks)
    await apiMocks.post(`**/v1/users/me/invitations/${INVITE_ID}/accept`, {})

    await page.goto('/invitations')
    await page.getByRole('button', { name: 'Accept invitation' }).click()

    await expect(page.getByText('You’ve joined the organization successfully.')).toBeVisible()
    await expect(
      page.getByText('There are currently no invitations awaiting response.'),
    ).toBeVisible()
  })

  test('keeps an invitation when accepting fails', async ({ page, apiMocks }) => {
    await mockAuthenticatedInvitationPage(apiMocks)
    await apiMocks.post(`**/v1/users/me/invitations/${INVITE_ID}/accept`, {
      status: 500,
      body: { detail: 'Unavailable' },
    })

    await page.goto('/invitations')
    await page.getByRole('button', { name: 'Accept invitation' }).click()

    await expect(page.getByText('Failed to accept the invitation')).toBeVisible()
    await expect(page.getByRole('dialog').getByText('Acme Corp')).toBeVisible()
  })

  test('declines an invitation and shows success', async ({ page, apiMocks }) => {
    await mockAuthenticatedInvitationPage(apiMocks)
    await apiMocks.post(`**/v1/users/me/invitations/${INVITE_ID}/reject`, {})

    await page.goto('/invitations')
    await page.getByRole('button', { name: 'Decline invitation' }).click()

    await expect(page.getByText('The invitation has been declined.')).toBeVisible()
    await expect(
      page.getByText('There are currently no invitations awaiting response.'),
    ).toBeVisible()
  })

  test('keeps an invitation when declining fails', async ({ page, apiMocks }) => {
    await mockAuthenticatedInvitationPage(apiMocks)
    await apiMocks.post(`**/v1/users/me/invitations/${INVITE_ID}/reject`, {
      status: 500,
      body: { detail: 'Unavailable' },
    })

    await page.goto('/invitations')
    await page.getByRole('button', { name: 'Decline invitation' }).click()

    await expect(page.getByText('Failed to reject the invitation')).toBeVisible()
    await expect(page.getByRole('dialog').getByText('Acme Corp')).toBeVisible()
  })
})
