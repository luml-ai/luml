import { test, expect } from './fixtures/test'
import type { ApiMocks } from './fixtures/api-mocks'
import {
  ORG_ID,
  ORG_ID_2,
  ORBIT_ID,
  ORBIT_ID_2,
  COLLECTION_ID,
  ARTIFACT_ID,
  DEPLOYMENT_ID,
  DEPLOYMENT_ID_2,
  USER_FIXTURE,
  DeploymentStatus,
  makeOrganization,
  makeOrganizationDetails,
  makeMember,
  makeOrbit,
  makeOrbitDetails,
  makeBucketSecret,
  makeArtifact,
  makeDeployment,
} from './fixtures/data'


async function mockDeploymentsBaseline(apiMocks: ApiMocks) {
  await apiMocks.get('**/v1/auth/users/me', USER_FIXTURE)
  await apiMocks.get('**/v1/users/me/organizations', [makeOrganization()])
  await apiMocks.get('**/v1/users/me/invitations', [])

  await apiMocks.get(
    new RegExp(`/v1/organizations/${ORG_ID}/orbits(\\?|$)`),
    [makeOrbit()],
  )
  await apiMocks.get(
    new RegExp(`/v1/organizations/${ORG_ID}(\\?|$)`),
    makeOrganizationDetails({ members: [makeMember()] }),
  )
  await apiMocks.get(
    new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}(\\?|$)`),
    makeOrbitDetails(),
  )
  await apiMocks.get(
    `**/v1/organizations/${ORG_ID}/bucket-secrets`,
    [makeBucketSecret()],
  )

  await apiMocks.get(
    new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/secrets(\\?|$)`),
    [],
  )

  await apiMocks.get(
    new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/deployments(\\?|$)`),
    [makeDeployment()],
  )

  await apiMocks.get(
    `**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections/${COLLECTION_ID}/artifacts/${ARTIFACT_ID}`,
    makeArtifact(),
  )
}

const deploymentsUrl = `/organization/${ORG_ID}/orbit/${ORBIT_ID}/deployments`

test.describe.configure({ mode: 'serial' })

test.describe('Deployments', () => {
  test.beforeEach(async ({ apiMocks }) => {
    await mockDeploymentsBaseline(apiMocks)
  })


  test.describe('List', () => {
    test('renders deployments table with data', async ({ page }) => {
      await page.goto(deploymentsUrl)

      await expect(
        page.getByRole('heading', { name: 'Deployments', exact: true }),
      ).toBeVisible({ timeout: 15000 })
      await expect(page.getByText('prod-deployment')).toBeVisible({ timeout: 10000 })
      await expect(page.getByText(/^1 Deployments$/)).toBeVisible()
    })

    test('shows empty state with "Add new Deployment" card when there are no deployments', async ({
      page,
      apiMocks,
    }) => {
      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/deployments(\\?|$)`),
        [],
      )

      await page.goto(deploymentsUrl)

      await expect(page.getByText('Add new Deployment')).toBeVisible({ timeout: 15000 })
      await expect(
        page.getByText('Instantly deploy models in a single click.'),
      ).toBeVisible()
    })
  })

  test.describe('Search', () => {
    test('filters deployments by global search', async ({ page, apiMocks }) => {
      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/deployments(\\?|$)`),
        [
          makeDeployment(),
          makeDeployment({
            id: DEPLOYMENT_ID_2,
            name: 'staging-deployment',
            tags: ['staging'],
          }),
        ],
      )

      await page.goto(deploymentsUrl)


      await expect(page.getByText('prod-deployment')).toBeVisible({ timeout: 15000 })
      await expect(page.getByText('staging-deployment')).toBeVisible()

      await page.getByPlaceholder('Search').fill('staging')

      await expect(page.getByText('staging-deployment')).toBeVisible()
      await expect(page.getByText('prod-deployment')).not.toBeVisible()
    })
  })


  test.describe('Status tags', () => {
    test('renders different status tags for different deployments', async ({
      page,
      apiMocks,
    }) => {
      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/deployments(\\?|$)`),
        [
          makeDeployment({ id: 'd-active', name: 'active-dep', status: DeploymentStatus.active }),
          makeDeployment({
            id: 'd-pending',
            name: 'pending-dep',
            status: DeploymentStatus.pending,
          }),
          makeDeployment({ id: 'd-failed', name: 'failed-dep', status: DeploymentStatus.failed }),
          makeDeployment({
            id: 'd-shutdown',
            name: 'shutdown-dep',
            status: DeploymentStatus.deletion_pending,
          }),
        ],
      )

      await page.goto(deploymentsUrl)

      await expect(page.getByText('active-dep')).toBeVisible({ timeout: 15000 })
      await expect(page.getByText('Active', { exact: true })).toBeVisible()
      await expect(page.getByText('Pending', { exact: true })).toBeVisible()
      await expect(page.getByText('Failed', { exact: true })).toBeVisible()
      await expect(page.getByText('Shutting down', { exact: true })).toBeVisible()
    })
  })



  test.describe('Edit deployment', () => {
    test('renames an active deployment via Editor', async ({ page, apiMocks }) => {
      let patchPayload: unknown = null
      await apiMocks.patch(
        `**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/deployments/${DEPLOYMENT_ID}`,
        (req) => {
          patchPayload = req.postDataJSON()
          return makeDeployment({ name: 'renamed-deployment' })
        },
      )

      await page.goto(deploymentsUrl)

      await expect(page.getByText('prod-deployment')).toBeVisible({ timeout: 15000 })
      const row = page
        .locator('.p-datatable-tbody tr')
        .filter({ hasText: 'prod-deployment' })

      await row.getByRole('button').last().click()

      const dialog = page
        .getByRole('dialog')
        .filter({ has: page.getByText('deployment settings', { exact: true }) })
      await expect(dialog).toBeVisible()

      await dialog.getByLabel('Name').fill('renamed-deployment')
      await dialog.getByRole('button', { name: 'save changes' }).click()

      await expect.poll(() => patchPayload).toMatchObject({
        name: 'renamed-deployment',
      })
      await expect(
        page.getByText('Deployment changes saved successfully.'),
      ).toBeVisible()
    })
  })

  test.describe('Soft delete', () => {
    test('stops an active deployment via DeploymentsDelete confirmation', async ({
      page,
      apiMocks,
    }) => {
      let deleteCalled = false
      await apiMocks.delete(
        `**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/deployments/${DEPLOYMENT_ID}`,
        () => {
          deleteCalled = true
          return makeDeployment({ status: DeploymentStatus.deletion_pending })
        },
      )

      await page.goto(deploymentsUrl)
      await expect(page.getByText('prod-deployment')).toBeVisible({ timeout: 15000 })

      const row = page
        .locator('.p-datatable-tbody tr')
        .filter({ hasText: 'prod-deployment' })
      await row.getByRole('button').last().click()

      const editor = page
        .getByRole('dialog')
        .filter({ has: page.getByText('deployment settings', { exact: true }) })
      await editor.getByRole('button', { name: /stop deployment/i }).click()

      const stopDialog = page
        .getByRole('dialog')
        .filter({ has: page.getByText('Stop this deployment?', { exact: true }) })
      await expect(stopDialog).toBeVisible()

      await stopDialog.getByLabel('Yes, stop this deployment').check()
      await stopDialog.getByRole('button', { name: 'stop', exact: true }).click()

      await expect.poll(() => deleteCalled).toBe(true)
      await expect(
        page.getByText(/is shutting down\./i),
      ).toBeVisible()
    })
  })


  test.describe('Force delete', () => {
    test('force deletes a failed deployment', async ({ page, apiMocks }) => {
      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/deployments(\\?|$)`),
        [makeDeployment({ status: DeploymentStatus.failed })],
      )

      let forceDeleteCalled = false
      await apiMocks.delete(
        `**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/deployments/${DEPLOYMENT_ID}/force`,
        () => {
          forceDeleteCalled = true
          return { detail: 'ok' }
        },
      )

      await page.goto(deploymentsUrl)
      await expect(page.getByText('prod-deployment')).toBeVisible({ timeout: 15000 })

      const row = page
        .locator('.p-datatable-tbody tr')
        .filter({ hasText: 'prod-deployment' })
      await row.getByRole('button').last().click()

      const editor = page
        .getByRole('dialog')
        .filter({ has: page.getByText('deployment settings', { exact: true }) })
      await editor.getByRole('button', { name: /force delete deployment/i }).click()

      const forceDialog = page.getByRole('dialog', {
        name: 'Force delete this deployment?',
      })
      await expect(forceDialog).toBeVisible()

      await forceDialog.locator('input').fill('delete')
      await forceDialog.getByRole('button').last().click()

      await expect.poll(() => forceDeleteCalled).toBe(true)
    })
  })

  test.describe('Tabs', () => {
    test('switches to Secrets tab', async ({ page }) => {
      await page.goto(deploymentsUrl)
      await expect(page.getByText('prod-deployment')).toBeVisible({ timeout: 15000 })

      await page
        .locator('button.tab')
        .filter({ hasText: 'Secrets' })
        .click()

      await expect(page.getByRole('button', { name: /Create secret/i })).toBeVisible()
    })
  })


  test.describe('Orbit switch', () => {
    test('switching orbit updates the URL and the deployments list', async ({
      page,
      apiMocks,
    }) => {
      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID}/orbits(\\?|$)`),
        [
          makeOrbit(),
          makeOrbit({ id: ORBIT_ID_2, name: 'Secondary Orbit' }),
        ],
      )

      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID_2}(\\?|$)`),
        makeOrbitDetails({ id: ORBIT_ID_2, name: 'Secondary Orbit' }),
      )

      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/deployments(\\?|$)`),
        [makeDeployment()],
      )
      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID_2}/deployments(\\?|$)`),
        [
          makeDeployment({
            id: DEPLOYMENT_ID_2,
            name: 'orbit-b-deployment',
            orbit_id: ORBIT_ID_2,
          }),
        ],
      )

      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID_2}/secrets(\\?|$)`),
        [],
      )

      await page.goto(deploymentsUrl)

      await expect(page.getByText('prod-deployment')).toBeVisible({ timeout: 15000 })

      await page
        .locator('.orbit-popover-wrapper .menu-link')
        .click()

      const popover = page.locator('.orbit-popover-wrapper .list-scroll')
      await popover.getByRole('button', { name: 'Secondary Orbit' }).click()

      await expect(page).toHaveURL(
        new RegExp(`/orbit/${ORBIT_ID_2}/deployments`),
      )
      await expect(page.getByText('orbit-b-deployment')).toBeVisible({ timeout: 10000 })
      await expect(page.getByText('prod-deployment')).not.toBeVisible()
    })
  })

  test.describe('Organization switch', () => {
    test('switching organization redirects to deployments of the first orbit in the new org', async ({
      page,
      apiMocks,
    }) => {
      await apiMocks.get('**/v1/users/me/organizations', [
        makeOrganization(),
        makeOrganization({ id: ORG_ID_2, name: 'Other Corp' }),
      ])

      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID_2}/orbits(\\?|$)`),
        [makeOrbit({ id: ORBIT_ID_2, name: 'Org B Orbit' })],
      )
      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID_2}(\\?|$)`),
        makeOrganizationDetails({ id: ORG_ID_2, name: 'Other Corp', members: [makeMember()] }),
      )
      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID_2}/orbits/${ORBIT_ID_2}(\\?|$)`),
        makeOrbitDetails({ id: ORBIT_ID_2, name: 'Org B Orbit' }),
      )
      await apiMocks.get(
        `**/v1/organizations/${ORG_ID_2}/bucket-secrets`,
        [],
      )

      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID_2}/orbits/${ORBIT_ID_2}/deployments(\\?|$)`),
        [
          makeDeployment({
            id: DEPLOYMENT_ID_2,
            name: 'org-b-deployment',
            orbit_id: ORBIT_ID_2,
          }),
        ],
      )
      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID_2}/orbits/${ORBIT_ID_2}/secrets(\\?|$)`),
        [],
      )

      await page.goto(deploymentsUrl)
      await expect(page.getByText('prod-deployment')).toBeVisible({ timeout: 15000 })

      await page
        .locator('.org-popover-wrapper .menu-link')
        .click()

      const popover = page.locator('.org-popover-wrapper .list-scroll')
      await popover.getByRole('button', { name: 'Other Corp' }).click()

      await expect(page).toHaveURL(
        new RegExp(`/organization/${ORG_ID_2}/orbit/${ORBIT_ID_2}/deployments`),
      )
      await expect(page.getByText('org-b-deployment')).toBeVisible({ timeout: 10000 })
      await expect(page.getByText('prod-deployment')).not.toBeVisible()
    })
  })
})