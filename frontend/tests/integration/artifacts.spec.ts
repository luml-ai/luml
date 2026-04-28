import { test, expect } from './fixtures/test'
import type { ApiMocks } from './fixtures/api-mocks'
import {
  ORG_ID,
  ORBIT_ID,
  COLLECTION_ID,
  ARTIFACT_ID,
  ARTIFACT_ID_2,
  USER_FIXTURE,
  ArtifactStatus,
  ArtifactType,
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
  makeArtifactsListResponse,
} from './fixtures/data'

const FAKE_DELETE_URL = 'https://fake-bucket.test/artifact-delete'
const FAKE_DOWNLOAD_URL = 'https://fake-bucket.test/artifact-download'

async function mockArtifactsBaseline(apiMocks: ApiMocks) {
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
    new RegExp(
      `/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections/${COLLECTION_ID}/artifacts(\\?|$)`,
    ),
    makeArtifactsListResponse([makeArtifact()]),
  )
}

const collectionPageUrl = `/organization/${ORG_ID}/orbit/${ORBIT_ID}/collection/${COLLECTION_ID}`

test.describe.configure({ mode: 'serial' })

test.describe('Artifacts', () => {
  test.beforeEach(async ({ apiMocks }) => {
    await mockArtifactsBaseline(apiMocks)
  })


  test.describe('List', () => {
    test('renders artifacts table with data', async ({ page }) => {
      await page.goto(collectionPageUrl)

      await expect(
        page.getByRole('heading', { name: /Main Collection/i }),
      ).toBeVisible({ timeout: 15000 })


      await expect(page.getByText('model-v1')).toBeVisible({ timeout: 10000 })
      await expect(page.getByText('Uploaded')).toBeVisible()
    })

    test('shows empty placeholder when there are no artifacts', async ({ page, apiMocks }) => {
      await apiMocks.get(
        new RegExp(
          `/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections/${COLLECTION_ID}/artifacts(\\?|$)`,
        ),
        makeArtifactsListResponse([]),
      )

      await page.goto(collectionPageUrl)
      await expect(page.getByRole('table')).toBeVisible()
      await expect(
        page.getByText('No artifacts to show. Add artifact to the table.'),
      ).toBeVisible({ timeout: 10000 })
    })

    test('shows different status tags for different artifacts', async ({ page, apiMocks }) => {
      await apiMocks.get(
        new RegExp(
          `/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections/${COLLECTION_ID}/artifacts(\\?|$)`,
        ),
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

      await expect(
        page.getByRole('button', { name: /Add artifact/i }),
      ).toBeVisible({ timeout: 15000 })
      await expect(page.getByText('model-v1')).toBeVisible({ timeout: 10000 })
      await expect(page.getByText('failed-model')).toBeVisible()

      await expect(page.getByText('Uploaded').first()).toBeVisible()
      await expect(page.getByText('Upload failed').first()).toBeVisible()
    })
  })

  test.describe('Selection toolbar', () => {
    test('toolbar shows "0 Selected" when no artifact is selected', async ({ page }) => {
      await page.goto(collectionPageUrl)

      await expect(
        page.getByRole('button', { name: /Add artifact/i }),
      ).toBeVisible({ timeout: 15000 })
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

      await expect.poll(() => patchPayload).toMatchObject({
        id: ARTIFACT_ID,
        name: 'renamed-model',
      })
      await expect(page.getByText('Artifact successfully updated')).toBeVisible()
    })
  })


  test.describe('Delete artifact', () => {
    test('deletes a single uploaded artifact via toolbar + confirm', async ({
      page,
      apiMocks,
    }) => {
      let getDeleteUrlCalled = false
      let confirmDeleteCalled = false
      let bucketDeleteCalled = false

      await apiMocks.get(
        `**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections/${COLLECTION_ID}/artifacts/${ARTIFACT_ID}/delete-url`,
        () => {
          getDeleteUrlCalled = true
          return { url: FAKE_DELETE_URL }
        },
      )
  
      await apiMocks.delete(FAKE_DELETE_URL, () => {
        bucketDeleteCalled = true
        return { status: 200, body: '' }
      })

      await apiMocks.delete(
        `**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections/${COLLECTION_ID}/artifacts/${ARTIFACT_ID}`,
        () => {
          confirmDeleteCalled = true
          return { detail: 'ok' }
        },
      )

      await page.goto(collectionPageUrl)

      await page.locator('.p-datatable-tbody tr').first().locator('input[type="checkbox"]').check()
      await expect(page.getByText('1 Selected')).toBeVisible()

      await page.locator('.toolbar-left button').nth(0).click()

      await page
        .getByRole('alertdialog')
        .getByRole('button', { name: /^delete artifact$/i })
        .click()

      await expect.poll(() => getDeleteUrlCalled).toBe(true)
      await expect.poll(() => bucketDeleteCalled).toBe(true)
      await expect.poll(() => confirmDeleteCalled).toBe(true)
      await expect(page.getByText(/has been removed from the collection/i)).toBeVisible()
    })

    test('deletes multiple artifacts at once', async ({ page, apiMocks }) => {
      await apiMocks.get(
        new RegExp(
          `/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections/${COLLECTION_ID}/artifacts(\\?|$)`,
        ),
        makeArtifactsListResponse([
          makeArtifact(),
          makeArtifact({ id: ARTIFACT_ID_2, name: 'model-v2' }),
        ]),
      )

      const deletedIds: string[] = []
      for (const id of [ARTIFACT_ID, ARTIFACT_ID_2]) {
        await apiMocks.get(
          `**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections/${COLLECTION_ID}/artifacts/${id}/delete-url`,
          () => ({ url: FAKE_DELETE_URL }),
        )
        await apiMocks.delete(
          `**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections/${COLLECTION_ID}/artifacts/${id}`,
          () => {
            deletedIds.push(id)
            return { detail: 'ok' }
          },
        )
      }
      await apiMocks.delete(FAKE_DELETE_URL, { status: 200, body: '' })

      await page.goto(collectionPageUrl)


      await page.locator('.p-datatable-thead input[type="checkbox"]').first().check()
      await expect(page.getByText('2 Selected')).toBeVisible()

      await page.locator('.toolbar-left button').nth(0).click()
      await page
        .getByRole('alertdialog')
        .getByRole('button', { name: /^delete artifact/i })
        .click()

      await expect.poll(() => deletedIds.length, { timeout: 5000 }).toBe(2)
    })
  })


  test.describe('Force delete', () => {
    test('opens force delete dialog for upload-failed artifact', async ({ page, apiMocks }) => {
      await apiMocks.get(
        new RegExp(
          `/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections/${COLLECTION_ID}/artifacts(\\?|$)`,
        ),
        makeArtifactsListResponse([
          makeArtifact({ status: ArtifactStatus.upload_failed }),
        ]),
      )

      let forceDeleteCalled = false
      await apiMocks.delete(
        `**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections/${COLLECTION_ID}/artifacts/${ARTIFACT_ID}/force`,
        () => {
          forceDeleteCalled = true
          return { detail: 'ok' }
        },
      )

      await page.goto(collectionPageUrl)

      await page.locator('.p-datatable-tbody tr').first().locator('input[type="checkbox"]').check()
      await page.locator('.toolbar-left button').nth(0).click()
      const byDialog = page
        .getByRole('dialog')
        .filter({ has: page.getByText(/Force delete/i) })
      const byAlertDialog = page
        .getByRole('alertdialog')
        .filter({ has: page.getByText(/Force delete/i) })
      const forceDialog = byDialog.or(byAlertDialog)
      await expect(forceDialog).toBeVisible()
      await forceDialog.locator('input').fill('delete')
      await forceDialog.getByRole('button').last().click()

      await expect.poll(() => forceDeleteCalled).toBe(true)
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

      await page
        .locator('.p-datatable-tbody tr')
        .first()
        .locator('input[type="checkbox"]')
        .check()
      await expect(page.getByText('1 Selected')).toBeVisible()

      await page.locator('.toolbar-left button').nth(2).click()

      await expect.poll(() => downloadUrlRequested, { timeout: 5000 }).toBe(true)
    })
  })

 
  test.describe('Create artifact form', () => {
    test('opens creator dialog from CollectionHeader', async ({ page }) => {
      await page.goto(collectionPageUrl)

      await page.getByRole('button', { name: /Add artifact/i }).click()

      const dialog = page
        .getByRole('dialog')
        .filter({ has: page.getByText(/add a new artifact/i) })
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

      const dialog = page
        .getByRole('dialog')
        .filter({ has: page.getByText(/add a new artifact/i) })

      await dialog.getByLabel('Name').fill('no-file-artifact')
      await dialog.getByRole('button', { name: 'Add', exact: true }).click()

      await page.waitForTimeout(500)
      expect(createCalled).toBe(false)
    })
  })

})