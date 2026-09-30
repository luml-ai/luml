import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import axios from 'axios'
import type { ExperimentSnapshotProvider } from '@luml/experiments'
import { ArtifactStatusEnum, ArtifactTypeEnum, type Artifact } from '@/lib/api/artifacts/interfaces'
import { FNNX_PRODUCER_TAGS_MANIFEST_ENUM } from '@/lib/fnnx/FnnxService'
import ArtifactPage from '../index.vue'
import { useArtifactsStore } from '@/stores/artifacts'

const apiMocks = vi.hoisted(() => ({
  getArtifact: vi.fn(),
  getDownloadUrl: vi.fn(),
}))

const routerHarness = vi.hoisted(() => ({
  route: null as null | {
    name: string
    params: Record<string, string>
  },
  replace: vi.fn(),
  push: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  api: {
    artifacts: {
      getById: apiMocks.getArtifact,
      getDownloadUrl: apiMocks.getDownloadUrl,
    },
  },
}))

vi.mock('axios', () => ({
  default: {
    get: vi.fn(),
    delete: vi.fn(),
  },
}))

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  const { reactive } = await import('vue')
  routerHarness.route = reactive({
    name: 'artifact',
    params: {
      organizationId: 'org',
      id: 'orbit',
      collectionId: 'collection',
      artifactId: 'model',
    },
  })
  return {
    ...actual,
    useRoute: () => routerHarness.route,
    useRouter: () => ({ push: routerHarness.push, replace: routerHarness.replace }),
  }
})

vi.mock('primevue', async (importOriginal) => {
  const actual = await importOriginal<typeof import('primevue')>()
  return { ...actual, useToast: () => ({ add: vi.fn() }) }
})

vi.mock('@/stores/orbits', () => ({
  useOrbitsStore: () => ({ getCurrentOrbitPermissions: null }),
}))

vi.mock('@/stores/collections', () => ({
  useCollectionsStore: () => ({ currentCollection: null }),
}))

vi.mock('@/stores/datasets', () => ({
  useDatasetsStore: () => ({ reset: vi.fn() }),
}))

vi.mock('@/components/orbits/tabs/registry/collection/artifact/ArtifactTabs.vue', async () => {
  const { defineComponent } = await import('vue')
  return {
    default: defineComponent({
      name: 'ArtifactTabs',
      props: {
        showModelAttachments: Boolean,
        showDataTab: Boolean,
        showCard: Boolean,
        showExperimentSnapshot: Boolean,
        cardDisabled: Boolean,
        experimentSnapshotDisabled: Boolean,
      },
      template: '<div />',
    }),
  }
})

vi.mock('@/components/deployments/create/DeploymentsCreateModal.vue', () => ({
  default: { template: '<div />' },
}))

vi.mock('@/components/orbits/tabs/registry/collection/artifact/ArtifactEditor.vue', () => ({
  default: { template: '<div />' },
}))

vi.mock('@/components/tracks/LinkArtifactToTrack.vue', () => ({
  default: { template: '<div />' },
}))

vi.mock(
  '@/components/orbits/tabs/registry/collection/artifacts-table/ArtifactsDeploymentsModal.vue',
  () => ({ default: { template: '<div />' } }),
)

const mockedAxios = vi.mocked(axios)

function model(): Artifact {
  return {
    id: 'model',
    type: ArtifactTypeEnum.model,
    status: ArtifactStatusEnum.uploaded,
    size: 200,
    file_index: {
      'attachments.tar': [0, 100],
      'attachments.index.json': [100, 50],
    },
    manifest: { producer_tags: [], dynamic_attributes: [], env_vars: [] },
  } as unknown as Artifact
}

function mountPage() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return shallowMount(ArtifactPage, {
    global: {
      plugins: [pinia],
      stubs: {
        RouterView: true,
        DeploymentsCreateModal: true,
        ArtifactEditor: true,
        LinkArtifactToTrack: true,
        ArtifactsDeploymentsModal: true,
      },
      directives: { tooltip: () => {} },
    },
  })
}

describe('artifact page', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    apiMocks.getArtifact.mockReset()
    apiMocks.getDownloadUrl.mockReset()
    mockedAxios.get.mockReset()
    routerHarness.replace.mockReset()
    routerHarness.push.mockReset()
    if (!routerHarness.route) throw new Error('Route harness was not initialized')
    routerHarness.route.name = 'artifact'
    routerHarness.route.params.artifactId = 'model'
    apiMocks.getArtifact.mockResolvedValue(model())
    apiMocks.getDownloadUrl.mockResolvedValue({ url: 'https://download.test/model' })
  })

  it('shows the tab after reading a non-empty attachment index', async () => {
    mockedAxios.get.mockResolvedValue({
      data: { 'attachments/report.pdf': [0, 42] },
    })
    const wrapper = mountPage()

    await flushPromises()

    expect(wrapper.findComponent({ name: 'ArtifactTabs' }).props('showModelAttachments')).toBe(true)
  })

  it('hides the tab after reading an empty attachment index', async () => {
    mockedAxios.get.mockResolvedValue({ data: {} })
    const wrapper = mountPage()

    await flushPromises()

    expect(wrapper.findComponent({ name: 'ArtifactTabs' }).props('showModelAttachments')).toBe(
      false,
    )
  })

  it('does not show the tab before attachment availability is known', async () => {
    apiMocks.getDownloadUrl.mockImplementation(() => new Promise(() => {}))
    const wrapper = mountPage()

    await flushPromises()

    expect(wrapper.findComponent({ name: 'ArtifactTabs' }).props('showModelAttachments')).toBe(
      false,
    )
  })

  it('keeps the tab available when index inspection fails', async () => {
    apiMocks.getDownloadUrl.mockRejectedValue(new Error('temporary failure'))
    const wrapper = mountPage()

    await flushPromises()

    expect(wrapper.findComponent({ name: 'ArtifactTabs' }).props('showModelAttachments')).toBe(true)
  })

  it('redirects a direct empty-attachments route to the overview', async () => {
    if (!routerHarness.route) throw new Error('Route harness was not initialized')
    routerHarness.route.name = 'attachments'
    mockedAxios.get.mockResolvedValue({ data: {} })
    mountPage()

    await flushPromises()

    expect(routerHarness.replace).toHaveBeenCalledWith({ name: 'artifact' })
  })

  it('redirects when a retry finds an empty attachment index', async () => {
    if (!routerHarness.route) throw new Error('Route harness was not initialized')
    routerHarness.route.name = 'attachments'
    apiMocks.getDownloadUrl.mockRejectedValueOnce(new Error('temporary failure'))
    mockedAxios.get.mockResolvedValue({ data: {} })
    mountPage()

    await flushPromises()
    expect(routerHarness.replace).not.toHaveBeenCalled()

    const store = useArtifactsStore()
    await store.loadCurrentArtifactAttachments(store.currentArtifact!)
    await flushPromises()

    expect(routerHarness.replace).toHaveBeenCalledWith({ name: 'artifact' })
  })

  it('retains cached card and snapshot state across tabs and clears it on teardown', async () => {
    mockedAxios.get.mockResolvedValue({ data: {} })
    const wrapper = mountPage()
    await flushPromises()
    const store = useArtifactsStore()
    const metadata = {
      metrics: {
        performance: { train: { ACC: 1, PRECISION: 1, RECALL: 1, F1: 1, SC_SCORE: 1 } },
        permutation_feature_importance_train: { importances: [] },
      },
    }
    const provider = {} as ExperimentSnapshotProvider
    const releaseProvider = vi.fn()
    store.setCurrentModelTag(FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_classification_v1)
    store.setCurrentModelMetadata(metadata)
    store.setCurrentModelHtmlBlobUrl('blob:card')
    store.setExperimentSnapshotProvider(provider, releaseProvider)

    if (!routerHarness.route) throw new Error('Route harness was not initialized')
    for (const tab of ['artifact-card', 'artifact', 'experiment-snapshot']) {
      routerHarness.route.name = tab
      await flushPromises()
      expect(store.currentModelMetadata).toEqual(metadata)
      expect(store.currentModelHtmlBlobUrl).toBe('blob:card')
      expect(store.experimentSnapshotProvider).toEqual(provider)
      expect(releaseProvider).not.toHaveBeenCalled()
    }
    expect(apiMocks.getArtifact).toHaveBeenCalledTimes(1)

    wrapper.unmount()

    expect(store.currentArtifact).toBeNull()
    expect(store.currentModelTag).toBeNull()
    expect(store.currentModelMetadata).toBeNull()
    expect(store.currentModelHtmlBlobUrl).toBeNull()
    expect(store.experimentSnapshotProvider).toBeNull()
    expect(releaseProvider).toHaveBeenCalledTimes(1)
  })
})
