import type { Orbit } from '@/lib/api/api.interfaces'
import type { OrbitCollection } from '@/lib/api/orbit-collections/interfaces'
import { createPinia, setActivePinia } from 'pinia'
import { effectScope, nextTick, reactive } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  api: {
    createOrbit: vi.fn(),
    getOrbitDetails: vi.fn(),
    getOrganizationOrbits: vi.fn(),
    bucketSecrets: { getBucketSecretsList: vi.fn() },
  },
  push: vi.fn(),
  auth: { isAuth: true },
  organization: {
    currentOrganization: null as null | { id: string; permissions: { orbit: string[] } },
    organizationDetails: null,
  },
}))

vi.mock('@/lib/api', () => ({ api: mocks.api }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: mocks.push }) }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mocks.auth }))
vi.mock('@/stores/organization', async () => {
  const { reactive } = await import('vue')
  const store = reactive(mocks.organization)
  mocks.organization = store
  return { useOrganizationStore: () => store }
})

import { QuickStartStepEnum, useQuickStart } from '../useQuickStart'
import { useBucketsStore } from '@/stores/buckets'
import { useOrbitsStore } from '@/stores/orbits'

function orbit(id: string, totalCollections = 0) {
  return { id, name: id, total_collections: totalCollections } as Orbit
}

function bucket(id: string) {
  return { id }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => {
    resolve = done
  })
  return { promise, resolve }
}

function setOrganization(id: string, orbitPermissions = ['list', 'create']) {
  mocks.organization.currentOrganization = reactive({
    id,
    permissions: { orbit: orbitPermissions },
  })
}

let scope: ReturnType<typeof effectScope>

async function setup() {
  scope = effectScope()
  const quickStart = scope.run(() => useQuickStart())!
  await flushPromises()
  return quickStart
}

describe('useQuickStart', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mocks.auth.isAuth = true
    mocks.api.getOrbitDetails.mockResolvedValue({})
    mocks.api.getOrganizationOrbits.mockResolvedValue([])
    mocks.api.bucketSecrets.getBucketSecretsList.mockResolvedValue([])
    setOrganization('org-1')
  })

  afterEach(() => {
    scope?.stop()
  })

  describe('orbit permissions', () => {
    beforeEach(() => {
      mocks.api.bucketSecrets.getBucketSecretsList.mockResolvedValue([bucket('bucket-1')])
    })

    it('does not offer collection creation without an orbit when orbits cannot be created', async () => {
      setOrganization('org-1', ['list'])

      const { activeStep, runActiveStep, isCollectionDialogVisible } = await setup()
      runActiveStep()

      expect(activeStep.value).toBeNull()
      expect(isCollectionDialogVisible.value).toBe(false)
    })

    it('offers collection creation in an existing orbit without orbit create permission', async () => {
      setOrganization('org-1', ['list'])
      useOrbitsStore().orbitsList = [orbit('orbit-1')]

      const { activeStep } = await setup()

      expect(activeStep.value).toBe(QuickStartStepEnum.collection)
    })
  })

  describe('first collection from home', () => {
    beforeEach(() => {
      mocks.api.bucketSecrets.getBucketSecretsList.mockResolvedValue([bucket('bucket-1')])
      mocks.api.createOrbit.mockResolvedValue(orbit('default-orbit'))
    })

    it('creates a default orbit with the organization bucket', async () => {
      const { activeStep, resolveCollectionRequestInfo } = await setup()
      expect(activeStep.value).toBe(QuickStartStepEnum.collection)

      const info = await resolveCollectionRequestInfo()

      expect(mocks.api.createOrbit).toHaveBeenCalledWith('org-1', {
        name: 'Default Orbit',
        bucket_secret_id: 'bucket-1',
        members: [],
        notify: false,
      })
      expect(info).toEqual({ organizationId: 'org-1', orbitId: 'default-orbit' })
      expect(useOrbitsStore().currentOrbitId).toBe('default-orbit')
    })

    it('reuses an existing orbit instead of creating a new one', async () => {
      const orbitsStore = useOrbitsStore()
      orbitsStore.orbitsList = [orbit('orbit-1'), orbit('orbit-2')]
      orbitsStore.currentOrbitId = 'orbit-2'

      const { resolveCollectionRequestInfo } = await setup()
      const info = await resolveCollectionRequestInfo()

      expect(mocks.api.createOrbit).not.toHaveBeenCalled()
      expect(info).toEqual({ organizationId: 'org-1', orbitId: 'orbit-2' })
    })

    it('reuses the default orbit when retrying after collection creation failed', async () => {
      const { resolveCollectionRequestInfo } = await setup()

      const first = await resolveCollectionRequestInfo()
      const retry = await resolveCollectionRequestInfo()

      expect(mocks.api.createOrbit).toHaveBeenCalledTimes(1)
      expect(retry).toEqual(first)
    })

    it('allows retrying when default orbit creation failed', async () => {
      mocks.api.createOrbit.mockRejectedValueOnce(new Error('boom'))
      const { resolveCollectionRequestInfo } = await setup()

      await expect(resolveCollectionRequestInfo()).rejects.toThrow('boom')
      const info = await resolveCollectionRequestInfo()

      expect(mocks.api.createOrbit).toHaveBeenCalledTimes(2)
      expect(info).toEqual({ organizationId: 'org-1', orbitId: 'default-orbit' })
    })

    it('opens the created collection and refreshes orbits', async () => {
      const { onCollectionCreated } = await setup()

      await onCollectionCreated({ id: 'collection-1' } as OrbitCollection, {
        organizationId: 'org-1',
        orbitId: 'default-orbit',
      })

      expect(mocks.push).toHaveBeenCalledWith({
        name: 'collection',
        params: { organizationId: 'org-1', id: 'default-orbit', collectionId: 'collection-1' },
      })
      expect(mocks.api.getOrganizationOrbits).toHaveBeenCalledWith('org-1')
    })
  })

  describe('organization switching', () => {
    it('ignores a stale bucket response from the previous organization', async () => {
      const previous = deferred<unknown[]>()
      mocks.api.bucketSecrets.getBucketSecretsList
        .mockReturnValueOnce(previous.promise)
        .mockResolvedValueOnce([bucket('bucket-2')])
      mocks.api.createOrbit.mockResolvedValue(orbit('default-orbit'))

      const { resolveCollectionRequestInfo } = await setup()
      setOrganization('org-2')
      await nextTick()
      await flushPromises()
      previous.resolve([bucket('bucket-1')])
      await flushPromises()

      expect(useBucketsStore().buckets).toEqual([bucket('bucket-2')])
      await resolveCollectionRequestInfo()
      expect(mocks.api.createOrbit).toHaveBeenCalledWith(
        'org-2',
        expect.objectContaining({ bucket_secret_id: 'bucket-2' }),
      )
    })

    it('does not create a default orbit before buckets of the new organization load', async () => {
      mocks.api.bucketSecrets.getBucketSecretsList
        .mockResolvedValueOnce([bucket('bucket-1')])
        .mockReturnValueOnce(new Promise(() => {}))

      const { resolveCollectionRequestInfo } = await setup()
      setOrganization('org-2')
      await nextTick()

      await expect(resolveCollectionRequestInfo()).rejects.toThrow('Storage bucket not found')
      expect(mocks.api.createOrbit).not.toHaveBeenCalled()
    })
  })
})
