import { flushPromises, shallowMount } from '@vue/test-utils'
import { defineComponent, h, nextTick, onMounted, onUnmounted } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import CollectionPage from '../CollectionPage.vue'

const harness = vi.hoisted(() => ({
  route: null as { params: Record<string, string>; name: string } | null,
  routerPush: vi.fn(),
  setCurrentCollection: vi.fn().mockResolvedValue(undefined),
  resetCurrentCollection: vi.fn(),
  getOrbitDetails: vi.fn().mockResolvedValue({ id: 'orbit' }),
  setCurrentOrbitDetails: vi.fn(),
  artifactMounted: vi.fn(),
  artifactUnmounted: vi.fn(),
  toastAdd: vi.fn(),
}))

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  const { reactive } = await import('vue')
  harness.route = reactive({
    name: 'experiment-snapshot',
    params: {
      organizationId: 'org',
      id: 'orbit',
      collectionId: 'models',
      artifactId: 'artifact',
    },
  })
  return {
    ...actual,
    useRoute: () => harness.route,
    useRouter: () => ({ push: harness.routerPush }),
  }
})
vi.mock('@/stores/collections', () => ({
  useCollectionsStore: () => ({
    currentCollection: { id: 'models' },
    setCurrentCollection: harness.setCurrentCollection,
    resetCurrentCollection: harness.resetCurrentCollection,
  }),
}))
vi.mock('@/stores/orbits', () => ({
  useOrbitsStore: () => ({
    currentOrbitDetails: { id: 'orbit' },
    getOrbitDetails: harness.getOrbitDetails,
    setCurrentOrbitDetails: harness.setCurrentOrbitDetails,
  }),
}))
vi.mock('@/stores/organization', () => ({
  useOrganizationStore: () => ({ currentOrganization: { id: 'org' } }),
}))
vi.mock('primevue', async (importOriginal) => {
  const actual = await importOriginal<typeof import('primevue')>()
  return { ...actual, useToast: () => ({ add: harness.toastAdd }) }
})

describe('CollectionPage', () => {
  let wrapper: ReturnType<typeof shallowMount> | null = null

  const artifactPage = defineComponent({
    setup() {
      onMounted(harness.artifactMounted)
      onUnmounted(harness.artifactUnmounted)
      return () => h('div', 'artifact page')
    },
  })

  function mountPage() {
    wrapper = shallowMount(CollectionPage, {
      global: {
        stubs: {
          UiPageLoader: true,
          Ui404: true,
          CollectionBreadcrumb: true,
          RouterView: artifactPage,
        },
      },
    })
    return wrapper
  }

  async function navigate(params: Record<string, string> = {}, name = 'artifact') {
    if (!harness.route) throw new Error('Route was not initialized')
    harness.route.name = name
    harness.route.params = { ...harness.route.params, ...params }
    await nextTick()
    await flushPromises()
  }

  beforeEach(() => {
    harness.setCurrentCollection.mockReset().mockResolvedValue(undefined)
    harness.resetCurrentCollection.mockReset()
    harness.toastAdd.mockReset()
    harness.getOrbitDetails.mockReset().mockResolvedValue({ id: 'orbit' })
    harness.setCurrentOrbitDetails.mockReset()
    harness.artifactMounted.mockReset()
    harness.artifactUnmounted.mockReset()
    if (harness.route) {
      harness.route.name = 'experiment-snapshot'
      harness.route.params = {
        organizationId: 'org',
        id: 'orbit',
        collectionId: 'models',
        artifactId: 'artifact',
      }
    }
  })

  afterEach(() => wrapper?.unmount())

  it('keeps the artifact page mounted when switching tabs with the same collection URL parameters', async () => {
    const page = mountPage()
    await flushPromises()
    expect(harness.artifactMounted).toHaveBeenCalledTimes(1)

    for (const tab of [
      'artifact',
      'experiment-snapshot',
      'artifact-card',
      'attachments',
      'lineage',
    ]) {
      await navigate({}, tab)
      expect(page.findComponent({ name: 'UiPageLoader' }).exists()).toBe(false)
      expect(harness.artifactUnmounted).not.toHaveBeenCalled()
      expect(harness.artifactMounted).toHaveBeenCalledTimes(1)
    }

    expect(harness.setCurrentCollection).toHaveBeenCalledExactlyOnceWith('models')
    expect(harness.resetCurrentCollection).toHaveBeenCalledTimes(1)
    expect(harness.getOrbitDetails).not.toHaveBeenCalled()
  })

  it.each([
    ['organizationId', 'other-org', 'models'],
    ['id', 'other-orbit', 'models'],
    ['collectionId', 'datasets', 'datasets'],
  ])(
    'reloads collection data when the %s URL parameter changes',
    async (param, value, collectionId) => {
      mountPage()
      await flushPromises()
      expect(harness.setCurrentCollection).toHaveBeenLastCalledWith('models')

      await navigate({ [param]: value })

      expect(harness.setCurrentCollection).toHaveBeenLastCalledWith(collectionId)
      expect(harness.setCurrentCollection).toHaveBeenCalledTimes(2)
      expect(harness.resetCurrentCollection).toHaveBeenCalledTimes(2)
      if (param === 'id') {
        expect(harness.getOrbitDetails).toHaveBeenCalledExactlyOnceWith('org', 'other-orbit')
      }
    },
  )

  it('remounts the artifact page without reloading its collection when the artifact changes', async () => {
    mountPage()
    await flushPromises()

    await navigate({ artifactId: 'other-artifact' })

    expect(harness.setCurrentCollection).toHaveBeenCalledTimes(1)
    expect(harness.resetCurrentCollection).toHaveBeenCalledTimes(1)
    expect(harness.artifactUnmounted).toHaveBeenCalledTimes(1)
    expect(harness.artifactMounted).toHaveBeenCalledTimes(2)

    await navigate({}, 'artifact-card')
    await navigate({}, 'experiment-snapshot')

    expect(harness.setCurrentCollection).toHaveBeenCalledTimes(1)
    expect(harness.artifactUnmounted).toHaveBeenCalledTimes(1)
    expect(harness.artifactMounted).toHaveBeenCalledTimes(2)
  })

  it('does not restart a pending collection load on a tab switch', async () => {
    let finishLoad!: () => void
    harness.setCurrentCollection.mockReturnValueOnce(
      new Promise<void>((resolve) => {
        finishLoad = resolve
      }),
    )
    mountPage()
    await navigate()

    expect(harness.setCurrentCollection).toHaveBeenCalledTimes(1)
    expect(harness.artifactMounted).not.toHaveBeenCalled()

    finishLoad()
    await flushPromises()
    expect(harness.artifactMounted).toHaveBeenCalledTimes(1)
  })

  it('reports a failed load once and retries when the collection URL changes', async () => {
    harness.setCurrentCollection.mockRejectedValueOnce(new Error('Load failed'))
    mountPage()
    await flushPromises()
    expect(harness.toastAdd).toHaveBeenCalledTimes(1)

    await navigate()
    expect(harness.setCurrentCollection).toHaveBeenCalledTimes(1)
    expect(harness.toastAdd).toHaveBeenCalledTimes(1)

    await navigate({ collectionId: 'datasets' })
    expect(harness.setCurrentCollection).toHaveBeenLastCalledWith('datasets')
    expect(harness.setCurrentCollection).toHaveBeenCalledTimes(2)
  })
})
