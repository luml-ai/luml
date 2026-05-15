import { test, expect } from './fixtures/test'
import type { ApiMocks } from './fixtures/api-mocks'
import {
  ORG_ID,
  ORBIT_ID,
  ORBIT_ID_2,
  BUCKET_ID,
  USER_ID,
  USER_ID_2,
  USER_FIXTURE,
  OrbitRole,
  makeOrganization,
  makeOrganizationDetails,
  makeMember,
  makeOrbit,
  makeOrbitDetails,
  makeBucketSecret,
} from './fixtures/data'


async function mockAuthenticatedBaseline(apiMocks: ApiMocks) {
  await apiMocks.get('**/v1/auth/users/me', USER_FIXTURE)
  await apiMocks.get('**/v1/users/me/organizations', [makeOrganization()])
  await apiMocks.get('**/v1/users/me/invitations', [])

  await apiMocks.get(`**/v1/organizations/${ORG_ID}/orbits`, [makeOrbit()])

  await apiMocks.get(
    `**/v1/organizations/${ORG_ID}`,
    makeOrganizationDetails({
      members: [makeMember({ user: USER_FIXTURE })],
      total_orbits: 1,
      orbits_limit: 10,
    }),
  )

  await apiMocks.get(
    `**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}`,
    makeOrbitDetails(),
  )
  await apiMocks.get(
    `**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID_2}`,
    makeOrbitDetails({ id: ORBIT_ID_2, name: 'Secondary Orbit' }),
  )

  await apiMocks.get(
    `**/v1/organizations/${ORG_ID}/bucket-secrets`,
    [makeBucketSecret()],
  )
}

async function openOrbitPopover(page: import('@playwright/test').Page, orbitName: string) {
  await page.locator('.orbit-popover-wrapper .menu-link').click()
  await expect(page.getByText(`${orbitName}`, { exact: true }).first()).toBeVisible()
}

test.describe('Orbits', () => {
  test.beforeEach(async ({ apiMocks }) => {
    await mockAuthenticatedBaseline(apiMocks)
  })

  test.describe('Orbit switcher popover', () => {
    test('shows current orbit name and the list of available orbits', async ({
      page,
      apiMocks,
    }) => {
      await apiMocks.get(`**/v1/organizations/${ORG_ID}/orbits`, [
        makeOrbit(),
        makeOrbit({ id: ORBIT_ID_2, name: 'Secondary Orbit' }),
      ])

      await page.goto(`/organization/${ORG_ID}/orbit/${ORBIT_ID}`)

      const trigger = page.locator('.orbit-popover-wrapper .menu-link')
      await expect(trigger).toContainText('Main Orbit')

      await trigger.click()

      await expect(page.getByText('Switch to Orbit')).toBeVisible()
      const list = page.locator('.orbit-popover-wrapper .list-scroll')
      await expect(list.getByRole('button', { name: 'Main Orbit' })).toBeVisible()
      await expect(list.getByRole('button', { name: 'Secondary Orbit' })).toBeVisible()
    })

    test('shows empty state when there are no orbits', async ({ page, apiMocks }) => {
      await apiMocks.get(`**/v1/organizations/${ORG_ID}/orbits`, [])
      await page.goto('/')

      const trigger = page.locator('.orbit-popover-wrapper .menu-link')
      await expect(trigger).toBeVisible()
      await trigger.click()

      await expect(page.getByText('Add new Orbit')).toBeVisible()
      await expect(
        page.getByText("Start by creating an Orbit to organize your team's work"),
      ).toBeVisible()

      await expect(page.getByText('Switch to Orbit')).toBeHidden()
    })

    test('switches active orbit and updates URL to the same tab', async ({
      page,
      apiMocks,
    }) => {
      await apiMocks.get(`**/v1/organizations/${ORG_ID}/orbits`, [
        makeOrbit(),
        makeOrbit({ id: ORBIT_ID_2, name: 'Secondary Orbit' }),
      ])

      await page.goto(`/organization/${ORG_ID}/orbit/${ORBIT_ID}`)

      await page.locator('.orbit-popover-wrapper .menu-link').click()
      await page
        .locator('.orbit-popover-wrapper .list-scroll')
        .getByRole('button', { name: 'Secondary Orbit' })
        .click()

      await expect(page).toHaveURL(
        new RegExp(`/organization/${ORG_ID}/orbit/${ORBIT_ID_2}$`),
      )
      await expect(
        page.locator('.orbit-popover-wrapper .menu-link'),
      ).toContainText('Secondary Orbit')
    })
  })


  test.describe('Create orbit', () => {
    test('creates an orbit with valid name and bucket', async ({ page, apiMocks }) => {
      let createPayload: unknown = null
      await apiMocks.post(`**/v1/organizations/${ORG_ID}/orbits`, (req: { postDataJSON: () => unknown }) => {
        createPayload = req.postDataJSON()
        return makeOrbit({ id: ORBIT_ID_2, name: 'New Orbit' })
      })

      await page.goto(`/organization/${ORG_ID}/orbit/${ORBIT_ID}`)

      await page.locator('.orbit-popover-wrapper .menu-link').click()
      await page.getByRole('button', { name: /New orbit/i }).click()

      const dialog = page.getByRole('dialog', { name: /CREATE A NEW ORBIT/i })
      await expect(dialog).toBeVisible()

      await dialog.getByLabel('Orbit name').fill('New Orbit')

      await dialog.getByLabel('Bucket').click()
      await page.getByRole('option', { name: 'main-bucket' }).click()

      await dialog.getByRole('button', { name: 'Create', exact: true }).click()

      await expect.poll(() => createPayload).toMatchObject({
        name: 'New Orbit',
        bucket_secret_id: BUCKET_ID,
      })
      await expect(page.getByText('Orbit created')).toBeVisible()
    })

    test('blocks create when name is empty', async ({ page, apiMocks }) => {
      let createCalled = false
      await apiMocks.post(`**/v1/organizations/${ORG_ID}/orbits`, () => {
        createCalled = true
        return makeOrbit()
      })

      await page.goto(`/organization/${ORG_ID}/orbit/${ORBIT_ID}`)

      await page.locator('.orbit-popover-wrapper .menu-link').click()
      await page.getByRole('button', { name: /New orbit/i }).click()

      const dialog = page.getByRole('dialog', { name: /CREATE A NEW ORBIT/i })
      await dialog.getByRole('button', { name: 'Create', exact: true }).click()

      await page.waitForTimeout(500)
      expect(createCalled).toBe(false)
    })

    test('blocks create with a name already taken by another orbit', async ({
      page,
      apiMocks,
    }) => {
      let createCalled = false
      await apiMocks.post(`**/v1/organizations/${ORG_ID}/orbits`, () => {
        createCalled = true
        return makeOrbit()
      })

      await page.goto(`/organization/${ORG_ID}/orbit/${ORBIT_ID}`)
      await page.locator('.orbit-popover-wrapper .menu-link').click()
      await page.getByRole('button', { name: /New orbit/i }).click()

      const dialog = page.getByRole('dialog', { name: /CREATE A NEW ORBIT/i })
      await dialog.getByLabel('Orbit name').fill('Main Orbit')
      await dialog.getByLabel('Bucket').click()
      await page.getByRole('option', { name: 'main-bucket' }).click()
      await dialog.getByRole('button', { name: 'Create', exact: true }).click()

      await page.waitForTimeout(500)
      expect(createCalled).toBe(false)
    })

    test('create button is disabled when orbit limit is reached', async ({
      page,
      apiMocks,
    }) => {
      await apiMocks.get(
        `**/v1/organizations/${ORG_ID}`,
        makeOrganizationDetails({
          total_orbits: 5,
          orbits_limit: 5,
          members: [makeMember({ user: USER_FIXTURE })],
        }),
      )

      await page.goto(`/organization/${ORG_ID}/orbit/${ORBIT_ID}`)

      await page.locator('.orbit-popover-wrapper .menu-link').click()
      const createBtn = page.getByRole('button', { name: /New orbit/i })
      await expect(createBtn).toBeDisabled()
    })

    test('assigns members with roles on create', async ({ page, apiMocks }) => {
      const SECOND_MEMBER_USER = {
        ...USER_FIXTURE,
        id: USER_ID_2,
        email: 'member2@example.com',
        full_name: 'Second Member',
      }
      await apiMocks.get(
        `**/v1/organizations/${ORG_ID}`,
        makeOrganizationDetails({
          members: [
            makeMember({ user: USER_FIXTURE }),
            makeMember({ id: 'member-2', user: SECOND_MEMBER_USER }),
          ],
          members_by_role: { owner: 1, admin: 0, member: 1 },
          orbits_limit: 10,
        }),
      )

      let createPayload: unknown = null
      await apiMocks.post(`**/v1/organizations/${ORG_ID}/orbits`, (req: { postDataJSON: () => unknown }) => {
        createPayload = req.postDataJSON()
        return makeOrbit({ id: ORBIT_ID_2, name: 'With Members' })
      })

      await page.goto(`/organization/${ORG_ID}/orbit/${ORBIT_ID}`)

      await page.locator('.orbit-popover-wrapper .menu-link').click()
      await page.getByRole('button', { name: /New orbit/i }).click()

      const dialog = page.getByRole('dialog', { name: /CREATE A NEW ORBIT/i })
      await dialog.getByLabel('Orbit name').fill('With Members')

      const membersField = dialog.locator('#members')
      await membersField.click()

      const memberOption = page
        .locator('.p-multiselect-overlay, .p-multiselect-panel, [role="listbox"]')
        .getByText('Second Member', { exact: true })
        .first()
      await memberOption.waitFor({ state: 'visible', timeout: 5000 })
      await memberOption.click()
      await page.keyboard.press('Escape')

      const bucketField = dialog.locator('#bucket')
      await bucketField.click()
      const bucketOption = page
        .locator('.p-select-overlay, .p-select-panel, [role="listbox"]')
        .getByText('main-bucket', { exact: true })
        .first()
      await bucketOption.waitFor({ state: 'visible', timeout: 5000 })
      await bucketOption.click()

      await dialog.getByRole('button', { name: 'Create', exact: true }).click()

      await expect.poll(() => createPayload).toMatchObject({
        name: 'With Members',
        members: [{ user_id: USER_ID_2, role: OrbitRole.member }],
      })
    })
  })


  test.describe('Edit orbit', () => {
    test('updates orbit name', async ({ page, apiMocks }) => {
      let patchPayload: unknown = null
      await apiMocks.patch(
        `**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}`,
        (req: { postDataJSON: () => unknown }) => {
          patchPayload = req.postDataJSON()
          return makeOrbit({ name: 'Renamed Orbit' })
        },
      )

      await page.goto(`/organization/${ORG_ID}/orbit/${ORBIT_ID}`)

      await page.locator('.orbit-popover-wrapper .menu-link').click()
      const activeRow = page.locator('.orbit-popover-wrapper .orbit-item.active')
      await activeRow.getByRole('button').last().click() 

      const dialog = page
        .getByRole('dialog')
        .filter({ has: page.getByText('orbit settings', { exact: true }) })
      await expect(dialog).toBeVisible()

      await dialog.getByLabel('Name').fill('Renamed Orbit')
      await dialog.getByRole('button', { name: 'save changes' }).click()

      await expect.poll(() => patchPayload).toMatchObject({
        id: ORBIT_ID,
        name: 'Renamed Orbit',
      })
      await expect(page.getByText('Orbit info successfully updated')).toBeVisible()
    })
  })


  test.describe('Delete orbit', () => {
    test('deletes the orbit after confirm dialog', async ({ page, apiMocks }) => {
      let deleteCalled = false
      await apiMocks.delete(
        `**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}`,
        () => {
          deleteCalled = true
          return { detail: 'ok' }
        },
      )

      await page.goto(`/organization/${ORG_ID}/orbit/${ORBIT_ID}`)

      await page.locator('.orbit-popover-wrapper .menu-link').click()
      const activeRow = page.locator('.orbit-popover-wrapper .orbit-item.active')
      await activeRow.getByRole('button').last().click()

      const dialog = page
        .getByRole('dialog')
        .filter({ has: page.getByText('orbit settings', { exact: true }) })
      await dialog.getByRole('button', { name: /delete Orbit/i }).click()
      const confirmBtn = page
        .getByRole('button', { name: /^(delete|confirm|yes|accept)$/i })
        .first()
      await confirmBtn.click()

      await expect.poll(() => deleteCalled).toBe(true)
      await expect(page.getByText('Orbit successfully deleted')).toBeVisible()
    })
  })
})