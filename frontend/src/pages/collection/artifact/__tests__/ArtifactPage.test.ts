import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import axios from 'axios'
import { ArtifactStatusEnum, ArtifactTypeEnum, type Artifact } from '@/lib/api/artifacts/interfaces'
import ArtifactPage from '../index.vue'

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

describe('artifact page attachment tab', () => {
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
})
