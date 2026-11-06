import type { Orbit } from '@/lib/api/api.interfaces'
import type { OrbitCollection } from '@/lib/api/orbit-collections/interfaces'
import { createPinia, setActivePinia } from 'pinia'
import { effectScope, nextTick, reactive } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  api: {
    createOrbit: vi.fn(),
    getOrbitDetails: vi.fn(),
    getOrganizationOrbits: vi.fn(),
    bucketSecrets: { getBucketSecretsList: vi.fn() },
    orbitCollections: { createCollection: vi.fn(), getCollectionsTags: vi.fn() },
  },
  push: vi.fn(),
  toastAdd: vi.fn(),
  auth: { isAuth: true },
  organization: {
    currentOrganization: null as null | {
      id: string
      role: string
      permissions: { orbit: string[] }
    },
    organizationDetails: null,
  },
}))

vi.mock('@/lib/api', () => ({ api: mocks.api }))
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mocks.push }),
  useRoute: () => ({ params: {} }),
}))
vi.mock('primevue', async (importOriginal) => ({
  ...((await importOriginal()) as Record<string, unknown>),
  useToast: () => ({ add: mocks.toastAdd }),
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mocks.auth }))
vi.mock('@/stores/organization', async () => {
  const { reactive } = await import('vue')
  const store = reactive(mocks.organization)
  mocks.organization = store
  return { useOrganizationStore: () => store }
})

import { QuickStartStepEnum, useQuickStart } from '../useQuickStart'
import CollectionCreator from '@/components/orbits/tabs/registry/CollectionCreator.vue'
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

function setOrganization(id: string, orbitPermissions = ['list', 'create'], role = 'owner') {
  mocks.organization.currentOrganization = reactive({
    id,
    role,
    permissions: { orbit: orbitPermissions },
  })
}

function mountCollectionCreator(quickStart: ReturnType<typeof useQuickStart>) {
  return mount(CollectionCreator, {
    props: {
      visible: true,
      showDefaultOrbitInfo: !quickStart.collectionOrbit.value,
      resolveRequestInfo: quickStart.resolveCollectionRequestInfo,
      afterCreate: quickStart.onCollectionCreated,
    },
    global: {
      plugins: [PrimeVue],
      stubs: { Dialog: { template: '<div><slot /></div>' } },
    },
  })
}

async function submitCollection(wrapper: ReturnType<typeof mountCollectionCreator>) {
  await wrapper.get('#name').setValue('First collection')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
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

  describe('bucket step', () => {
    it.each(['owner', 'admin'])('offers bucket linking to an organization %s', async (role) => {
      setOrganization('org-1', ['list', 'create'], role)

      const { activeStep } = await setup()

      expect(activeStep.value).toBe(QuickStartStepEnum.bucket)
    })

    it('does not offer bucket linking to an organization member', async () => {
      setOrganization('org-1', ['list'], 'member')

      const { activeStep, runActiveStep, isBucketDialogVisible } = await setup()
      runActiveStep()

      expect(activeStep.value).toBeNull()
      expect(isBucketDialogVisible.value).toBe(false)
      expect(mocks.api.bucketSecrets.getBucketSecretsList).not.toHaveBeenCalled()
    })

    it('offers collection creation to a member with an accessible orbit', async () => {
      setOrganization('org-1', ['list'], 'member')
      useOrbitsStore().orbitsList = [orbit('orbit-1')]

      const { activeStep } = await setup()

      expect(activeStep.value).toBe(QuickStartStepEnum.collection)
    })

    it('does not offer bucket linking when the bucket list request fails', async () => {
      mocks.api.bucketSecrets.getBucketSecretsList.mockRejectedValue(new Error('forbidden'))
      vi.spyOn(console, 'warn').mockImplementation(() => {})

      const { activeStep } = await setup()

      expect(activeStep.value).toBeNull()
    })

    it('still offers collection creation when the bucket list request fails', async () => {
      mocks.api.bucketSecrets.getBucketSecretsList.mockRejectedValue(new Error('network'))
      vi.spyOn(console, 'warn').mockImplementation(() => {})
      useOrbitsStore().orbitsList = [orbit('orbit-1')]

      const { activeStep } = await setup()

      expect(activeStep.value).toBe(QuickStartStepEnum.collection)
    })
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

  describe('collection submission from home', () => {
    beforeEach(() => {
      vi.stubGlobal(
        'matchMedia',
        vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
      )
      mocks.api.bucketSecrets.getBucketSecretsList.mockResolvedValue([bucket('bucket-1')])
      mocks.api.createOrbit.mockResolvedValue(orbit('default-orbit'))
      mocks.api.orbitCollections.createCollection.mockResolvedValue({ id: 'collection-1' })
      mocks.api.orbitCollections.getCollectionsTags.mockResolvedValue([])
    })

    afterEach(() => {
      vi.unstubAllGlobals()
    })

    it('creates the collection in a new default orbit without route params', async () => {
      const quickStart = await setup()
      const wrapper = mountCollectionCreator(quickStart)

      await submitCollection(wrapper)

      expect(mocks.api.createOrbit).toHaveBeenCalledTimes(1)
      expect(mocks.api.orbitCollections.createCollection).toHaveBeenCalledWith(
        'org-1',
        'default-orbit',
        expect.objectContaining({ name: 'First collection' }),
      )
      expect(mocks.api.orbitCollections.getCollectionsTags).toHaveBeenCalledWith(
        'org-1',
        'default-orbit',
      )
      expect(mocks.push).toHaveBeenCalledWith({
        name: 'collection',
        params: { organizationId: 'org-1', id: 'default-orbit', collectionId: 'collection-1' },
      })
      expect(wrapper.emitted('update:visible')).toEqual([[false]])
      wrapper.unmount()
    })

    it('creates the collection in the existing orbit without route params', async () => {
      useOrbitsStore().orbitsList = [orbit('orbit-1')]
      const quickStart = await setup()
      const wrapper = mountCollectionCreator(quickStart)

      await submitCollection(wrapper)

      expect(mocks.api.createOrbit).not.toHaveBeenCalled()
      expect(mocks.api.orbitCollections.createCollection).toHaveBeenCalledWith(
        'org-1',
        'orbit-1',
        expect.objectContaining({ name: 'First collection' }),
      )
      expect(mocks.api.orbitCollections.getCollectionsTags).toHaveBeenCalledWith('org-1', 'orbit-1')
      wrapper.unmount()
    })

    it('retries a failed collection request in the already created default orbit', async () => {
      mocks.api.orbitCollections.createCollection.mockRejectedValueOnce(new Error('boom'))
      const quickStart = await setup()
      const wrapper = mountCollectionCreator(quickStart)

      await submitCollection(wrapper)

      expect(mocks.toastAdd).toHaveBeenCalledWith(expect.objectContaining({ severity: 'error' }))
      expect(mocks.push).not.toHaveBeenCalled()
      expect(wrapper.emitted('update:visible')).toBeUndefined()

      await submitCollection(wrapper)

      expect(mocks.api.createOrbit).toHaveBeenCalledTimes(1)
      expect(mocks.api.orbitCollections.createCollection).toHaveBeenCalledTimes(2)
      expect(mocks.api.orbitCollections.createCollection).toHaveBeenLastCalledWith(
        'org-1',
        'default-orbit',
        expect.objectContaining({ name: 'First collection' }),
      )
      expect(mocks.push).toHaveBeenCalledTimes(1)
      wrapper.unmount()
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

    it('does not reuse buckets of an organization where the user was admin', async () => {
      mocks.api.bucketSecrets.getBucketSecretsList.mockResolvedValue([bucket('bucket-1')])

      const { activeStep, resolveCollectionRequestInfo } = await setup()
      expect(activeStep.value).toBe(QuickStartStepEnum.collection)

      setOrganization('org-2', ['list', 'create'], 'member')
      await nextTick()
      await flushPromises()

      expect(mocks.api.bucketSecrets.getBucketSecretsList).toHaveBeenCalledTimes(1)
      expect(activeStep.value).toBeNull()
      await expect(resolveCollectionRequestInfo()).rejects.toThrow('Storage bucket not found')
      expect(mocks.api.createOrbit).not.toHaveBeenCalled()
    })

    it('waits for the latest request when the same organization is reselected', async () => {
      const first = deferred<unknown[]>()
      const latest = deferred<unknown[]>()
      mocks.api.bucketSecrets.getBucketSecretsList
        .mockReturnValueOnce(first.promise)
        .mockResolvedValueOnce([])
        .mockReturnValueOnce(latest.promise)

      const { activeStep } = await setup()
      setOrganization('org-2')
      await nextTick()
      await flushPromises()
      setOrganization('org-1')
      await nextTick()

      first.resolve([])
      await flushPromises()
      expect(activeStep.value).toBeNull()

      latest.resolve([bucket('bucket-1')])
      await flushPromises()
      expect(useBucketsStore().buckets).toEqual([bucket('bucket-1')])
      expect(activeStep.value).toBe(QuickStartStepEnum.collection)
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
