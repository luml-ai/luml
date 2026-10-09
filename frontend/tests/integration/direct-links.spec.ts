import { test, expect } from './fixtures/test'
import {
  ORG_ID,
  ORG_ID_2,
  ORBIT_ID,
  ORBIT_ID_2,
  TRACK_ID,
  USER_ID,
  USER_FIXTURE,
  makeOrganization,
  makeOrganizationDetails,
  makeOrbit,
  makeOrbitDetails,
} from './fixtures/data'

for (const savedHasOrbits of [false, true]) {
  for (const delayedResponse of ['organizations', 'saved-orbits']) {
    test(`direct track link selects its organization and orbit with saved orbits=${savedHasOrbits} and delayed ${delayedResponse}`, async ({
      page,
      apiMocks,
    }) => {
      const savedOrbitId = 'cccccccc-cccc-cccc-cccc-cccccccccccc'
      await page.addInitScript(
        ({ organizationId, orbitId }) => {
          localStorage.setItem('currentOrganizationId', JSON.stringify(organizationId))
          localStorage.setItem('currentOrbitId', JSON.stringify(orbitId))
        },
        { organizationId: ORG_ID, orbitId: savedOrbitId },
      )
      await apiMocks.get('**/v1/auth/users/me', USER_FIXTURE)
      await apiMocks.get('**/v1/users/me/invitations', [])
      await apiMocks.get('**/v1/users/me/organizations', async () => {
        if (delayedResponse === 'organizations') {
          await new Promise((resolve) => setTimeout(resolve, 200))
        }
        return [makeOrganization(), makeOrganization({ id: ORG_ID_2, name: 'Linked Org' })]
      })
      await apiMocks.get(`**/v1/organizations/${ORG_ID}/orbits`, async () => {
        if (delayedResponse === 'saved-orbits') {
          await new Promise((resolve) => setTimeout(resolve, 200))
        }
        return savedHasOrbits ? [makeOrbit({ id: savedOrbitId, name: 'Saved Orbit' })] : []
      })
      await apiMocks.get(`**/v1/organizations/${ORG_ID}`, makeOrganizationDetails())
      await apiMocks.get(
        `**/v1/organizations/${ORG_ID}/orbits/${savedOrbitId}`,
        makeOrbitDetails({ id: savedOrbitId, name: 'Saved Orbit' }),
      )
      await apiMocks.get(
        `**/v1/organizations/${ORG_ID_2}`,
        makeOrganizationDetails({ id: ORG_ID_2, name: 'Linked Org' }),
      )
      await apiMocks.get(`**/v1/organizations/${ORG_ID_2}/orbits`, [
        makeOrbit({ organization_id: ORG_ID_2, name: 'First Linked Orbit' }),
        makeOrbit({ id: ORBIT_ID_2, organization_id: ORG_ID_2, name: 'Linked Orbit' }),
      ])
      for (const orbitId of [ORBIT_ID, ORBIT_ID_2]) {
        await apiMocks.get(
          `**/v1/organizations/${ORG_ID_2}/orbits/${orbitId}`,
          makeOrbitDetails({ id: orbitId, organization_id: ORG_ID_2 }),
        )
      }
      const trackApi = `**/v1/organizations/${ORG_ID_2}/orbits/${ORBIT_ID_2}/tracks/${TRACK_ID}`
      await apiMocks.get(trackApi, {
        id: TRACK_ID,
        orbit_id: ORBIT_ID_2,
        name: 'Linked Track',
        artifact_type: 'model',
        description: null,
        tags: [],
        created_by: USER_ID,
        next_version: 1,
        total_entries: 0,
        created_at: '2025-01-01T00:00:00.000Z',
        updated_at: null,
      })
      await apiMocks.get(`${trackApi}/stages`, [])
      await apiMocks.get(`${trackApi}/entries?**`, { items: [], cursor: null })
      await apiMocks.get(`**/v1/organizations/${ORG_ID_2}/orbits/${ORBIT_ID_2}/collections?**`, {
        items: [],
        cursor: null,
      })

      await page.goto(`/organization/${ORG_ID_2}/orbit/${ORBIT_ID_2}/tracks/${TRACK_ID}`)
      for (let load = 0; load < 2; load++) {
        if (load) await page.reload()
        await expect(page.getByRole('heading', { name: 'Linked Track' })).toBeVisible()
        await expect(page.locator('.org-popover-wrapper .menu-link')).toContainText('Linked Org')
        const orbitTrigger = page.locator('.orbit-popover-wrapper .menu-link')
        await expect(orbitTrigger).toContainText('Linked Orbit')
        await orbitTrigger.click()
        const list = page.locator('.orbit-popover-wrapper .list-scroll')
        await expect(
          list.getByRole('button', { name: 'First Linked Orbit', exact: true }),
        ).toBeVisible()
        await expect(list.getByRole('button', { name: 'Linked Orbit', exact: true })).toBeVisible()
        await expect(list.getByRole('button', { name: 'Saved Orbit' })).toHaveCount(0)
        await orbitTrigger.click()
        await page.getByRole('button', { name: 'Link artifact', exact: true }).click()
        await expect(
          page.getByRole('dialog').getByText('Collection', { exact: true }),
        ).toBeVisible()
      }
    })
  }
}
