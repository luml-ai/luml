import { test, expect } from './fixtures/test'
import type { ApiMocks } from './fixtures/api-mocks'
import {
  ORG_ID,
  ORBIT_ID,
  COLLECTION_ID,
  COLLECTION_ID_2,
  USER_FIXTURE,
  CollectionType,
  makeOrganization,
  makeOrganizationDetails,
  makeMember,
  makeOrbit,
  makeOrbitDetails,
  makeBucketSecret,
  makeCollection,
  makeCollectionsListResponse,
} from './fixtures/data'

async function mockCollectionsBaseline(apiMocks: ApiMocks) {
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
    new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections`),
    makeCollectionsListResponse([makeCollection()]),
  )
}

const orbitRegistryUrl = `/organization/${ORG_ID}/orbit/${ORBIT_ID}`

test.describe('Collections', () => {
  test.beforeEach(async ({ apiMocks }) => {
    await mockCollectionsBaseline(apiMocks)
  })

  test.describe('List', () => {
    test('renders a populated collections list', async ({ page }) => {
      await page.goto(orbitRegistryUrl)

      await expect(
        page.getByRole('heading', { name: 'Registry', exact: true }),
      ).toBeVisible()
      await expect(page.getByText('Main Collection')).toBeVisible()
      await expect(page.getByText('production').first()).toBeVisible()
    })

    test('shows welcome state when there are no collections', async ({ page, apiMocks }) => {
      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections`),
        makeCollectionsListResponse([]),
      )

      await page.goto(orbitRegistryUrl)

      await expect(page.getByText('Welcome to the Registry')).toBeVisible()
      await expect(
        page.getByText(/Start by creating your first collection/i),
      ).toBeVisible()
    })
  })

  test.describe('Create collection', () => {
    const TYPE_CASES = [
      { type: CollectionType.dataset, optionLabel: 'Dataset', name: 'New Dataset Collection' },
      { type: CollectionType.model, optionLabel: 'Model', name: 'New Model Collection' },
      { type: CollectionType.mixed, optionLabel: 'Mixed', name: 'New Mixed Collection' },
    ] as const

    for (const { type, optionLabel, name } of TYPE_CASES) {
      test(`creates a new ${type} collection with valid data`, async ({ page, apiMocks }) => {
        let createPayload: unknown = null
        await apiMocks.post(
          `**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections`,
          (req: { postDataJSON: () => unknown }) => {
            createPayload = req.postDataJSON()
            return makeCollection({
              id: COLLECTION_ID_2,
              name,
              type,
              description: 'Brand new',
              tags: [],
            })
          },
        )

        await page.goto(orbitRegistryUrl)
        await page.getByRole('button', { name: /Create collection/i }).click()

        const dialog = page
          .getByRole('dialog')
          .filter({ has: page.getByText('Create a new collection', { exact: true }) })
        await expect(dialog).toBeVisible()

        await dialog.getByLabel('Name').fill(name)
        await dialog.locator('#type').click()
        await page
          .locator('.p-select-overlay, .p-select-panel, [role="listbox"]')
          .getByText(optionLabel, { exact: true })
          .first()
          .click()

        await dialog.getByLabel('Description').fill('Brand new')
        await dialog.getByRole('button', { name: 'Create', exact: true }).click()

        await expect.poll(() => createPayload).toMatchObject({
          name,
          type,
          description: 'Brand new',
        })
        await expect(page.getByText('Collection created')).toBeVisible()
      })
    }

    test('blocks create with empty name', async ({ page, apiMocks }) => {
      let createCalled = false
      await apiMocks.post(
        `**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections`,
        () => {
          createCalled = true
          return makeCollection()
        },
      )

      await page.goto(orbitRegistryUrl)
      await page.getByRole('button', { name: /Create collection/i }).click()

      const dialog = page
        .getByRole('dialog')
        .filter({ has: page.getByText('Create a new collection', { exact: true }) })
      await dialog.getByRole('button', { name: 'Create', exact: true }).click()

      await page.waitForTimeout(500)
      expect(createCalled).toBe(false)
    })
  })

  test.describe('Edit collection', () => {
    test('renames an existing collection', async ({ page, apiMocks }) => {
      let patchPayload: unknown = null
      await apiMocks.patch(
        `**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections/${COLLECTION_ID}`,
        (req: { postDataJSON: () => unknown }) => {
          patchPayload = req.postDataJSON()
          return makeCollection({ name: 'Renamed Collection' })
        },
      )

      await page.goto(orbitRegistryUrl)
      const card = page.locator('.card').filter({ hasText: 'Main Collection' })
      await card.locator('.right').getByRole('button').click()

      const dialog = page
        .getByRole('dialog')
        .filter({ has: page.getByText('Collection settings', { exact: true }) })
      await expect(dialog).toBeVisible()

      await dialog.getByLabel('Name').fill('Renamed Collection')
      await dialog.getByRole('button', { name: 'save changes' }).click()

      await expect.poll(() => patchPayload).toMatchObject({
        name: 'Renamed Collection',
      })
      await expect(page.getByText('Collection successfully updated')).toBeVisible()
    })
  })

  test.describe('Delete collection', () => {
    test('deletes the collection after confirm dialog', async ({ page, apiMocks }) => {
      let deleteCalled = false
      await apiMocks.delete(
        `**/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections/${COLLECTION_ID}`,
        () => {
          deleteCalled = true
          return { detail: 'ok' }
        },
      )

      await page.goto(orbitRegistryUrl)

      const card = page.locator('.card').filter({ hasText: 'Main Collection' })
      await card.locator('.right').getByRole('button').click()

      const dialog = page
        .getByRole('dialog')
        .filter({ has: page.getByText('Collection settings', { exact: true }) })
      await dialog.getByRole('button', { name: /delete collection/i }).click()

      const confirmBtn = page
        .getByRole('button', { name: /^(delete|confirm|yes|accept)$/i })
        .first()
      await confirmBtn.click()

      await expect.poll(() => deleteCalled).toBe(true)
      await expect(page.getByText(/was removed from the Registry/i)).toBeVisible()
    })
  })

  test.describe('Search', () => {
    test('triggers a search request after debounce', async ({ page, apiMocks }) => {
      const calls: Array<{ search?: string; types?: string }> = []
      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections`),
        (req: { url: () => string | URL }) => {
          const url = new URL(req.url())
          calls.push({
            search: url.searchParams.get('search') ?? undefined,
            types: url.searchParams.get('types') ?? undefined,
          })
          const name = url.searchParams.get('search') || 'Main Collection'
          return makeCollectionsListResponse([makeCollection({ name })])
        },
      )

      await page.goto(orbitRegistryUrl)

      const initialCallCount = calls.length

      await page.getByPlaceholder('Search').fill('production')

      await expect.poll(() => calls.length, { timeout: 3000 }).toBeGreaterThan(initialCallCount)

      await expect
        .poll(() => calls.some((c) => c.search === 'production'), { timeout: 3000 })
        .toBe(true)
    })
  })

  test.describe('Type filter', () => {
    test('filters collections by selected type', async ({ page, apiMocks }) => {
      const calls: Array<{ rawQuery: string }> = []
      await apiMocks.get(
        new RegExp(`/v1/organizations/${ORG_ID}/orbits/${ORBIT_ID}/collections`),
        (req: { url: () => string | URL }) => {
          const url = new URL(req.url())
          calls.push({ rawQuery: url.search })
          return makeCollectionsListResponse([makeCollection()])
        },
      )

      await page.goto(orbitRegistryUrl)
      const initialCallCount = calls.length
      await page
        .locator('.p-multiselect')
        .filter({ hasText: 'Filter by type' })
        .click()
      await page
        .locator('.p-multiselect-overlay, .p-multiselect-panel, [role="listbox"]')
        .getByText('Model', { exact: true })
        .first()
        .click()
      await page.keyboard.press('Escape')

      await expect
        .poll(() => calls.length, { timeout: 3000 })
        .toBeGreaterThan(initialCallCount)

      await expect
        .poll(
          () => calls.slice(initialCallCount).some((c) => c.rawQuery.includes('model')),
          { timeout: 3000 },
        )
        .toBe(true)
    })
  })
})