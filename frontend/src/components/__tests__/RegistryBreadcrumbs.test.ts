import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'
import PrimeVue from 'primevue/config'
import { createMemoryHistory, createRouter } from 'vue-router'
import TrackBreadcrumbs from '@/components/tracks/TrackBreadcrumbs.vue'
import CollectionBreadcrumb from '@/components/orbits/tabs/registry/collection/CollectionBreadcrumb.vue'

const collections = reactive({ currentCollection: null as { name: string } | null })
const artifacts = reactive({ currentArtifact: null as { name: string } | null })

vi.mock('@/stores/collections', () => ({ useCollectionsStore: () => collections }))
vi.mock('@/stores/artifacts', () => ({ useArtifactsStore: () => artifacts }))

const orbitPath = '/organization/org-1/orbit/orbit-1'
const collectionPath = `${orbitPath}/collection/collection-1`
const artifactPath = `${collectionPath}/artifacts/artifact-1`

async function mountBreadcrumb(path: string, track = false) {
  const page = { template: '<div />' }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/organization/:organizationId/orbit/:id',
        name: 'orbit-collections',
        component: page,
      },
      {
        path: '/organization/:organizationId/orbit/:id/tracks',
        name: 'orbit-tracks',
        component: page,
      },
      {
        path: '/organization/:organizationId/orbit/:id/tracks/:trackId',
        name: 'track',
        component: page,
      },
      {
        path: '/organization/:organizationId/orbit/:id/collection/:collectionId/artifacts/:artifactId/:pathMatch(.*)*',
        component: page,
      },
      {
        path: '/organization/:organizationId/orbit/:id/collection/:collectionId/:pathMatch(.*)*',
        component: page,
      },
    ],
  })
  await router.push(path)
  await router.isReady()
  const wrapper = track
    ? mount(TrackBreadcrumbs, {
        props: { trackName: 'Iris Classifier', trackId: 'track-1' },
        global: { plugins: [router, PrimeVue] },
      })
    : mount(CollectionBreadcrumb, { global: { plugins: [router, PrimeVue] } })
  return { wrapper, router }
}

describe('registry breadcrumbs', () => {
  beforeEach(() => {
    collections.currentCollection = { name: 'LLM · Failure Tests' }
    artifacts.currentArtifact = null
  })

  it('links the registry, tracks list and current track', async () => {
    const { wrapper, router } = await mountBreadcrumb(`${orbitPath}/tracks/track-1`, true)
    const links = wrapper.findAll('a')

    expect(links.map((link) => [link.text(), link.attributes('href')])).toEqual([
      ['Registry', orbitPath],
      ['Tracks', `${orbitPath}/tracks`],
      ['Iris Classifier', `${orbitPath}/tracks/track-1`],
    ])
    await links[1].trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('orbit-tracks')
  })

  it('links the registry, collections list and current collection', async () => {
    const { wrapper, router } = await mountBreadcrumb(collectionPath)
    const links = wrapper.findAll('a')

    expect(links.map((link) => [link.text(), link.attributes('href')])).toEqual([
      ['Registry', orbitPath],
      ['Collections', orbitPath],
      ['LLM · Failure Tests', collectionPath],
    ])
    await links[1].trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('orbit-collections')
  })

  it.each(['', '/data', '/card', '/experiment-snapshot', '/attachments', '/lineage'])(
    'retains the full collection hierarchy on artifact tab %s',
    async (tab) => {
      artifacts.currentArtifact = { name: 'Iris <model>' }
      const { wrapper, router } = await mountBreadcrumb(`${artifactPath}${tab}`)
      const links = wrapper.findAll('a')

      expect(links.map((link) => [link.text(), link.attributes('href')])).toEqual([
        ['Registry', orbitPath],
        ['Collections', orbitPath],
        ['LLM · Failure Tests', collectionPath],
        ['Iris <model>', artifactPath],
      ])
      await links[2].trigger('click')
      await flushPromises()
      expect(router.currentRoute.value.path).toBe(collectionPath)
    },
  )

  it('retains the collections list and comparison query', async () => {
    const path = `${collectionPath}/compare?artifacts=first&artifacts=second`
    const { wrapper } = await mountBreadcrumb(path)

    expect(wrapper.findAll('a').map((link) => [link.text(), link.attributes('href')])).toEqual([
      ['Registry', orbitPath],
      ['Collections', orbitPath],
      ['LLM · Failure Tests', collectionPath],
      ['Experiments comparison (2)', path],
    ])
  })

  it('keeps list links available while collection data is unavailable', async () => {
    collections.currentCollection = null
    const { wrapper } = await mountBreadcrumb(collectionPath)

    expect(wrapper.findAll('a').map((link) => link.text())).toEqual(['Registry', 'Collections'])
  })

  it('updates list links when the organization and orbit change', async () => {
    const { wrapper, router } = await mountBreadcrumb(`${orbitPath}/tracks/track-1`, true)
    await router.push('/organization/org-2/orbit/orbit-2/tracks/track-1')
    await flushPromises()

    expect(wrapper.findAll('a').map((link) => link.attributes('href'))).toEqual([
      '/organization/org-2/orbit/orbit-2',
      '/organization/org-2/orbit/orbit-2/tracks',
      '/organization/org-2/orbit/orbit-2/tracks/track-1',
    ])
  })
})
