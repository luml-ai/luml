import { test, expect } from './fixtures/test'
import type { ApiMocks } from './fixtures/api-mocks'
import {
  ORG_ID,
  ORG_ID_2,
  USER_ID,
  USER_ID_2,
  MEMBER_ID,
  MEMBER_ID_2,
  INVITE_ID,
  USER_FIXTURE,
  OrganizationRole,
  makeOrganization,
  makeOrganizationDetails,
  makeMember,
  makeInvitation,
} from './fixtures/data'

async function mockAuthenticatedBaseline(apiMocks: ApiMocks) {
  await apiMocks.get('**/v1/auth/users/me', USER_FIXTURE)
  await apiMocks.get('**/v1/users/me/organizations', [makeOrganization()])
  await apiMocks.get('**/v1/users/me/invitations', [])

  await apiMocks.get(`**/v1/organizations/${ORG_ID}/orbits`, [])
  await apiMocks.get(`**/v1/organizations/${ORG_ID_2}/orbits`, [])

  await apiMocks.get(`**/v1/organizations/${ORG_ID}`, makeOrganizationDetails())
  await apiMocks.get(`**/v1/organizations/${ORG_ID_2}`, makeOrganizationDetails({ id: ORG_ID_2, name: 'Second Org' }))
}

test.describe('Organizations', () => {
  test.beforeEach(async ({ apiMocks }) => {
    await mockAuthenticatedBaseline(apiMocks)
  })

  test.describe('Organization switcher (popover)', () => {
    test('shows current organization name and the list of available ones', async ({
      page,
      apiMocks,
    }) => {
      await apiMocks.get('**/v1/users/me/organizations', [
        makeOrganization(),
        makeOrganization({ id: ORG_ID_2, name: 'Second Org' }),
      ])

      await page.goto('/')

      const trigger = page.locator('.menu-link').filter({ hasText: 'Acme Corp' })
      await expect(trigger).toBeVisible()

      await trigger.click()

      await expect(page.getByText('Switch to Organization')).toBeVisible()
      const list = page.locator('.list-scroll')
      await expect(list.getByRole('button', { name: 'Acme Corp' })).toBeVisible()
      await expect(list.getByRole('button', { name: 'Second Org' })).toBeVisible()

      await expect(page.getByRole('button', { name: 'Create new' })).toBeVisible()
    })

    test('switches active organization', async ({ page, apiMocks }) => {
      await apiMocks.get('**/v1/users/me/organizations', [
        makeOrganization(),
        makeOrganization({ id: ORG_ID_2, name: 'Second Org' }),
      ])

      await page.goto('/')
      await page.locator('.menu-link').filter({ hasText: 'Acme Corp' }).click()

      const detailsRequest = page.waitForRequest(
        (req) => req.url().includes(`/v1/organizations/${ORG_ID_2}`) && req.method() === 'GET',
      )
      await page.getByRole('button', { name: 'Second Org' }).click()
      await detailsRequest

      await expect(
        page.locator('.menu-link').filter({ hasText: 'Second Org' }),
      ).toBeVisible()
    })

    test('switching organization on settings page updates URL and content', async ({
      page,
      apiMocks,
    }) => {
      await apiMocks.get('**/v1/users/me/organizations', [
        makeOrganization(),
        makeOrganization({ id: ORG_ID_2, name: 'Second Org' }),
      ])

      const firstOrgDetails = makeOrganizationDetails({
        orbits: [
          {
            id: 'orbit-a1',
            name: 'First Org Orbit',
            organization_id: ORG_ID,
            bucket_secret_id: 'bs-1',
            total_members: 1,
            total_collections: 0,
            total_satellites: 0,
            total_artifacts: 0,
            role: 'admin',
            created_at: '2025-01-01T00:00:00.000Z',
            updated_at: null,
            permissions: {},
          },
        ],
      })

      const secondOrgDetails = makeOrganizationDetails({
        id: ORG_ID_2,
        name: 'Second Org',
        orbits: [
          {
            id: 'orbit-b1',
            name: 'Second Org Orbit',
            organization_id: ORG_ID_2,
            bucket_secret_id: 'bs-2',
            total_members: 1,
            total_collections: 0,
            total_satellites: 0,
            total_artifacts: 0,
            role: 'admin',
            created_at: '2025-01-01T00:00:00.000Z',
            updated_at: null,
            permissions: {},
          },
        ],
      })

      await apiMocks.get(`**/v1/organizations/${ORG_ID}`, firstOrgDetails)
      await apiMocks.get(`**/v1/organizations/${ORG_ID_2}`, secondOrgDetails)

      await page.goto(`/organization/${ORG_ID}/orbits-list`)

      const orbitsTable = page.locator('.users-list')
      await expect(orbitsTable.getByText('First Org Orbit')).toBeVisible()
      await expect(orbitsTable.getByText('Second Org Orbit')).toBeHidden()

      await page.locator('.menu-link').filter({ hasText: 'Acme Corp' }).click()
      await page.locator('.list-scroll').getByRole('button', { name: 'Second Org' }).click()

      await expect(page).toHaveURL(new RegExp(`/organization/${ORG_ID_2}/orbits-list$`))

      await expect(orbitsTable.getByText('Second Org Orbit')).toBeVisible()
      await expect(orbitsTable.getByText('First Org Orbit')).toBeHidden()

      await expect(
        page.locator('.menu-link').filter({ hasText: 'Second Org' }),
      ).toBeVisible()
    })
  })


  test.describe('Create organization', () => {
    test('creates a new organization with a valid name', async ({ page, apiMocks }) => {
      let createPayload: unknown = null
      await apiMocks.post('**/v1/organizations', (req) => {
        createPayload = req.postDataJSON()
        return {
          id: ORG_ID_2,
          name: 'New Org',
          logo: 'https://framerusercontent.com/images/Ks0qcMuaRUt9YEMHOZIkAAXLwl0.png',
          created_at: '2025-03-01T00:00:00.000Z',
          updated_at: '2025-03-01T00:00:00.000Z',
        }
      })

      await apiMocks.get('**/v1/users/me/organizations', [
        makeOrganization(),
        makeOrganization({ id: ORG_ID_2, name: 'New Org' }),
      ])

      await page.goto('/')
      await page.locator('.menu-link').filter({ hasText: 'Acme Corp' }).click()
      await page.getByRole('button', { name: 'Create new' }).click()

      await expect(page.getByRole('heading', { name: /Create a new Organization/i })).toBeVisible()

      await page.getByLabel('Name').fill('New Org')
      await page.getByRole('button', { name: 'Create', exact: true }).click()

      await expect.poll(() => createPayload).toMatchObject({ name: 'New Org' })
      await expect(page.getByText('All changes have been saved.')).toBeVisible()
    })

    test('blocks create when name is shorter than 3 characters', async ({ page, apiMocks }) => {
      let createCalled = false
      await apiMocks.post('**/v1/organizations', () => {
        createCalled = true
        return { id: ORG_ID_2, name: 'x', logo: '', created_at: '', updated_at: '' }
      })

      await page.goto('/')
      await page.locator('.menu-link').filter({ hasText: 'Acme Corp' }).click()
      await page.getByRole('button', { name: 'Create new' }).click()

      await page.getByLabel('Name').fill('ab')
      await page.getByRole('button', { name: 'Create', exact: true }).click()

      await page.waitForTimeout(500)
      expect(createCalled).toBe(false)
    })
  })


  test.describe('Edit organization', () => {
    test('updates organization name', async ({ page, apiMocks }) => {
      let patchPayload: unknown = null
      await apiMocks.patch(`**/v1/organizations/${ORG_ID}`, (req) => {
        patchPayload = req.postDataJSON()
        return makeOrganizationDetails({ name: 'Renamed Org' })
      })

      await page.goto(`/organization/${ORG_ID}`)

      await page.locator('.edit-button').click()
      await expect(page.getByRole('heading', { name: /Organization settings/i })).toBeVisible()

      const nameInput = page.getByLabel('Name')
      await nameInput.fill('Renamed Org')
      await page.getByRole('button', { name: 'save changes' }).click()

      await expect.poll(() => patchPayload).toMatchObject({ name: 'Renamed Org' })
      await expect(page.getByText('All changes have been saved.')).toBeVisible()
    })
  })


  test.describe('Delete organization', () => {
    test('delete button is disabled until the confirmation checkbox is checked', async ({
      page,
    }) => {
      await page.goto(`/organization/${ORG_ID}`)
      await page.locator('.edit-button').click()
      await page.getByRole('button', { name: /delete organization/i }).click()

      await expect(page.getByText('Delete this organization?')).toBeVisible()

      const deleteBtn = page.getByRole('button', { name: 'delete', exact: true })
      await expect(deleteBtn).toBeDisabled()

      await page.getByLabel(/Yes, delete this organization/i).check()
      await expect(deleteBtn).toBeEnabled()
    })

    test('deletes the organization after confirmation and redirects home', async ({
      page,
      apiMocks,
    }) => {
      let deleteCalled = false
      await apiMocks.delete(`**/v1/organizations/${ORG_ID}`, () => {
        deleteCalled = true
        return { detail: 'Organization deleted' }
      })

      await page.goto(`/organization/${ORG_ID}`)
      await page.locator('.edit-button').click()
      await page.getByRole('button', { name: /delete organization/i }).click()
      await page.getByLabel(/Yes, delete this organization/i).check()
      await page.getByRole('button', { name: 'delete', exact: true }).click()

      await expect.poll(() => deleteCalled).toBe(true)
      await expect(page).toHaveURL(/\/$/)
    })
  })


  test.describe('Leave organization', () => {
    test('leaves current organization after confirm dialog', async ({ page, apiMocks }) => {
      await apiMocks.get('**/v1/users/me/organizations', [makeOrganization()])

      let leaveCalled = false
      await apiMocks.delete(`**/v1/organizations/${ORG_ID}/leave`, () => {
        leaveCalled = true
        return { detail: 'ok' }
      })

      await page.goto('/')
      await page.locator('.menu-link').filter({ hasText: 'Acme Corp' }).click()

      const orgRow = page.locator('.organization').filter({ hasText: 'Acme Corp' })
      await orgRow.getByRole('button').last().click() 

      const confirmBtn = page
        .getByRole('button', { name: /^(leave|yes|confirm|accept)$/i })
        .first()
      await confirmBtn.click()

      await expect.poll(() => leaveCalled).toBe(true)
    })
  })


  test.describe('Invites', () => {
    test('creates an invite with valid email and role', async ({ page, apiMocks }) => {
      let createPayload: unknown = null
      await apiMocks.post(`**/v1/organizations/${ORG_ID}/invitations`, (req) => {
        createPayload = req.postDataJSON()
        return makeInvitation({ email: 'new@example.com' })
      })

      await page.goto(`/organization/${ORG_ID}`)

      await page.getByRole('button', { name: /Invite member/i }).click()
      const dialog = page.getByRole('dialog', { name: 'Invite member' })
      await expect(dialog).toBeVisible()

      await page.getByPlaceholder('Email').fill('new@example.com')
      await page.getByRole('button', { name: 'Invite', exact: true }).click()

      await expect.poll(() => createPayload).toMatchObject({
        email: 'new@example.com',
        organization_id: ORG_ID,
      })
      await expect(
        page.getByText('An email invitation was sent to the user.'),
      ).toBeVisible()
    })

    test('shows validation error for invalid email', async ({ page, apiMocks }) => {
      let createCalled = false
      await apiMocks.post(`**/v1/organizations/${ORG_ID}/invitations`, () => {
        createCalled = true
        return makeInvitation()
      })

      await page.goto(`/organization/${ORG_ID}`)
      await page.getByRole('button', { name: /Invite member/i }).click()

      await page.getByPlaceholder('Email').fill('not-an-email')
      await page.getByRole('button', { name: 'Invite', exact: true }).click()

      await expect(page.getByText('Please enter a valid email address')).toBeVisible()
      await page.waitForTimeout(300)
      expect(createCalled).toBe(false)
    })

    test('cancels (deletes) a pending invite', async ({ page, apiMocks }) => {
      await apiMocks.get(
        `**/v1/organizations/${ORG_ID}`,
        makeOrganizationDetails({ invites: [makeInvitation()] }),
      )

      let deleteCalled = false
      await apiMocks.delete(
        `**/v1/organizations/${ORG_ID}/invitations/${INVITE_ID}`,
        () => {
          deleteCalled = true
          return { detail: 'ok' }
        },
      )

      await page.goto(`/organization/${ORG_ID}`)

      await page.getByRole('button', { name: /Manage invites/i }).click()
      await expect(page.getByText('invitee@example.com')).toBeVisible()

      const row = page
        .locator('.table-row')
        .filter({ hasText: 'invitee@example.com' })
      await row.getByRole('button').click()

      await expect.poll(() => deleteCalled).toBe(true)
    })
  })


  test.describe('Members', () => {
    test('lists members with correct role counts', async ({ page, apiMocks }) => {
      await apiMocks.get(
        `**/v1/organizations/${ORG_ID}`,
        makeOrganizationDetails({
          members: [
            makeMember(), 
            makeMember({
              id: MEMBER_ID_2,
              role: OrganizationRole.member,
              user: { ...USER_FIXTURE, id: USER_ID_2, full_name: 'Plain Member', email: 'plain@example.com' },
            }),
          ],
          members_by_role: { owner: 1, admin: 0, member: 1 },
        }),
      )

      await page.goto(`/organization/${ORG_ID}`)

      await expect(page.getByRole('heading', { name: /Members \(2\)/i })).toBeVisible()
      const list = page.locator('.users-list')
      await expect(list.getByText('Owner User')).toBeVisible()
      await expect(list.getByText('Plain Member')).toBeVisible()
    })

    test('removes a member via user settings dialog', async ({ page, apiMocks }) => {
      await apiMocks.get(
        `**/v1/organizations/${ORG_ID}`,
        makeOrganizationDetails({
          members: [
            makeMember(),
            makeMember({
              id: MEMBER_ID_2,
              role: OrganizationRole.member,
              user: { ...USER_FIXTURE, id: USER_ID_2, full_name: 'Plain Member', email: 'plain@example.com' },
            }),
          ],
        }),
      )

      let deleteCalled = false
      await apiMocks.delete(
        `**/v1/organizations/${ORG_ID}/members/${MEMBER_ID_2}`,
        () => {
          deleteCalled = true
          return { detail: 'ok' }
        },
      )

      await page.goto(`/organization/${ORG_ID}`)

      const memberRow = page.locator('.row').filter({ hasText: 'Plain Member' })
      await memberRow.getByRole('button').click()

      await expect(page.getByRole('heading', { name: /user settings/i })).toBeVisible()
      await page.getByRole('button', { name: /delete user/i }).click()

      const confirmBtn = page
        .getByRole('button', { name: /^(delete|yes|remove|confirm)$/i })
        .first()
      await confirmBtn.click()

      await expect.poll(() => deleteCalled).toBe(true)
    })
  })
})