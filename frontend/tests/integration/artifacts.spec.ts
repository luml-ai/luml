import { test, expect } from './fixtures/test'
import type { ApiMocks } from './fixtures/api-mocks'
import {
  ORG_ID,
  ORBIT_ID,
  COLLECTION_ID,
  ARTIFACT_ID,
  ARTIFACT_ID_2,
  ARTIFACT_ID_3,
  TRACK_ID,
  DEPLOYMENT_ID,
  DEPLOYMENT_ID_2,
  USER_FIXTURE,
  ORB_FULL_PERMISSIONS,
  Permission,
  ArtifactStatus,
  DeploymentStatus,
  makeOrganization,
  makeOrganizationDetails,
  makeMember,
  makeOrbit,
  makeOrbitDetails,
  makeBucketSecret,
  makeCollection,
  makeCollectionsListResponse,
  makeExtendedCollection,
  makeArtifact,
  makeArtifactDeleteFailure,
  makeArtifactDeleteUrl,
  makeArtifactsListResponse,
  makeDeployment,
} from './fixtures/data'

const FAKE_DELETE_URL = 'https://fake-bucket.test/artifact-delete'
const FAKE_DOWNLOAD_URL = 'https://fake-bucket.test/artifact-download'
const DELETE_URLS_ENDPOINT = `**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections/${COLLECTION_ID}/artifacts/delete-urls`
const CONFIRM_DELETE_ENDPOINT = `**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections/${COLLECTION_ID}/artifacts`

function bucketDeleteUrl(artifactId: string): string {
  return `${FAKE_DELETE_URL}/${artifactId}`
}

function generatedArtifactId(index: number): string {
  return `00000000-0000-4000-8000-${index.toString().padStart(12, '0')}`
}

async function mockArtifactsBaseline(apiMocks: ApiMocks) {
  await apiMocks.get('**/v1/auth/users/me', USER_FIXTURE)
  await apiMocks.get('**/v1/users/me/organizations', [makeOrganization()])
  await apiMocks.get('**/v1/users/me/invitations', [])

  await apiMocks.get(new RegExp(`/v1/organizations/${ORG_ID}/orbits(\\?|$)`), [makeOrbit()])
  await apiMocks.get(
    new RegExp(`/v1/organizations/${ORG_ID}(\\?|$)`),
    makeOrganizationDetails({ members: [makeMember()] }),
  )
  await apiMocks.get(
    new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}(\\?|$)`),
    makeOrbitDetails(),
  )
  await apiMocks.get(`**/v1/organizations/${ORG_ID}/bucket-secrets`, [makeBucketSecret()])

  await apiMocks.get(
    new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections(\\?|$)`),
    makeCollectionsListResponse([makeCollection()]),
  )

  await apiMocks.get(
    new RegExp(
      `/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections/${COLLECTION_ID}(\\?|$)`,
    ),
    makeExtendedCollection(),
  )

  await apiMocks.get(
    new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/artifacts(\\?|$)`),
    makeArtifactsListResponse([makeArtifact()]),
  )
}

const collectionPageUrl = `/organization/${ORG_ID}/orbit/${ORBIT_ID}/collection/${COLLECTION_ID}`
const artifactPageUrl = `${collectionPageUrl}/artifacts/${ARTIFACT_ID}`

test.describe.configure({ mode: 'serial' })

test.describe('Artifacts', () => {
  test.beforeEach(async ({ apiMocks }) => {
    await mockArtifactsBaseline(apiMocks)
  })

  test.describe('Deletion blockers', () => {
    test('shows deployment and track blockers with links', async ({ page, apiMocks }) => {
      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/artifacts(\\?|$)`),
        makeArtifactsListResponse([
          makeArtifact({ name: 'A' }),
          makeArtifact({ id: ARTIFACT_ID_2, name: 'B' }),
          makeArtifact({ id: ARTIFACT_ID_3, name: 'C' }),
        ]),
      )
      await apiMocks.post(DELETE_URLS_ENDPOINT, {
        urls: [makeArtifactDeleteUrl(ARTIFACT_ID, 'A', bucketDeleteUrl(ARTIFACT_ID))],
        failed: [
          makeArtifactDeleteFailure({
            artifact_id: ARTIFACT_ID_2,
            name: 'B',
            reason: 'deployments',
            deployments: [
              { id: DEPLOYMENT_ID, name: 'old', status: DeploymentStatus.failed },
              {
                id: DEPLOYMENT_ID_2,
                name: 'stuck',
                status: DeploymentStatus.deletion_failed,
              },
            ],
          }),
          makeArtifactDeleteFailure({
            artifact_id: ARTIFACT_ID_3,
            name: 'C',
            reason: 'tracks',
            tracks: [{ id: TRACK_ID, name: 'release' }],
          }),
        ],
      })
      await apiMocks.delete(bucketDeleteUrl(ARTIFACT_ID), { status: 204, body: '' })
      await apiMocks.delete(CONFIRM_DELETE_ENDPOINT, {
        deleted: [ARTIFACT_ID],
        failed: [],
      })

      await page.goto(collectionPageUrl)
      await page.locator('.p-datatable-thead input[type="checkbox"]').first().check()
      await page.locator('.toolbar-left button').nth(0).click()
      await page
        .getByRole('alertdialog')
        .getByRole('button', { name: /^delete artifacts$/i })
        .click()

      const dialog = page
        .getByRole('dialog')
        .filter({ has: page.getByText('Some artifacts were not deleted', { exact: true }) })
      await expect(dialog).toContainText(
        'Used by deployments: old (failed), stuck (deletion_failed). Delete the deployments first.',
      )
      await expect(dialog).toContainText(
        'Linked to tracks: release. Unlink the artifact from the tracks first.',
      )
      await expect(dialog.getByRole('link', { name: 'old' })).toHaveAttribute(
        'href',
        `/organization/${ORG_ID}/orbit/${ORBIT_ID}/deployments?deployment=${DEPLOYMENT_ID}`,
      )
      await expect(dialog.getByRole('link', { name: 'stuck' })).toHaveAttribute(
        'href',
        `/organization/${ORG_ID}/orbit/${ORBIT_ID}/deployments?deployment=${DEPLOYMENT_ID_2}`,
      )
      await expect(dialog.getByRole('link', { name: 'release' })).toHaveAttribute(
        'href',
        `/organization/${ORG_ID}/orbit/${ORBIT_ID}/tracks/${TRACK_ID}`,
      )
      await expect(dialog.getByRole('button', { name: /^force delete$/i })).toHaveCount(0)
      await expect(page.getByText('Artifact "A" deleted')).toBeVisible()
      await expect(page.getByText('A', { exact: true })).toHaveCount(0)
      await expect(page.getByText('B', { exact: true })).toBeVisible()
      await expect(page.getByText('C', { exact: true })).toBeVisible()
    })

    test('sends an actively deployed artifact with the selection and reports its blocker', async ({
      page,
      apiMocks,
    }) => {
      const ids = [ARTIFACT_ID, ARTIFACT_ID_2]
      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/artifacts(\\?|$)`),
        makeArtifactsListResponse([
          makeArtifact({ name: 'A' }),
          makeArtifact({
            id: ARTIFACT_ID_2,
            name: 'B',
            deployments: [
              makeDeployment({
                id: DEPLOYMENT_ID,
                artifact_id: ARTIFACT_ID_2,
                artifact_name: 'B',
                name: 'api',
                status: DeploymentStatus.active,
              }),
            ],
          }),
        ]),
      )
      let requestPayload: unknown
      await apiMocks.post(DELETE_URLS_ENDPOINT, (request: { postDataJSON: () => unknown }) => {
        requestPayload = request.postDataJSON()
        return {
          urls: [makeArtifactDeleteUrl(ARTIFACT_ID, 'A', bucketDeleteUrl(ARTIFACT_ID))],
          failed: [
            makeArtifactDeleteFailure({
              artifact_id: ARTIFACT_ID_2,
              name: 'B',
              reason: 'deployments',
              deployments: [{ id: DEPLOYMENT_ID, name: 'api', status: DeploymentStatus.active }],
            }),
          ],
        }
      })
      await apiMocks.delete(bucketDeleteUrl(ARTIFACT_ID), { status: 204, body: '' })
      await apiMocks.delete(CONFIRM_DELETE_ENDPOINT, {
        deleted: [ARTIFACT_ID],
        failed: [],
      })

      await page.goto(collectionPageUrl)
      await page.locator('.p-datatable-thead input[type="checkbox"]').first().check()
      await page.locator('.toolbar-left button').nth(0).click()
      await page
        .getByRole('alertdialog')
        .getByRole('button', { name: /^delete artifacts$/i })
        .click()

      await expect.poll(() => requestPayload).toEqual({ artifact_ids: ids })
      await expect(page.getByText('Artifact "A" deleted')).toBeVisible()
      const dialog = page
        .getByRole('dialog')
        .filter({ has: page.getByText('Artifact was not deleted', { exact: true }) })
      await expect(dialog).toContainText(
        'Used by deployments: api (active). Delete the deployments first.',
      )
      await expect(dialog.getByRole('link', { name: 'api' })).toHaveAttribute(
        'href',
        `/organization/${ORG_ID}/orbit/${ORBIT_ID}/deployments?deployment=${DEPLOYMENT_ID}`,
      )
      await expect(page.getByText('B', { exact: true })).toBeVisible()
    })

    test('removes a stale not-found row without reporting or counting it', async ({
      page,
      apiMocks,
    }) => {
      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/artifacts(\\?|$)`),
        makeArtifactsListResponse([
          makeArtifact({ name: 'A' }),
          makeArtifact({ id: ARTIFACT_ID_2, name: 'B' }),
        ]),
      )
      await apiMocks.post(DELETE_URLS_ENDPOINT, {
        urls: [makeArtifactDeleteUrl(ARTIFACT_ID, 'A', bucketDeleteUrl(ARTIFACT_ID))],
        failed: [
          makeArtifactDeleteFailure({
            artifact_id: ARTIFACT_ID_2,
            name: null,
            reason: 'not_found',
          }),
        ],
      })
      await apiMocks.delete(bucketDeleteUrl(ARTIFACT_ID), { status: 204, body: '' })
      await apiMocks.delete(CONFIRM_DELETE_ENDPOINT, {
        deleted: [ARTIFACT_ID],
        failed: [],
      })

      await page.goto(collectionPageUrl)
      await page.locator('.p-datatable-thead input[type="checkbox"]').first().check()
      await page.getByRole('button', { name: 'Delete', exact: true }).click()
      await page
        .getByRole('alertdialog')
        .getByRole('button', { name: /^delete artifacts$/i })
        .click()

      await expect(page.getByText('Artifact "A" deleted')).toBeVisible()
      await expect(page.getByText('A', { exact: true })).toHaveCount(0)
      await expect(page.getByText('B', { exact: true })).toHaveCount(0)
      await expect(page.getByRole('dialog')).toHaveCount(0)
    })

    test('deletes a tracked artifact after it is unlinked on the track page', async ({
      page,
      apiMocks,
    }) => {
      const entryId = generatedArtifactId(999)
      let deletionRequests = 0
      let unlinkRequests = 0
      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}(\\?|$)`),
        makeOrbitDetails({
          permissions: {
            ...ORB_FULL_PERMISSIONS,
            track: [
              Permission.list,
              Permission.read,
              Permission.create,
              Permission.update,
              Permission.delete,
            ],
          },
        }),
      )
      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/artifacts(\\?|$)`),
        makeArtifactsListResponse([makeArtifact({ id: ARTIFACT_ID_3, name: 'C' })]),
      )
      await apiMocks.post(DELETE_URLS_ENDPOINT, () => {
        deletionRequests += 1
        if (deletionRequests === 1) {
          return {
            urls: [],
            failed: [
              makeArtifactDeleteFailure({
                artifact_id: ARTIFACT_ID_3,
                name: 'C',
                reason: 'tracks',
                tracks: [{ id: TRACK_ID, name: 'release' }],
              }),
            ],
          }
        }
        return {
          urls: [makeArtifactDeleteUrl(ARTIFACT_ID_3, 'C', bucketDeleteUrl(ARTIFACT_ID_3))],
          failed: [],
        }
      })
      await apiMocks.delete(bucketDeleteUrl(ARTIFACT_ID_3), { status: 204, body: '' })
      await apiMocks.delete(CONFIRM_DELETE_ENDPOINT, {
        deleted: [ARTIFACT_ID_3],
        failed: [],
      })
      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/tracks/${TRACK_ID}(\\?|$)`),
        {
          id: TRACK_ID,
          orbit_id: ORBIT_ID,
          name: 'release',
          artifact_type: 'model',
          description: null,
          tags: [],
          created_by: 'Owner User',
          next_version: 2,
          total_entries: 1,
          created_at: '2025-03-01T00:00:00.000Z',
          updated_at: null,
        },
      )
      await apiMocks.get(
        new RegExp(
          `/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/tracks/${TRACK_ID}/stages(\\?|$)`,
        ),
        [],
      )
      await apiMocks.get(
        new RegExp(
          `/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/tracks/${TRACK_ID}/entries(\\?|$)`,
        ),
        {
          items: [
            {
              id: entryId,
              track_id: TRACK_ID,
              artifact_id: ARTIFACT_ID_3,
              artifact_collection_id: COLLECTION_ID,
              version: 1,
              stage_id: null,
              added_by: USER_FIXTURE.id,
              created_at: '2025-03-01T00:00:00.000Z',
              updated_at: null,
              artifact_name: 'C',
              artifact_description: null,
              stage_name: null,
            },
          ],
          cursor: null,
        },
      )
      await apiMocks.delete(
        `**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/tracks/${TRACK_ID}/entries/${entryId}`,
        () => {
          unlinkRequests += 1
          return { detail: 'Artifact unlinked' }
        },
      )

      await page.goto(collectionPageUrl)
      await page.locator('.p-datatable-tbody tr').first().locator('input[type="checkbox"]').check()
      await page.getByRole('button', { name: 'Delete' }).click()
      await page
        .getByRole('alertdialog')
        .getByRole('button', { name: /^delete artifact$/i })
        .click()
      const resultDialog = page
        .getByRole('dialog')
        .filter({ has: page.getByText('Artifact was not deleted', { exact: true }) })
      const trackHref = await resultDialog
        .getByRole('link', { name: 'release' })
        .getAttribute('href')
      await resultDialog.getByText('Close', { exact: true }).click()

      await page.goto(trackHref ?? '')
      await expect(page.getByRole('heading', { name: 'release' })).toBeVisible()
      await page.locator('.p-datatable-tbody tr').first().locator('input[type="checkbox"]').check()
      await page.locator('.toolbar-left button').first().click()
      await page
        .getByRole('alertdialog')
        .getByRole('button', { name: /^unlink artifact$/i })
        .click()
      await expect.poll(() => unlinkRequests).toBe(1)

      await page.goto(collectionPageUrl)
      await page.locator('.p-datatable-tbody tr').first().locator('input[type="checkbox"]').check()
      await page.getByRole('button', { name: 'Delete' }).click()
      await page
        .getByRole('alertdialog')
        .getByRole('button', { name: /^delete artifact$/i })
        .click()

      await expect.poll(() => deletionRequests).toBe(2)
      await expect(page.getByText('Artifact "C" deleted')).toBeVisible()
    })
  })

  test.describe('List', () => {
    test('renders artifacts table with data', async ({ page }) => {
      await page.goto(collectionPageUrl)

      await expect(page.getByRole('heading', { name: /Main Collection/i })).toBeVisible({
        timeout: 15000,
      })

      await expect(page.getByText('model-v1')).toBeVisible({ timeout: 10000 })
      await expect(page.getByText('Uploaded')).toBeVisible()
    })

    test('shows empty placeholder when there are no artifacts', async ({ page, apiMocks }) => {
      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/artifacts(\\?|$)`),
        makeArtifactsListResponse([]),
      )

      await page.goto(collectionPageUrl)
      await expect(page.getByRole('table')).toBeVisible()
      await expect(page.getByText('No artifacts to show. Add artifact to the table.')).toBeVisible({
        timeout: 10000,
      })
    })

    test('shows different status tags for different artifacts', async ({ page, apiMocks }) => {
      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/artifacts(\\?|$)`),
        makeArtifactsListResponse([
          makeArtifact(),
          makeArtifact({
            id: ARTIFACT_ID_2,
            name: 'failed-model',
            status: ArtifactStatus.upload_failed,
          }),
        ]),
      )

      await page.goto(collectionPageUrl)

      await expect(page.getByRole('button', { name: /Add artifact/i })).toBeVisible({
        timeout: 15000,
      })
      await expect(page.getByText('model-v1')).toBeVisible({ timeout: 10000 })
      await expect(page.getByText('failed-model')).toBeVisible()

      await expect(page.getByText('Uploaded').first()).toBeVisible()
      await expect(page.getByText('Upload failed').first()).toBeVisible()
    })
  })

  test.describe('Selection toolbar', () => {
    test('toolbar shows "0 Selected" when no artifact is selected', async ({ page }) => {
      await page.goto(collectionPageUrl)

      await expect(page.getByRole('button', { name: /Add artifact/i })).toBeVisible({
        timeout: 15000,
      })
      await expect(page.getByText('0 Selected')).toBeVisible({ timeout: 10000 })
    })

    test('selecting one artifact updates the selected counter', async ({ page }) => {
      await page.goto(collectionPageUrl)

      const firstCheckbox = page
        .locator('.p-datatable-tbody tr')
        .first()
        .locator('input[type="checkbox"]')
      await firstCheckbox.check()

      await expect(page.getByText('1 Selected')).toBeVisible()
    })
  })

  test.describe('Edit artifact', () => {
    test('renames an artifact via toolbar Settings', async ({ page, apiMocks }) => {
      let patchPayload: unknown = null
      await apiMocks.patch(
        `**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections/${COLLECTION_ID}/artifacts/${ARTIFACT_ID}`,
        (req: { postDataJSON: () => unknown }) => {
          patchPayload = req.postDataJSON()
          return makeArtifact({ name: 'renamed-model' })
        },
      )

      await page.goto(collectionPageUrl)

      await page.locator('.p-datatable-tbody tr').first().locator('input[type="checkbox"]').check()
      await expect(page.getByText('1 Selected')).toBeVisible()

      await page.locator('.toolbar-left button').nth(1).click()

      const dialog = page
        .getByRole('dialog')
        .filter({ has: page.getByText('Artifact settings', { exact: true }) })
      await expect(dialog).toBeVisible()

      await dialog.getByLabel('Name').fill('renamed-model')
      await dialog.getByRole('button', { name: 'save changes' }).click()

      await expect
        .poll(() => patchPayload)
        .toMatchObject({
          id: ARTIFACT_ID,
          name: 'renamed-model',
        })
      await expect(page.getByText('Artifact successfully updated')).toBeVisible()
    })
  })

  test.describe('Delete from artifact editor', () => {
    test('deletes the artifact and returns to its collection', async ({ page, apiMocks }) => {
      await apiMocks.get(
        `**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections/${COLLECTION_ID}/artifacts/${ARTIFACT_ID}`,
        makeArtifact(),
      )
      await apiMocks.post(DELETE_URLS_ENDPOINT, {
        urls: [makeArtifactDeleteUrl(ARTIFACT_ID, 'model-v1', bucketDeleteUrl(ARTIFACT_ID))],
        failed: [],
      })
      await apiMocks.delete(bucketDeleteUrl(ARTIFACT_ID), { status: 204, body: '' })
      await apiMocks.delete(CONFIRM_DELETE_ENDPOINT, {
        deleted: [ARTIFACT_ID],
        failed: [],
      })

      await page.goto(artifactPageUrl)
      await expect(page.getByText('Artifact details')).toBeVisible()
      await page.locator('.header > .toolbar').first().locator('button').first().click()
      const editor = page
        .getByRole('dialog')
        .filter({ has: page.getByText('Artifact settings', { exact: true }) })
      await editor.getByRole('button', { name: 'Delete artifact' }).click()
      await page
        .getByRole('alertdialog')
        .getByRole('button', { name: /^delete artifact$/i })
        .click()

      await expect(page.getByText('Artifact "model-v1" deleted')).toBeVisible()
      await expect(page).toHaveURL(new RegExp(`${collectionPageUrl}/?$`))
    })

    test('keeps the editor open and reports an active deployment blocker', async ({
      page,
      apiMocks,
    }) => {
      const artifact = makeArtifact({
        deployments: [
          makeDeployment({ id: DEPLOYMENT_ID, name: 'api', status: DeploymentStatus.active }),
        ],
      })
      await apiMocks.get(
        `**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections/${COLLECTION_ID}/artifacts/${ARTIFACT_ID}`,
        artifact,
      )
      await apiMocks.post(DELETE_URLS_ENDPOINT, {
        urls: [],
        failed: [
          makeArtifactDeleteFailure({
            reason: 'deployments',
            deployments: [{ id: DEPLOYMENT_ID, name: 'api', status: DeploymentStatus.active }],
          }),
        ],
      })

      await page.goto(artifactPageUrl)
      await expect(page.getByText('Artifact details')).toBeVisible()
      await page.locator('.header > .toolbar').first().locator('button').first().click()
      const editor = page
        .getByRole('dialog')
        .filter({ has: page.getByText('Artifact settings', { exact: true }) })
      await editor.getByRole('button', { name: 'Delete artifact' }).click()
      await page
        .getByRole('alertdialog')
        .getByRole('button', { name: /^delete artifact$/i })
        .click()

      const resultDialog = page
        .getByRole('dialog')
        .filter({ has: page.getByText('Artifact was not deleted', { exact: true }) })
      await expect(resultDialog).toContainText('api (active)')
      await expect(editor).toBeVisible()
      await expect(page).toHaveURL(artifactPageUrl)
    })

    test('keeps the editor open and links to a blocking track', async ({ page, apiMocks }) => {
      await apiMocks.get(
        `**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections/${COLLECTION_ID}/artifacts/${ARTIFACT_ID}`,
        makeArtifact({ tracks: [{ id: TRACK_ID, name: 'release' }] }),
      )
      await apiMocks.post(DELETE_URLS_ENDPOINT, {
        urls: [],
        failed: [
          makeArtifactDeleteFailure({
            reason: 'tracks',
            tracks: [{ id: TRACK_ID, name: 'release' }],
          }),
        ],
      })

      await page.goto(artifactPageUrl)
      await expect(page.getByText('Artifact details')).toBeVisible()
      await page.locator('.header > .toolbar').first().locator('button').first().click()
      const editor = page
        .getByRole('dialog')
        .filter({ has: page.getByText('Artifact settings', { exact: true }) })
      await editor.getByRole('button', { name: 'Delete artifact' }).click()
      await page
        .getByRole('alertdialog')
        .getByRole('button', { name: /^delete artifact$/i })
        .click()

      const resultDialog = page
        .getByRole('dialog')
        .filter({ has: page.getByText('Artifact was not deleted', { exact: true }) })
      await expect(resultDialog).toContainText(
        'Linked to tracks: release. Unlink the artifact from the tracks first.',
      )
      await expect(resultDialog.getByRole('link', { name: 'release' })).toHaveAttribute(
        'href',
        `/organization/${ORG_ID}/orbit/${ORBIT_ID}/tracks/${TRACK_ID}`,
      )
      await expect(editor).toBeVisible()
      await expect(page).toHaveURL(artifactPageUrl)
    })

    test('force deletes a deletion-failed artifact and returns to the collection', async ({
      page,
      apiMocks,
    }) => {
      await apiMocks.get(
        `**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections/${COLLECTION_ID}/artifacts/${ARTIFACT_ID}`,
        makeArtifact({ status: ArtifactStatus.deletion_failed }),
      )
      let confirmationPayload: unknown
      await apiMocks.delete(CONFIRM_DELETE_ENDPOINT, (request: { postDataJSON: () => unknown }) => {
        confirmationPayload = request.postDataJSON()
        return { deleted: [ARTIFACT_ID], failed: [] }
      })

      await page.goto(artifactPageUrl)
      await expect(page.getByText('Artifact details')).toBeVisible()
      await page.locator('.header > .toolbar').first().locator('button').first().click()
      const editor = page
        .getByRole('dialog')
        .filter({ has: page.getByText('Artifact settings', { exact: true }) })
      await editor.getByRole('button', { name: 'Delete artifact' }).click()
      const forceDialog = page
        .getByRole('dialog')
        .filter({ has: page.getByText('Delete this artifact?', { exact: true }) })
      await forceDialog.locator('input').fill('delete')
      await forceDialog.getByRole('button', { name: /^force delete$/i }).click()

      await expect
        .poll(() => confirmationPayload)
        .toEqual({
          artifact_ids: [ARTIFACT_ID],
          force: true,
        })
      await expect(page.getByText('Artifact "model-v1" deleted')).toBeVisible()
      await expect(page).toHaveURL(new RegExp(`${collectionPageUrl}/?$`))
    })
  })

  test.describe('Delete artifact', () => {
    test('deletes a single uploaded artifact via toolbar + confirm', async ({ page, apiMocks }) => {
      let deleteUrlPayload: unknown
      let confirmationPayload: unknown
      let bucketDeleteCalled = false

      await apiMocks.post(DELETE_URLS_ENDPOINT, (request: { postDataJSON: () => unknown }) => {
        deleteUrlPayload = request.postDataJSON()
        return {
          urls: [makeArtifactDeleteUrl(ARTIFACT_ID, 'model-v1', bucketDeleteUrl(ARTIFACT_ID))],
          failed: [],
        }
      })
      await apiMocks.delete(bucketDeleteUrl(ARTIFACT_ID), () => {
        bucketDeleteCalled = true
        return { status: 200, body: '' }
      })
      await apiMocks.delete(CONFIRM_DELETE_ENDPOINT, (request: { postDataJSON: () => unknown }) => {
        confirmationPayload = request.postDataJSON()
        return { deleted: [ARTIFACT_ID], failed: [] }
      })

      await page.goto(collectionPageUrl)

      await page.locator('.p-datatable-tbody tr').first().locator('input[type="checkbox"]').check()
      await expect(page.getByText('1 Selected')).toBeVisible()

      await page.locator('.toolbar-left button').nth(0).click()

      await page
        .getByRole('alertdialog')
        .getByRole('button', { name: /^delete artifact$/i })
        .click()

      await expect.poll(() => deleteUrlPayload).toEqual({ artifact_ids: [ARTIFACT_ID] })
      await expect.poll(() => bucketDeleteCalled).toBe(true)
      await expect
        .poll(() => confirmationPayload)
        .toEqual({
          artifact_ids: [ARTIFACT_ID],
          force: false,
        })
      await expect(page.getByText('Artifact "model-v1" deleted')).toBeVisible()
      await expect(page.getByText('0 Selected')).toBeVisible()
      await expect(page.getByText('model-v1', { exact: true })).not.toBeVisible()
    })

    test('deletes multiple artifacts at once', async ({ page, apiMocks }) => {
      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/artifacts(\\?|$)`),
        makeArtifactsListResponse([
          makeArtifact(),
          makeArtifact({ id: ARTIFACT_ID_2, name: 'model-v2' }),
        ]),
      )

      const ids = [ARTIFACT_ID, ARTIFACT_ID_2]
      let requestPayload: unknown
      let confirmationPayload: unknown
      let bucketDeletes = 0
      await apiMocks.post(DELETE_URLS_ENDPOINT, (request: { postDataJSON: () => unknown }) => {
        requestPayload = request.postDataJSON()
        return {
          urls: ids.map((id, index) =>
            makeArtifactDeleteUrl(id, index === 0 ? 'model-v1' : 'model-v2', bucketDeleteUrl(id)),
          ),
          failed: [],
        }
      })
      for (const id of ids) {
        await apiMocks.delete(bucketDeleteUrl(id), () => {
          bucketDeletes += 1
          return { status: 204, body: '' }
        })
      }
      await apiMocks.delete(CONFIRM_DELETE_ENDPOINT, (request: { postDataJSON: () => unknown }) => {
        confirmationPayload = request.postDataJSON()
        return { deleted: ids, failed: [] }
      })

      await page.goto(collectionPageUrl)
      await page.locator('.p-datatable-thead input[type="checkbox"]').first().check()
      await expect(page.getByText('2 Selected')).toBeVisible()

      await page.locator('.toolbar-left button').nth(0).click()
      await expect(page.getByRole('alertdialog')).toContainText('Delete 2 artifacts?')
      await page
        .getByRole('alertdialog')
        .getByRole('button', { name: /^delete artifacts$/i })
        .click()

      await expect.poll(() => requestPayload).toEqual({ artifact_ids: ids })
      await expect.poll(() => bucketDeletes).toBe(2)
      await expect.poll(() => confirmationPayload).toEqual({ artifact_ids: ids, force: false })
      await expect(page.getByText('2 artifacts deleted')).toBeVisible()
      await expect(page.getByText('0 Selected')).toBeVisible()
    })

    test('deletes more than one hundred selected artifacts in sequential chunks', async ({
      page,
      apiMocks,
    }) => {
      const artifacts = Array.from({ length: 130 }, (_, index) =>
        makeArtifact({ id: generatedArtifactId(index), name: `model-${index}` }),
      )
      const ids = artifacts.map(({ id }) => id)
      const requestChunks: string[][] = []
      const confirmationChunks: string[][] = []
      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/artifacts(\\?|$)`),
        makeArtifactsListResponse(artifacts),
      )
      await apiMocks.post(DELETE_URLS_ENDPOINT, (request: { postDataJSON: () => unknown }) => {
        const artifactIds = (request.postDataJSON() as { artifact_ids: string[] }).artifact_ids
        requestChunks.push(artifactIds)
        return {
          urls: artifactIds.map((id) => makeArtifactDeleteUrl(id, id, bucketDeleteUrl(id))),
          failed: [],
        }
      })
      await apiMocks.delete(new RegExp(`^${FAKE_DELETE_URL}/`), { status: 204, body: '' })
      await apiMocks.delete(CONFIRM_DELETE_ENDPOINT, (request: { postDataJSON: () => unknown }) => {
        const artifactIds = (request.postDataJSON() as { artifact_ids: string[] }).artifact_ids
        confirmationChunks.push(artifactIds)
        return { deleted: artifactIds, failed: [] }
      })

      await page.goto(collectionPageUrl)
      await page.locator('.p-datatable-thead input[type="checkbox"]').first().check()
      await expect(page.getByText('130 Selected')).toBeVisible()
      await page.getByRole('button', { name: 'Delete' }).click()
      await expect(page.getByRole('alertdialog')).toContainText('Delete 130 artifacts?')
      await page
        .getByRole('alertdialog')
        .getByRole('button', { name: /^delete artifacts$/i })
        .click()

      await expect.poll(() => requestChunks).toEqual([ids.slice(0, 100), ids.slice(100)])
      await expect.poll(() => confirmationChunks).toEqual([ids.slice(0, 100), ids.slice(100)])
      await expect(page.getByText('130 artifacts deleted')).toBeVisible()
      await expect(page.getByText('0 Selected')).toBeVisible()
    })
  })

  test.describe('Deletion failures', () => {
    test('retries a deletion-failed artifact in a mixed selection', async ({ page, apiMocks }) => {
      const ids = [ARTIFACT_ID, ARTIFACT_ID_2]
      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/artifacts(\\?|$)`),
        makeArtifactsListResponse([
          makeArtifact({ name: 'uploaded-model' }),
          makeArtifact({
            id: ARTIFACT_ID_2,
            name: 'failed-model',
            status: ArtifactStatus.deletion_failed,
          }),
        ]),
      )
      let requestPayload: unknown
      await apiMocks.post(DELETE_URLS_ENDPOINT, (request: { postDataJSON: () => unknown }) => {
        requestPayload = request.postDataJSON()
        return {
          urls: [
            makeArtifactDeleteUrl(ARTIFACT_ID, 'uploaded-model', bucketDeleteUrl(ARTIFACT_ID)),
            makeArtifactDeleteUrl(ARTIFACT_ID_2, 'failed-model', bucketDeleteUrl(ARTIFACT_ID_2)),
          ],
          failed: [],
        }
      })
      await apiMocks.delete(bucketDeleteUrl(ARTIFACT_ID), { status: 204, body: '' })
      await apiMocks.delete(bucketDeleteUrl(ARTIFACT_ID_2), { status: 204, body: '' })
      await apiMocks.delete(CONFIRM_DELETE_ENDPOINT, { deleted: ids, failed: [] })

      await page.goto(collectionPageUrl)
      await page.locator('.p-datatable-thead input[type="checkbox"]').first().check()
      await page.locator('.toolbar-left button').nth(0).click()
      const confirmation = page.getByRole('alertdialog')
      await expect(confirmation).toContainText('Delete 2 artifacts?')
      await confirmation.getByRole('button', { name: /^delete artifacts$/i }).click()

      await expect.poll(() => requestPayload).toEqual({ artifact_ids: ids })
      await expect(page.getByText('2 artifacts deleted')).toBeVisible()
    })

    test('does not force a mixed selection when one bucket deletion fails again', async ({
      page,
      apiMocks,
    }) => {
      const ids = [ARTIFACT_ID, ARTIFACT_ID_2]
      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/artifacts(\\?|$)`),
        makeArtifactsListResponse([
          makeArtifact({ name: 'A' }),
          makeArtifact({
            id: ARTIFACT_ID_2,
            name: 'B',
            status: ArtifactStatus.deletion_failed,
          }),
        ]),
      )
      let requestPayload: unknown
      let confirmationPayload: unknown
      await apiMocks.post(DELETE_URLS_ENDPOINT, (request: { postDataJSON: () => unknown }) => {
        requestPayload = request.postDataJSON()
        return {
          urls: [
            makeArtifactDeleteUrl(ARTIFACT_ID, 'A', bucketDeleteUrl(ARTIFACT_ID)),
            makeArtifactDeleteUrl(ARTIFACT_ID_2, 'B', bucketDeleteUrl(ARTIFACT_ID_2)),
          ],
          failed: [],
        }
      })
      await apiMocks.delete(bucketDeleteUrl(ARTIFACT_ID), { status: 204, body: '' })
      await apiMocks.delete(bucketDeleteUrl(ARTIFACT_ID_2), { status: 403, body: '' })
      await apiMocks.patch(
        `**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections/${COLLECTION_ID}/artifacts/${ARTIFACT_ID_2}`,
        makeArtifact({
          id: ARTIFACT_ID_2,
          name: 'B',
          status: ArtifactStatus.deletion_failed,
        }),
      )
      await apiMocks.delete(CONFIRM_DELETE_ENDPOINT, (request: { postDataJSON: () => unknown }) => {
        confirmationPayload = request.postDataJSON()
        return { deleted: [ARTIFACT_ID], failed: [] }
      })

      await page.goto(collectionPageUrl)
      await page.locator('.p-datatable-thead input[type="checkbox"]').first().check()
      await page.getByRole('button', { name: 'Delete' }).click()
      const confirmation = page.getByRole('alertdialog')
      await expect(confirmation).toContainText('Delete 2 artifacts?')
      await confirmation.getByRole('button', { name: /^delete artifacts$/i }).click()

      await expect.poll(() => requestPayload).toEqual({ artifact_ids: ids })
      await expect
        .poll(() => confirmationPayload)
        .toEqual({
          artifact_ids: [ARTIFACT_ID],
          force: false,
        })
      await expect(page.getByText('Artifact "A" deleted')).toBeVisible()
      const resultDialog = page
        .getByRole('dialog')
        .filter({ has: page.getByText('Artifact was not deleted', { exact: true }) })
      await expect(resultDialog).toContainText(
        'The file could not be deleted from the bucket. Try again, or force delete to remove the artifact and leave the file in the bucket.',
      )
      await expect(resultDialog.getByRole('button', { name: /^force delete$/i })).toBeVisible()
      await expect(page.getByText('Deletion failed')).toBeVisible()
    })

    test('deletes an upload-failed artifact through the normal flow when the object is missing', async ({
      page,
      apiMocks,
    }) => {
      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/artifacts(\\?|$)`),
        makeArtifactsListResponse([makeArtifact({ status: ArtifactStatus.upload_failed })]),
      )
      let confirmationPayload: unknown
      await apiMocks.post(DELETE_URLS_ENDPOINT, {
        urls: [makeArtifactDeleteUrl(ARTIFACT_ID, 'model-v1', bucketDeleteUrl(ARTIFACT_ID))],
        failed: [],
      })
      await apiMocks.delete(bucketDeleteUrl(ARTIFACT_ID), { status: 404, body: '' })
      await apiMocks.delete(CONFIRM_DELETE_ENDPOINT, (request: { postDataJSON: () => unknown }) => {
        confirmationPayload = request.postDataJSON()
        return { deleted: [ARTIFACT_ID], failed: [] }
      })

      await page.goto(collectionPageUrl)
      await page.locator('.p-datatable-tbody tr').first().locator('input[type="checkbox"]').check()
      await page.locator('.toolbar-left button').nth(0).click()
      await page
        .getByRole('alertdialog')
        .getByRole('button', { name: /^delete artifact$/i })
        .click()

      await expect
        .poll(() => confirmationPayload)
        .toEqual({
          artifact_ids: [ARTIFACT_ID],
          force: false,
        })
      await expect(page.getByText('Artifact "model-v1" deleted')).toBeVisible()
    })

    test('retries deletion-failed artifacts through the normal flow', async ({
      page,
      apiMocks,
    }) => {
      const ids = [ARTIFACT_ID, ARTIFACT_ID_2]
      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/artifacts(\\?|$)`),
        makeArtifactsListResponse([
          makeArtifact({ status: ArtifactStatus.deletion_failed }),
          makeArtifact({
            id: ARTIFACT_ID_2,
            name: 'model-v2',
            status: ArtifactStatus.deletion_failed,
          }),
        ]),
      )
      let deleteUrlRequests = 0
      let confirmationPayload: unknown
      await apiMocks.post(DELETE_URLS_ENDPOINT, () => {
        deleteUrlRequests += 1
        return {
          urls: ids.map((id, index) =>
            makeArtifactDeleteUrl(id, `model-v${index + 1}`, bucketDeleteUrl(id)),
          ),
          failed: [],
        }
      })
      for (const id of ids) {
        await apiMocks.delete(bucketDeleteUrl(id), { status: 204, body: '' })
      }
      await apiMocks.delete(CONFIRM_DELETE_ENDPOINT, (request: { postDataJSON: () => unknown }) => {
        confirmationPayload = request.postDataJSON()
        return { deleted: ids, failed: [] }
      })

      await page.goto(collectionPageUrl)
      await page.locator('.p-datatable-thead input[type="checkbox"]').first().check()
      await page.getByRole('button', { name: 'Delete' }).click()
      const dialog = page
        .getByRole('dialog')
        .filter({ has: page.getByText('Delete these artifacts?', { exact: true }) })
      await expect(dialog).toContainText('The file could not be deleted from the bucket last time.')
      await expect(dialog.getByRole('button', { name: /^force delete$/i })).toBeDisabled()
      await dialog.getByRole('button', { name: 'Try again' }).click()

      await expect.poll(() => deleteUrlRequests).toBe(1)
      await expect
        .poll(() => confirmationPayload)
        .toEqual({
          artifact_ids: ids,
          force: false,
        })
      await expect(page.getByText('2 artifacts deleted')).toBeVisible()
    })

    test('force deletes deletion-failed artifacts without requesting a URL', async ({
      page,
      apiMocks,
    }) => {
      const ids = [ARTIFACT_ID, ARTIFACT_ID_2]
      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/artifacts(\\?|$)`),
        makeArtifactsListResponse([
          makeArtifact({ status: ArtifactStatus.deletion_failed }),
          makeArtifact({
            id: ARTIFACT_ID_2,
            name: 'model-v2',
            status: ArtifactStatus.deletion_failed,
          }),
        ]),
      )
      let deleteUrlRequests = 0
      let bucketDeletes = 0
      let confirmationPayload: unknown
      page.on('request', (request) => {
        if (request.method() === 'POST' && request.url().endsWith('/artifacts/delete-urls')) {
          deleteUrlRequests += 1
        }
        if (request.method() === 'DELETE' && request.url().startsWith(FAKE_DELETE_URL)) {
          bucketDeletes += 1
        }
      })
      await apiMocks.delete(CONFIRM_DELETE_ENDPOINT, (request: { postDataJSON: () => unknown }) => {
        confirmationPayload = request.postDataJSON()
        return { deleted: ids, failed: [] }
      })

      await page.goto(collectionPageUrl)
      await page.locator('.p-datatable-thead input[type="checkbox"]').first().check()
      await page.getByRole('button', { name: 'Delete' }).click()
      const dialog = page
        .getByRole('dialog')
        .filter({ has: page.getByText('Delete these artifacts?', { exact: true }) })
      await expect(dialog.getByRole('button', { name: /^force delete$/i })).toBeDisabled()
      await dialog.locator('input').fill('delete')
      await dialog.getByRole('button', { name: /^force delete$/i }).click()

      await expect
        .poll(() => confirmationPayload)
        .toEqual({
          artifact_ids: ids,
          force: true,
        })
      expect(deleteUrlRequests).toBe(0)
      expect(bucketDeletes).toBe(0)
      await expect(page.getByText('2 artifacts deleted')).toBeVisible()
      await expect(page.getByText('0 Selected')).toBeVisible()
    })

    test('reports a blocker that appears before a forced confirmation', async ({
      page,
      apiMocks,
    }) => {
      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/artifacts(\\?|$)`),
        makeArtifactsListResponse([makeArtifact({ status: ArtifactStatus.deletion_failed })]),
      )
      let confirmationPayload: unknown
      let deleteUrlRequests = 0
      page.on('request', (request) => {
        if (request.method() === 'POST' && request.url().endsWith('/artifacts/delete-urls')) {
          deleteUrlRequests += 1
        }
      })
      await apiMocks.delete(CONFIRM_DELETE_ENDPOINT, (request: { postDataJSON: () => unknown }) => {
        confirmationPayload = request.postDataJSON()
        return {
          deleted: [],
          failed: [
            makeArtifactDeleteFailure({
              reason: 'tracks',
              tracks: [{ id: TRACK_ID, name: 'release' }],
            }),
          ],
        }
      })

      await page.goto(collectionPageUrl)
      await page.locator('.p-datatable-tbody tr').first().locator('input[type="checkbox"]').check()
      await page.getByRole('button', { name: 'Delete' }).click()
      const forceDialog = page
        .getByRole('dialog')
        .filter({ has: page.getByText('Delete this artifact?', { exact: true }) })
      await forceDialog.locator('input').fill('delete')
      await forceDialog.getByRole('button', { name: /^force delete$/i }).click()

      await expect
        .poll(() => confirmationPayload)
        .toEqual({
          artifact_ids: [ARTIFACT_ID],
          force: true,
        })
      expect(deleteUrlRequests).toBe(0)
      const resultDialog = page
        .getByRole('dialog')
        .filter({ has: page.getByText('Artifact was not deleted', { exact: true }) })
      await expect(resultDialog).toContainText(
        'Linked to tracks: release. Unlink the artifact from the tracks first.',
      )
      await expect(resultDialog.getByRole('button', { name: /^force delete$/i })).toHaveCount(0)
      await expect(page.getByText('Deletion failed')).toBeVisible()
      await expect(page.getByText('0 Selected')).toBeVisible()
    })

    test('offers force after a bucket refusal and force deletes only from the registry', async ({
      page,
      apiMocks,
    }) => {
      let deleteUrlRequests = 0
      let bucketDeletes = 0
      let statusPayload: unknown
      let forceConfirmationPayload: unknown
      await apiMocks.post(DELETE_URLS_ENDPOINT, () => {
        deleteUrlRequests += 1
        return {
          urls: [makeArtifactDeleteUrl(ARTIFACT_ID, 'model-v1', bucketDeleteUrl(ARTIFACT_ID))],
          failed: [],
        }
      })
      await apiMocks.delete(bucketDeleteUrl(ARTIFACT_ID), () => {
        bucketDeletes += 1
        return { status: 403, body: '' }
      })
      await apiMocks.patch(
        `**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections/${COLLECTION_ID}/artifacts/${ARTIFACT_ID}`,
        (request: { postDataJSON: () => unknown }) => {
          statusPayload = request.postDataJSON()
          return makeArtifact({ status: ArtifactStatus.deletion_failed })
        },
      )
      await apiMocks.delete(CONFIRM_DELETE_ENDPOINT, (request: { postDataJSON: () => unknown }) => {
        forceConfirmationPayload = request.postDataJSON()
        return { deleted: [ARTIFACT_ID], failed: [] }
      })

      await page.goto(collectionPageUrl)
      await page.locator('.p-datatable-tbody tr').first().locator('input[type="checkbox"]').check()
      await page.locator('.toolbar-left button').nth(0).click()
      await page
        .getByRole('alertdialog')
        .getByRole('button', { name: /^delete artifact$/i })
        .click()

      const resultDialog = page
        .getByRole('dialog')
        .filter({ has: page.getByText('Artifact was not deleted', { exact: true }) })
      await expect(resultDialog).toContainText(
        'The file could not be deleted from the bucket. Try again, or force delete to remove the artifact and leave the file in the bucket.',
      )
      await expect
        .poll(() => statusPayload)
        .toEqual({
          id: ARTIFACT_ID,
          status: ArtifactStatus.deletion_failed,
        })
      await resultDialog.getByRole('button', { name: /^force delete$/i }).click()

      const forceDialog = page
        .getByRole('dialog')
        .filter({ has: page.getByText('Force delete this artifact?', { exact: true }) })
      await forceDialog.locator('input').fill('delete')
      await forceDialog.getByRole('button', { name: /^force delete$/i }).click()

      await expect
        .poll(() => forceConfirmationPayload)
        .toEqual({
          artifact_ids: [ARTIFACT_ID],
          force: true,
        })
      expect(deleteUrlRequests).toBe(1)
      expect(bucketDeletes).toBe(1)
      await expect(page.getByText('Artifact "model-v1" deleted')).toBeVisible()
      await expect(resultDialog).not.toBeVisible()
    })

    test('keeps a storage failure retryable when its status update fails', async ({
      page,
      apiMocks,
    }) => {
      let bucketDeletes = 0
      let deleteUrlRequests = 0
      await apiMocks.post(DELETE_URLS_ENDPOINT, () => {
        deleteUrlRequests += 1
        return {
          urls: [makeArtifactDeleteUrl(ARTIFACT_ID, 'model-v1', bucketDeleteUrl(ARTIFACT_ID))],
          failed: [],
        }
      })
      await apiMocks.delete(bucketDeleteUrl(ARTIFACT_ID), () => {
        bucketDeletes += 1
        return bucketDeletes === 1 ? { status: 403, body: '' } : { status: 204, body: '' }
      })
      await apiMocks.patch(
        `**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections/${COLLECTION_ID}/artifacts/${ARTIFACT_ID}`,
        { status: 500, body: { detail: 'Status update unavailable' } },
      )
      await apiMocks.delete(CONFIRM_DELETE_ENDPOINT, {
        deleted: [ARTIFACT_ID],
        failed: [],
      })

      await page.goto(collectionPageUrl)
      await page.locator('.p-datatable-tbody tr').first().locator('input[type="checkbox"]').check()
      await page.getByRole('button', { name: 'Delete' }).click()
      await page
        .getByRole('alertdialog')
        .getByRole('button', { name: /^delete artifact$/i })
        .click()

      const resultDialog = page
        .getByRole('dialog')
        .filter({ has: page.getByText('Artifact was not deleted', { exact: true }) })
      await expect(resultDialog).toContainText(
        'The file could not be deleted from the bucket. Try again, or force delete to remove the artifact and leave the file in the bucket.',
      )
      await expect(page.getByText('Pending deletions')).toBeVisible()
      await resultDialog.getByText('Close', { exact: true }).click()

      await page.locator('.p-datatable-tbody tr').first().locator('input[type="checkbox"]').check()
      await page.getByRole('button', { name: 'Delete' }).click()
      await page
        .getByRole('alertdialog')
        .getByRole('button', { name: /^delete artifact$/i })
        .click()

      await expect.poll(() => deleteUrlRequests).toBe(2)
      await expect.poll(() => bucketDeletes).toBe(2)
      await expect(page.getByText('Artifact "model-v1" deleted')).toBeVisible()
    })
  })

  test.describe('Deletion request errors', () => {
    test('keeps all artifacts selected when the deletion request fails', async ({
      page,
      apiMocks,
    }) => {
      const artifacts = [ARTIFACT_ID, ARTIFACT_ID_2, ARTIFACT_ID_3].map((id, index) =>
        makeArtifact({ id, name: `model-${index + 1}` }),
      )
      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/artifacts(\\?|$)`),
        makeArtifactsListResponse(artifacts),
      )
      await apiMocks.post(DELETE_URLS_ENDPOINT, {
        status: 500,
        body: { detail: 'Registry unavailable' },
      })

      await page.goto(collectionPageUrl)
      await page.locator('.p-datatable-thead input[type="checkbox"]').first().check()
      await page.locator('.toolbar-left button').nth(0).click()
      await page
        .getByRole('alertdialog')
        .getByRole('button', { name: /^delete artifacts$/i })
        .click()

      await expect(page.getByText('Registry unavailable')).toBeVisible()
      await expect(page.getByText('3 Selected')).toBeVisible()
      await expect(page.getByText('model-1', { exact: true })).toBeVisible()
      await expect(page.getByRole('dialog')).not.toBeVisible()
    })

    test('retains only unclassified artifacts when confirmation fails', async ({
      page,
      apiMocks,
    }) => {
      const artifacts = [ARTIFACT_ID, ARTIFACT_ID_2, ARTIFACT_ID_3].map((id, index) =>
        makeArtifact({ id, name: `model-${index + 1}` }),
      )
      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/artifacts(\\?|$)`),
        makeArtifactsListResponse(artifacts),
      )
      await apiMocks.post(DELETE_URLS_ENDPOINT, {
        urls: [
          makeArtifactDeleteUrl(ARTIFACT_ID, 'model-1', bucketDeleteUrl(ARTIFACT_ID)),
          makeArtifactDeleteUrl(ARTIFACT_ID_3, 'model-3', bucketDeleteUrl(ARTIFACT_ID_3)),
        ],
        failed: [
          makeArtifactDeleteFailure({
            artifact_id: ARTIFACT_ID_2,
            name: 'model-2',
            reason: 'deployments',
            deployments: [{ id: DEPLOYMENT_ID, name: 'api', status: DeploymentStatus.active }],
          }),
        ],
      })
      await apiMocks.delete(bucketDeleteUrl(ARTIFACT_ID), { status: 204, body: '' })
      await apiMocks.delete(bucketDeleteUrl(ARTIFACT_ID_3), { status: 204, body: '' })
      await apiMocks.delete(CONFIRM_DELETE_ENDPOINT, {
        status: 500,
        body: { detail: 'Confirmation unavailable' },
      })

      await page.goto(collectionPageUrl)
      await page.locator('.p-datatable-thead input[type="checkbox"]').first().check()
      await page.locator('.toolbar-left button').nth(0).click()
      await page
        .getByRole('alertdialog')
        .getByRole('button', { name: /^delete artifacts$/i })
        .click()

      await expect(page.getByText('Confirmation unavailable')).toBeVisible()
      await expect(page.getByText('2 Selected')).toBeVisible()
      const dialog = page
        .getByRole('dialog')
        .filter({ has: page.getByText('Artifact was not deleted', { exact: true }) })
      await expect(dialog).toContainText('api (active)')
    })

    test('reports completed and retryable counts when a later chunk request fails', async ({
      page,
      apiMocks,
    }) => {
      const artifacts = Array.from({ length: 130 }, (_, index) =>
        makeArtifact({ id: generatedArtifactId(index), name: `model-${index}` }),
      )
      let requestCount = 0
      let confirmationCount = 0
      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/artifacts(\\?|$)`),
        makeArtifactsListResponse(artifacts),
      )
      await apiMocks.post(DELETE_URLS_ENDPOINT, (request: { postDataJSON: () => unknown }) => {
        requestCount += 1
        if (requestCount === 2) {
          return { status: 500, body: { detail: 'Registry unavailable' } }
        }
        const artifactIds = (request.postDataJSON() as { artifact_ids: string[] }).artifact_ids
        return {
          urls: artifactIds.map((id) => makeArtifactDeleteUrl(id, id, bucketDeleteUrl(id))),
          failed: [],
        }
      })
      await apiMocks.delete(new RegExp(`^${FAKE_DELETE_URL}/`), { status: 204, body: '' })
      await apiMocks.delete(CONFIRM_DELETE_ENDPOINT, (request: { postDataJSON: () => unknown }) => {
        confirmationCount += 1
        const artifactIds = (request.postDataJSON() as { artifact_ids: string[] }).artifact_ids
        return { deleted: artifactIds, failed: [] }
      })

      await page.goto(collectionPageUrl)
      await page.locator('.p-datatable-thead input[type="checkbox"]').first().check()
      await page.getByRole('button', { name: 'Delete' }).click()
      await page
        .getByRole('alertdialog')
        .getByRole('button', { name: /^delete artifacts$/i })
        .click()

      await expect(
        page.getByText('Registry unavailable. 100 artifacts deleted, 30 not completed'),
      ).toBeVisible()
      await expect(page.getByText('30 Selected')).toBeVisible()
      expect(requestCount).toBe(2)
      expect(confirmationCount).toBe(1)

      await page.getByRole('button', { name: 'Delete' }).click()
      await page
        .getByRole('alertdialog')
        .getByRole('button', { name: /^delete artifacts$/i })
        .click()

      await expect.poll(() => requestCount).toBe(3)
      await expect.poll(() => confirmationCount).toBe(2)
      await expect(page.getByText('30 artifacts deleted')).toBeVisible()
      await expect(page.getByText('0 Selected')).toBeVisible()
    })

    test('clears rows when a retry reports a lost confirmation as not found', async ({
      page,
      apiMocks,
    }) => {
      const artifacts = [
        makeArtifact({ name: 'A' }),
        makeArtifact({ id: ARTIFACT_ID_2, name: 'B' }),
        makeArtifact({ id: ARTIFACT_ID_3, name: 'C' }),
      ]
      const ids = artifacts.map(({ id }) => id)
      let requestCount = 0
      let bucketDeletes = 0
      let confirmationCount = 0
      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/artifacts(\\?|$)`),
        makeArtifactsListResponse(artifacts),
      )
      await apiMocks.post(DELETE_URLS_ENDPOINT, () => {
        requestCount += 1
        if (requestCount === 2) {
          return {
            urls: [],
            failed: ids.map((id) =>
              makeArtifactDeleteFailure({ artifact_id: id, name: null, reason: 'not_found' }),
            ),
          }
        }
        return {
          urls: artifacts.map(({ id, name }) =>
            makeArtifactDeleteUrl(id, name, bucketDeleteUrl(id)),
          ),
          failed: [],
        }
      })
      await apiMocks.delete(new RegExp(`^${FAKE_DELETE_URL}/`), () => {
        bucketDeletes += 1
        return { status: 204, body: '' }
      })
      await apiMocks.delete(CONFIRM_DELETE_ENDPOINT, () => {
        confirmationCount += 1
        return { status: 500, body: { detail: 'Confirmation unavailable' } }
      })

      await page.goto(collectionPageUrl)
      await page.locator('.p-datatable-thead input[type="checkbox"]').first().check()
      await page.getByRole('button', { name: 'Delete' }).click()
      await page
        .getByRole('alertdialog')
        .getByRole('button', { name: /^delete artifacts$/i })
        .click()

      await expect(page.getByText('Confirmation unavailable')).toBeVisible()
      await expect(page.getByText('3 Selected')).toBeVisible()
      await expect(page.getByText('Pending deletions').first()).toBeVisible()

      await page.getByRole('button', { name: 'Delete', exact: true }).click()
      await page
        .getByRole('alertdialog')
        .getByRole('button', { name: /^delete artifacts$/i })
        .click()

      await expect.poll(() => requestCount).toBe(2)
      expect(bucketDeletes).toBe(3)
      expect(confirmationCount).toBe(1)
      await expect(page.getByText('0 Selected')).toBeVisible()
      await expect(page.getByText('A', { exact: true })).toHaveCount(0)
      await expect(page.getByText('B', { exact: true })).toHaveCount(0)
      await expect(page.getByText('C', { exact: true })).toHaveCount(0)
      await expect(page.getByRole('dialog')).toHaveCount(0)
    })
  })

  test.describe('Deletion permissions', () => {
    test('hides deletion actions without artifact delete permission', async ({
      page,
      apiMocks,
    }) => {
      const permissions = {
        ...ORB_FULL_PERMISSIONS,
        artifact: [Permission.list, Permission.read, Permission.create, Permission.update],
      }
      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}(\\?|$)`),
        makeOrbitDetails({ permissions }),
      )
      await apiMocks.get(
        `**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections/${COLLECTION_ID}/artifacts/${ARTIFACT_ID}`,
        makeArtifact(),
      )

      await page.goto(collectionPageUrl)
      await expect(page.getByRole('button', { name: 'Delete' })).toHaveCount(0)

      await page.goto(artifactPageUrl)
      await expect(page.getByText('Artifact details')).toBeVisible()
      await page.locator('.header > .toolbar').first().locator('button').first().click()
      const editor = page
        .getByRole('dialog')
        .filter({ has: page.getByText('Artifact settings', { exact: true }) })
      await expect(editor.getByRole('button', { name: 'Delete artifact' })).toHaveCount(0)
    })
  })

  test.describe('Download', () => {
    test('downloads selected artifact file', async ({ page, apiMocks }) => {
      let downloadUrlRequested = false
      await apiMocks.get(
        `**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections/${COLLECTION_ID}/artifacts/${ARTIFACT_ID}/download-url`,
        () => {
          downloadUrlRequested = true
          return { url: FAKE_DOWNLOAD_URL }
        },
      )
      await apiMocks.get(FAKE_DOWNLOAD_URL, {
        status: 200,
        body: 'fake-file-content',
        headers: { 'content-type': 'application/octet-stream' },
      })

      await page.goto(collectionPageUrl)

      await expect(page.getByText('0 Selected')).toBeVisible()

      await page.locator('.p-datatable-tbody tr').first().locator('input[type="checkbox"]').check()
      await expect(page.getByText('1 Selected')).toBeVisible()

      await page.locator('.toolbar-left button').nth(2).click()

      await expect.poll(() => downloadUrlRequested, { timeout: 5000 }).toBe(true)
    })
  })

  test.describe('Create artifact form', () => {
    test('opens creator dialog from CollectionHeader', async ({ page }) => {
      await page.goto(collectionPageUrl)

      await page.getByRole('button', { name: /Add artifact/i }).click()

      const dialog = page.getByRole('dialog').filter({ has: page.getByText(/add a new artifact/i) })
      await expect(dialog).toBeVisible()
    })

    test('blocks submit when file is missing', async ({ page, apiMocks }) => {
      let createCalled = false
      await apiMocks.post(
        `**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections/${COLLECTION_ID}/artifacts`,
        () => {
          createCalled = true
          return { artifact: makeArtifact(), upload_details: { url: 'ignored' } }
        },
      )

      await page.goto(collectionPageUrl)
      await page.getByRole('button', { name: /Add artifact/i }).click()

      const dialog = page.getByRole('dialog').filter({ has: page.getByText(/add a new artifact/i) })

      await dialog.getByLabel('Name').fill('no-file-artifact')
      await dialog.getByRole('button', { name: 'Add', exact: true }).click()

      await page.waitForTimeout(500)
      expect(createCalled).toBe(false)
    })
  })
})
