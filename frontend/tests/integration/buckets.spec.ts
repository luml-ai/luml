import { test, expect } from './fixtures/test'
import type { ApiMocks } from './fixtures/api-mocks'
import {
  ORG_ID,
  BUCKET_ID,
  USER_FIXTURE,
  BUCKET_PRESIGNED_URL,
  BUCKET_DOWNLOAD_URL,
  BUCKET_DELETE_URL,
  makeOrganization,
  makeOrganizationDetails,
  makeMember,
  makeBucketSecret,
  makeAzureBucketSecret,
  makeBucketConnectionUrls,
} from './fixtures/data'

async function mockBucketsBaseline(apiMocks: ApiMocks) {
  await apiMocks.get('**/v1/auth/users/me', USER_FIXTURE)
  await apiMocks.get('**/v1/users/me/organizations', [makeOrganization()])
  await apiMocks.get('**/v1/users/me/invitations', [])
  await apiMocks.get(`**/v1/organizations/${ORG_ID}/orbits`, [])

  await apiMocks.get(
    `**/v1/organizations/${ORG_ID}`,
    makeOrganizationDetails({ members: [makeMember()] }),
  )

  await apiMocks.get(
    `**/v1/organizations/${ORG_ID}/bucket-secrets`,
    [makeBucketSecret()],
  )

  await apiMocks.post('**/bucket-secrets/urls', makeBucketConnectionUrls())
  await apiMocks.post(
    `**/v1/organizations/${ORG_ID}/bucket-secrets/${BUCKET_ID}/urls`,
    makeBucketConnectionUrls(),
  )

  await apiMocks.put(BUCKET_PRESIGNED_URL, { status: 200, body: '' })

  await apiMocks.get(BUCKET_DOWNLOAD_URL, (req: { headers: () => { (): any; new(): any;[x: string]: any } }) => {
    const hasRange = req.headers()['range']
    return {
      status: hasRange ? 206 : 200,
      body: 'ok',
      headers: { 'content-type': 'text/plain' },
    }
  })

  await apiMocks.delete(BUCKET_DELETE_URL, { status: 200, body: '' })
}

async function gotoBucketsTab(page: import('@playwright/test').Page) {
  await page.goto(`/organization/${ORG_ID}/buckets`)
}

test.describe('Bucket Secrets', () => {
  test.beforeEach(async ({ apiMocks }) => {
    await mockBucketsBaseline(apiMocks)
  })


  test.describe('List', () => {
    test('renders existing buckets in the table', async ({ page }) => {
      await gotoBucketsTab(page)

      await expect(
        page.getByRole('heading', { name: /List of Buckets for current organization \(1\)/i }),
      ).toBeVisible()

      const table = page.locator('.table-wrapper')
      await expect(table.getByText('main-bucket')).toBeVisible()
      await expect(table.getByText('s3.amazonaws.com')).toBeVisible()
    })

    test('shows empty placeholder when there are no buckets', async ({ page, apiMocks }) => {
      await apiMocks.get(`**/v1/organizations/${ORG_ID}/bucket-secrets`, [])

      await gotoBucketsTab(page)

      await expect(
        page.getByText('No buckets created for this organization.'),
      ).toBeVisible()
    })
  })

  test.describe('Create S3 bucket', () => {
    test('creates a new S3 bucket with a valid form', async ({ page, apiMocks }) => {
      let createPayload: unknown = null
      await apiMocks.post(`**/v1/organizations/${ORG_ID}/bucket-secrets`, (req: { postDataJSON: () => unknown }) => {
        createPayload = req.postDataJSON()
        return makeBucketSecret({ id: 'new-bucket', bucket_name: 'new-s3-bucket' })
      })

      await gotoBucketsTab(page)

      await page.getByRole('button', { name: /New bucket/i }).click()

      const dialog = page.getByRole('dialog').filter({
        has: page.getByText('Add a new storage bucket'),
      })
      await expect(dialog).toBeVisible()

      await dialog.getByLabel('Endpoint').fill('s3.amazonaws.com')
      await dialog.getByLabel('Bucket name').fill('new-s3-bucket')
      await dialog.getByLabel('Access key').fill('AKIATEST')
      await dialog.getByLabel('Secret key').fill('SECRETTEST')
      await dialog.getByLabel('Region').fill('us-east-1')
      await dialog.getByRole('button', { name: 'Create', exact: true }).click()

      await expect.poll(() => createPayload).toMatchObject({
        type: 's3',
        bucket_name: 'new-s3-bucket',
        endpoint: 's3.amazonaws.com',
        region: 'us-east-1',
        access_key: 'AKIATEST',
        secret_key: 'SECRETTEST',
      })
      await expect(page.getByText('New bucket has been added.')).toBeVisible()
    })

    test('blocks create with empty required fields', async ({ page, apiMocks }) => {
      let createCalled = false
      await apiMocks.post(`**/v1/organizations/${ORG_ID}/bucket-secrets`, () => {
        createCalled = true
        return makeBucketSecret()
      })

      await gotoBucketsTab(page)

      await page.getByRole('button', { name: /New bucket/i }).click()
      const dialog = page.getByRole('dialog').filter({
        has: page.getByText('Add a new storage bucket'),
      })

      await dialog.getByRole('button', { name: 'Create', exact: true }).click()

      await expect(page.getByText('Please enter a valid endpoint URL')).toBeVisible()
      await expect(page.getByText('Please enter a name for the bucket')).toBeVisible()

      await page.waitForTimeout(300)
      expect(createCalled).toBe(false)
    })

    test('shows error toast when connection check fails', async ({ page, apiMocks }) => {
      await apiMocks.get(BUCKET_DOWNLOAD_URL, (req: { headers: () => { (): any; new(): any;[x: string]: any } }) => {
        const hasRange = req.headers()['range']
        return { status: hasRange ? 500 : 200, body: 'fail' }
      })

      let createCalled = false
      await apiMocks.post(`**/v1/organizations/${ORG_ID}/bucket-secrets`, () => {
        createCalled = true
        return makeBucketSecret()
      })

      await gotoBucketsTab(page)

      await page.getByRole('button', { name: /New bucket/i }).click()
      const dialog = page.getByRole('dialog').filter({
        has: page.getByText('Add a new storage bucket'),
      })

      await dialog.getByLabel('Endpoint').fill('s3.amazonaws.com')
      await dialog.getByLabel('Bucket name').fill('broken-bucket')
      await dialog.getByLabel('Region').fill('us-east-1')
      await dialog.getByRole('button', { name: 'Create', exact: true }).click()

      await expect(page.getByText(/Range requests are not supported/i)).toBeVisible()
      expect(createCalled).toBe(false)
    })
  })

  test.describe('Create Azure bucket', () => {
    test('switches form to Azure and creates a new Azure bucket', async ({
      page,
      apiMocks,
    }) => {
      let createPayload: unknown = null
      await apiMocks.post(`**/v1/organizations/${ORG_ID}/bucket-secrets`, (req: { postDataJSON: () => unknown }) => {
        createPayload = req.postDataJSON()
        return makeAzureBucketSecret({ id: 'new-azure', bucket_name: 'new-container' })
      })

      await gotoBucketsTab(page)

      await page.getByRole('button', { name: /New bucket/i }).click()
      const dialog = page.getByRole('dialog').filter({
        has: page.getByText('Add a new storage bucket'),
      })

      await dialog.getByRole('button', { name: 'Azure', exact: true }).click()

      await dialog.getByLabel('Container name').fill('new-container')
      await dialog
        .getByLabel('Connection string')
        .fill('DefaultEndpointsProtocol=https;AccountName=acme;AccountKey=fake==')
      await dialog.getByRole('button', { name: 'Create', exact: true }).click()

      await expect.poll(() => createPayload).toMatchObject({
        type: 'azure',
        bucket_name: 'new-container',
      })
      await expect(page.getByText('New bucket has been added.')).toBeVisible()
    })

    test('blocks Azure create with empty required fields', async ({ page, apiMocks }) => {
      let createCalled = false
      await apiMocks.post(`**/v1/organizations/${ORG_ID}/bucket-secrets`, () => {
        createCalled = true
        return makeAzureBucketSecret()
      })

      await gotoBucketsTab(page)

      await page.getByRole('button', { name: /New bucket/i }).click()
      const dialog = page.getByRole('dialog').filter({
        has: page.getByText('Add a new storage bucket'),
      })

      await dialog.getByRole('button', { name: 'Azure', exact: true }).click()
      await dialog.getByRole('button', { name: 'Create', exact: true }).click()

      await expect(page.getByText('Please enter a valid container name')).toBeVisible()
      await expect(page.getByText('Please enter a valid connection string')).toBeVisible()

      await page.waitForTimeout(300)
      expect(createCalled).toBe(false)
    })
  })


  test.describe('Edit S3 bucket', () => {
    test('updates an existing bucket', async ({ page, apiMocks }) => {
      let patchPayload: unknown = null
      await apiMocks.patch(
        `**/v1/organizations/${ORG_ID}/bucket-secrets/${BUCKET_ID}`,
        (req: { postDataJSON: () => unknown }) => {
          patchPayload = req.postDataJSON()
          return makeBucketSecret({ bucket_name: 'renamed-bucket' })
        },
      )

      await gotoBucketsTab(page)

      const row = page.locator('.simple-table__row').filter({ hasText: 'main-bucket' })
      await row.getByRole('button').click()

      const dialog = page
        .getByRole('dialog')
        .filter({ has: page.getByText('bucket settings', { exact: true }) })
      await expect(dialog).toBeVisible()

      await dialog.getByLabel('Bucket name').fill('renamed-bucket')
      await dialog.getByRole('button', { name: 'save changes' }).click()

      await expect.poll(() => patchPayload).toMatchObject({
        bucket_name: 'renamed-bucket',
      })
      await expect(page.getByText('Bucket has been updated.')).toBeVisible()
    })
  })


  test.describe('Delete bucket', () => {
    test('deletes a bucket after confirm dialog', async ({ page, apiMocks }) => {
      let deleteCalled = false
      await apiMocks.delete(
        `**/v1/organizations/${ORG_ID}/bucket-secrets/${BUCKET_ID}`,
        () => {
          deleteCalled = true
          return { detail: 'ok' }
        },
      )

      await gotoBucketsTab(page)

      const row = page.locator('.simple-table__row').filter({ hasText: 'main-bucket' })
      await row.getByRole('button').click()

      const dialog = page
        .getByRole('dialog')
        .filter({ has: page.getByText('bucket settings', { exact: true }) })
      await dialog.getByRole('button', { name: /delete bucket/i }).click()

      const confirmBtn = page
        .getByRole('button', { name: /^(delete|yes|confirm|accept)$/i })
        .first()
      await confirmBtn.click()

      await expect.poll(() => deleteCalled).toBe(true)
      await expect(page.getByText(/was deleted\./i)).toBeVisible()
    })
  })
})