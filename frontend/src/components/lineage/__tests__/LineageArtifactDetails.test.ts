import { flushPromises, shallowMount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { LineageNodeData } from '../lineage.interface'
import { ArtifactStatusEnum, ArtifactTypeEnum, type Artifact } from '@/lib/api/artifacts/interfaces'
import LineageArtifactDetails from '../LineageArtifactDetails.vue'

const route = vi.hoisted(() => ({
  params: {
    organizationId: 'org',
    id: 'orbit',
    collectionId: 'models',
    artifactId: 'focal',
  },
}))

const mocks = vi.hoisted(() => ({
  getById: vi.fn(),
  toastAdd: vi.fn(),
}))

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return { ...actual, useRoute: () => route }
})

vi.mock('@/lib/api', () => ({ api: { artifacts: { getById: mocks.getById } } }))

vi.mock('primevue', async (importOriginal) => {
  const actual = await importOriginal<typeof import('primevue')>()
  return { ...actual, useToast: () => ({ add: mocks.toastAdd }) }
})

const DialogStub = defineComponent({
  name: 'UiDialogRight',
  props: { visible: Boolean },
  template: '<div v-if="visible"><slot></slot><footer><slot name="footer"></slot></footer></div>',
})

const RouterLinkStub = defineComponent({
  name: 'RouterLink',
  props: { to: { type: Object, required: true } },
  template: '<a><slot /></a>',
})

const ArtifactDetailsStub = defineComponent({
  name: 'ArtifactDetails',
  props: { artifact: { type: Object, required: true } },
  template: '<div class="artifact-details">{{ artifact.name }}</div>',
})

function artifact(overrides: Partial<Artifact> = {}): Artifact {
  return {
    id: 'dataset',
    name: 'Training data',
    collection_id: 'datasets',
    collection_name: 'Datasets',
    type: ArtifactTypeEnum.dataset,
    status: ArtifactStatusEnum.uploaded,
    created_at: '2026-01-02T03:04:05Z',
    deployments: [],
    ...overrides,
  } as unknown as Artifact
}

function nodeData(variant: LineageNodeData['variant'] = 'default'): LineageNodeData {
  return {
    nodeId: 'node-dataset',
    artifactId: 'dataset',
    collectionId: 'datasets',
    collectionName: 'Datasets',
    isDeleted: false,
    type: ArtifactTypeEnum.dataset,
    title: 'Training data',
    variant,
    data: artifact(),
    deployments: [],
    tracks: [],
  }
}

function mountDetails(data: LineageNodeData) {
  return shallowMount(LineageArtifactDetails, {
    props: { data, visible: true },
    global: {
      stubs: {
        UiDialogRight: DialogStub,
        RouterLink: RouterLinkStub,
        ArtifactDetails: ArtifactDetailsStub,
        Tag: { template: '<span><slot /></span>' },
        ProgressSpinner: { template: '<i class="spinner" />' },
      },
    },
  })
}

describe('LineageArtifactDetails', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getById.mockResolvedValue(artifact({ tracks: [{ id: 't1', name: 'Release track' }] }))
  })

  it('shows the graph payload right away and swaps in the fetched artifact details', async () => {
    const wrapper = mountDetails(nodeData())

    const details = wrapper.findComponent(ArtifactDetailsStub)
    expect(details.props('artifact')).toEqual(nodeData().data)

    await flushPromises()
    expect(mocks.getById).toHaveBeenCalledWith('org', 'orbit', 'datasets', 'dataset')
    expect(wrapper.findComponent(ArtifactDetailsStub).props('artifact').tracks).toEqual([
      { id: 't1', name: 'Release track' },
    ])
    expect(mocks.toastAdd).not.toHaveBeenCalled()
  })

  it('keeps the graph payload and reports when the details cannot be loaded', async () => {
    mocks.getById.mockRejectedValueOnce(new Error('boom'))
    const wrapper = mountDetails(nodeData())
    await flushPromises()

    expect(mocks.toastAdd).toHaveBeenCalledTimes(1)
    expect(wrapper.findComponent(ArtifactDetailsStub).props('artifact')).toEqual(nodeData().data)
  })

  it('renders cross-collection navigation for a live node', async () => {
    const wrapper = mountDetails(nodeData())
    await flushPromises()

    expect(wrapper.text()).toContain('Open artifact')
    expect(wrapper.text()).toContain('Focus lineage')
    const links = wrapper.findAllComponents(RouterLinkStub)
    expect(links.map((link) => link.props('to'))).toEqual([
      {
        name: 'artifact',
        params: {
          organizationId: 'org',
          id: 'orbit',
          collectionId: 'datasets',
          artifactId: 'dataset',
        },
      },
      {
        name: 'lineage',
        params: {
          organizationId: 'org',
          id: 'orbit',
          collectionId: 'datasets',
          artifactId: 'dataset',
        },
      },
    ])
  })

  it('hides Focus lineage for the focal artifact', async () => {
    const wrapper = mountDetails(nodeData('main'))
    await flushPromises()

    expect(wrapper.text()).toContain('Open artifact')
    expect(wrapper.text()).not.toContain('Focus lineage')
    expect(wrapper.findAllComponents(RouterLinkStub)).toHaveLength(1)
  })

  it('renders a deleted node from its copied fields without fetching or navigation', async () => {
    const wrapper = mountDetails({
      ...nodeData('disabled'),
      artifactId: null,
      collectionId: null,
      isDeleted: true,
      data: null,
    })
    await flushPromises()

    expect(mocks.getById).not.toHaveBeenCalled()
    expect(wrapper.findComponent(ArtifactDetailsStub).exists()).toBe(false)
    expect(wrapper.text()).toContain('Dataset')
    expect(wrapper.text()).toContain('Training data')
    expect(wrapper.text()).toContain('Datasets')
    expect(wrapper.text()).toContain('Deleted')
    expect(wrapper.text()).not.toContain('Open artifact')
    expect(wrapper.findAllComponents(RouterLinkStub)).toHaveLength(0)
  })

  it('shows a loader while a node without graph payload is being fetched', async () => {
    let resolve: (value: Artifact) => void = () => {}
    mocks.getById.mockReturnValueOnce(new Promise<Artifact>((r) => (resolve = r)))
    const wrapper = mountDetails({ ...nodeData(), data: null })

    expect(wrapper.find('.spinner').exists()).toBe(true)
    resolve(artifact())
    await flushPromises()
    expect(wrapper.find('.spinner').exists()).toBe(false)
    expect(wrapper.findComponent(ArtifactDetailsStub).props('artifact').name).toBe('Training data')
  })
})
