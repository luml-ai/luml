import { shallowMount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import { ArtifactStatusEnum, ArtifactTypeEnum, type Artifact } from '@/lib/api/artifacts/interfaces'
import ArtifactDetails from '../ArtifactDetails.vue'

const route = vi.hoisted(() => ({ params: { organizationId: 'org', id: 'orbit' } }))

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return { ...actual, useRoute: () => route }
})

const RouterLinkStub = defineComponent({
  name: 'RouterLink',
  props: { to: { type: Object, required: true } },
  template: '<a><slot /></a>',
})

const TracksStub = defineComponent({
  name: 'ArtifactTracks',
  props: { tracks: { type: Array, required: true } },
  template: '<div class="tracks">{{ tracks.length }}</div>',
})

function artifact(overrides: Partial<Artifact> = {}): Artifact {
  return {
    id: '01a0-artifact',
    name: 'llm_train-v54567',
    collection_id: 'col-1',
    collection_name: 'DataTeam Collection',
    type: ArtifactTypeEnum.model,
    status: ArtifactStatusEnum.pending_upload,
    created_at: '2026-03-12T14:45:30Z',
    description: 'Above average mid-training loss',
    tags: ['nlp', 'v5'],
    size: 128_000_000,
    extra_values: { Loss: 0.479246, Tokenizer: 'Unigram' },
    manifest: null,
    deployments: [
      { id: 'd1', name: 'sentence_transformers', orbit_id: 'orbit', status: 'active' },
      { id: 'd2', name: 'fallback', orbit_id: 'orbit', status: 'pending' },
    ],
    tracks: [{ id: 't1', name: 'My TEST Track', created_at: '', updated_at: '' }],
    ...overrides,
  } as unknown as Artifact
}

function mountDetails(data: Artifact, withManifest = false) {
  return shallowMount(ArtifactDetails, {
    props: { artifact: data, withManifest },
    global: {
      stubs: {
        RouterLink: RouterLinkStub,
        ArtifactTracks: TracksStub,
        Tag: { props: ['value'], template: '<span>{{ value }}<slot /></span>' },
        Button: { template: '<button><slot /></button>' },
        ModelManifestModal: true,
      },
    },
  })
}

describe('ArtifactDetails', () => {
  it('renders every field of the design from the artifact', () => {
    const wrapper = mountDetails(artifact())
    const text = wrapper.text()

    expect(text).toContain('01a0-artifact')
    expect(text).toContain('llm_train-v54567')
    expect(text).toContain('Pending upload')
    expect(text).toContain(new Date('2026-03-12T14:45:30Z').toLocaleString())
    expect(text).toContain('Above average mid-training loss')
    expect(text).toContain('nlp')
    expect(text).toContain('v5')
    expect(text).toContain('sentence_transformers, fallback')
    expect(text).toContain('DataTeam Collection')
    expect(text).toContain('128.00 MB')
    expect(text).toContain('Loss')
    expect(text).toContain('0.479246')
    expect(text).toContain('Tokenizer')
    expect(text).toContain('Unigram')
    expect(text).not.toContain('Manifest')
    expect(wrapper.findComponent(TracksStub).props('tracks')).toEqual(artifact().tracks)
  })

  it('hides the manifest row unless asked for it', () => {
    const manifest = { variant: 'pipeline' } as unknown as Artifact['manifest']
    expect(mountDetails(artifact({ manifest })).text()).not.toContain('Manifest')
    expect(mountDetails(artifact({ manifest }), true).text()).toContain('Manifest')
  })

  it('links deployments and the collection', () => {
    const wrapper = mountDetails(artifact())
    const links = wrapper.findAllComponents(RouterLinkStub).map((link) => link.props('to'))

    expect(links).toEqual([
      {
        name: 'orbit-deployments',
        params: { organizationId: 'org', id: 'orbit' },
        query: { deployment: 'd1' },
      },
      {
        name: 'orbit-deployments',
        params: { organizationId: 'org', id: 'orbit' },
        query: { deployment: 'd2' },
      },
      { name: 'collection', params: { organizationId: 'org', id: 'orbit', collectionId: 'col-1' } },
    ])
  })

  it('falls back to the details response collection and shows dashes for empty fields', () => {
    const wrapper = mountDetails(
      artifact({
        collection_name: undefined,
        collection: { id: 'col-1', name: 'Details collection' },
        description: '',
        tags: [],
        deployments: [],
        extra_values: {},
        tracks: [],
        manifest: { variant: 'pipeline' } as unknown as Artifact['manifest'],
      }),
      true,
    )
    const text = wrapper.text()

    expect(text).toContain('Details collection')
    expect(text).toContain('Manifest')
    expect(text).toContain('Show')
    expect(text.match(/-/g)?.length).toBeGreaterThanOrEqual(3)
    expect(wrapper.findComponent(TracksStub).props('tracks')).toEqual([])
  })
})
