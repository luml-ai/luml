import { test, expect } from './fixtures/test'
import {
  ORG_ID,
  ORG_ID_2,
  ORBIT_ID,
  ORBIT_ID_2,
  USER_FIXTURE,
  makeOrganization,
  makeOrganizationDetails,
  makeOrbit,
  makeOrbitDetails,
} from './fixtures/data'

for (const hasReplacement of [true, false]) {
  for (const startPage of ['settings', 'orbit']) {
    test(`leaves the current organization from ${startPage} ${hasReplacement ? 'with a replacement' : 'without a replacement'}`, async ({
      page,
      apiMocks,
    }) => {
      let left = false
      const departedRequests: string[] = []
      const replacement = makeOrganization({ id: ORG_ID_2, name: 'Second Org' })
      await apiMocks.get('**/v1/auth/users/me', USER_FIXTURE)
      await apiMocks.get('**/v1/users/me/invitations', [])
      await apiMocks.get('**/v1/users/me/organizations', () => [
        ...(left ? [] : [makeOrganization()]),
        ...(hasReplacement ? [replacement] : []),
      ])
      await apiMocks.get(`**/v1/organizations/${ORG_ID}`, makeOrganizationDetails())
      await apiMocks.get(`**/v1/organizations/${ORG_ID}/orbits`, [makeOrbit()])
      await apiMocks.get(`**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}`, makeOrbitDetails())
      await apiMocks.get(`**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections*`, [])
      await apiMocks.get(
        `**/v1/organizations/${ORG_ID_2}`,
        makeOrganizationDetails({ id: ORG_ID_2, name: 'Second Org' }),
      )
      await apiMocks.get(`**/v1/organizations/${ORG_ID_2}/orbits`, [
        makeOrbit({ id: ORBIT_ID_2, organization_id: ORG_ID_2 }),
      ])
      await apiMocks.get(
        `**/v1/organizations/${ORG_ID_2}/orbits/${ORBIT_ID_2}`,
        makeOrbitDetails({ id: ORBIT_ID_2, organization_id: ORG_ID_2 }),
      )
      await apiMocks.get(`**/v1/organizations/${ORG_ID_2}/orbits/${ORBIT_ID_2}/collections*`, [])
      await apiMocks.delete(`**/v1/organizations/${ORG_ID}/leave`, () => {
        left = true
        return {}
      })
      page.on('request', (request) => {
        if (left && request.url().includes(`/organizations/${ORG_ID}`)) {
          departedRequests.push(request.url())
        }
      })

      await page.goto(
        startPage === 'settings'
          ? `/organization/${ORG_ID}`
          : `/organization/${ORG_ID}/orbit/${ORBIT_ID}`,
      )
      await page.locator('.org-popover-wrapper .menu-link').click()
      await page
        .locator('.org-popover-wrapper .organization')
        .filter({ hasText: 'Acme Corp' })
        .locator('.button')
        .click()
      await page.getByRole('button', { name: 'Leave', exact: true }).click()

      const expectedPath = hasReplacement
        ? `/organization/${ORG_ID_2}/orbit/${ORBIT_ID_2}`
        : '/setup'
      await expect(page).toHaveURL(new RegExp(`${expectedPath}$`))
      await expect
        .poll(() => page.evaluate(() => localStorage.getItem('currentOrganizationId')))
        .toBe(hasReplacement ? JSON.stringify(ORG_ID_2) : null)
      await expect
        .poll(() => page.evaluate(() => localStorage.getItem('currentOrbitId')))
        .toBe(hasReplacement ? JSON.stringify(ORBIT_ID_2) : null)

      await page.reload()

      await expect(page).toHaveURL(new RegExp(`${expectedPath}$`))
      if (hasReplacement) {
        await expect(page.locator('.org-popover-wrapper .menu-link')).toContainText('Second Org')
      } else {
        await expect(page.getByText('Create an Orbit', { exact: true })).toBeVisible()
      }
      expect(departedRequests).toEqual([])
    })
  }
}
