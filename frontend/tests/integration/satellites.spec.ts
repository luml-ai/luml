import { test, expect } from './fixtures/test'
import {
  ORG_ID,
  ORBIT_ID,
  USER_FIXTURE,
  makeBucketSecret,
  makeMember,
  makeOrbit,
  makeOrbitDetails,
  makeOrganization,
  makeOrganizationDetails,
} from './fixtures/data'

test.describe('Satellites', () => {
  test.beforeEach(async ({ page, apiMocks }) => {
    await apiMocks.get('**/v1/auth/users/me', USER_FIXTURE)
    await apiMocks.get('**/v1/users/me/organizations', [makeOrganization()])
    await apiMocks.get('**/v1/users/me/invitations', [])
    await apiMocks.get(`**/v1/organizations/${ORG_ID}/orbits`, [makeOrbit()])
    await apiMocks.get(
      `**/v1/organizations/${ORG_ID}`,
      makeOrganizationDetails({
        members: [makeMember({ user: USER_FIXTURE })],
        total_orbits: 1,
      }),
    )
    await apiMocks.get(`**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}`, makeOrbitDetails())
    await apiMocks.get(`**/v1/organizations/${ORG_ID}/bucket-secrets`, [makeBucketSecret()])
    await apiMocks.get(`**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/satellites`, [
      {
        id: '11111111-2222-3333-4444-555555555555',
        orbit_id: ORBIT_ID,
        name: 'Test satellite',
        description: 'Test description',
        base_url: 'https://satellite.example.com',
        paired: true,
        capabilities: {},
        present_capabilities: [],
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-02T00:00:00Z',
        last_seen_at: '2026-01-02T00:00:00Z',
        status: 'active',
      },
    ])

    await page.goto(`/organization/${ORG_ID}/orbit/${ORBIT_ID}/satellites`)
  })

  test('uses the default cursor for a satellite card', async ({ page }) => {
    const card = page.locator('.card').filter({ hasText: 'Test satellite' })
    await expect(card).toBeVisible()
    await expect(card).toHaveCSS('cursor', 'auto')
  })

  test('does not highlight a satellite card on hover', async ({ page }) => {
    const card = page.locator('.card').filter({ hasText: 'Test satellite' })
    await expect(card).toBeVisible()
    const backgroundColor = await card.evaluate(
      (element) => getComputedStyle(element).backgroundColor,
    )
    await card.hover()
    await page.waitForTimeout(250)

    await expect(card).toHaveCSS('background-color', backgroundColor)
  })
})
