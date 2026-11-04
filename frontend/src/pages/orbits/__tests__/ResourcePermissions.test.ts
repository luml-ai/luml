import { enableAutoUnmount, flushPromises, mount, shallowMount } from '@vue/test-utils'
import { nextTick, reactive } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { PermissionEnum as P } from '@/lib/api/api.interfaces'
import { ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces'
import TrackPage from '../TrackPage.vue'
import TrackCard from '@/components/tracks/TrackCard.vue'
import OrbitDeploymentsView from '../OrbitDeploymentsView.vue'
import OrbitSatellitesView from '../OrbitSatellitesView.vue'
import OrbitSecretsView from '../OrbitSecretsView.vue'
import SecretsList from '@/components/orbit-secrets/SecretsList.vue'
import S3BucketForm from '@/components/organizations/registry/S3BucketForm.vue'
import UiRichCard from '@/components/ui/UiRichCard.vue'
import UiCardAdd from '@/components/ui/UiCardAdd.vue'
import LinkArtifactCreator from '@/components/tracks/LinkArtifactCreator.vue'
import DeploymentsCreateModal from '@/components/deployments/create/DeploymentsCreateModal.vue'
import SatellitesCreateModal from '@/components/satellites/SatellitesCreateModal.vue'
import SecretCreator from '@/components/orbit-secrets/SecretCreator.vue'
import SecretModal from '@/components/orbit-secrets/SecretModal.vue'
import SecretsEditor from '@/components/orbit-secrets/SecretsEditor.vue'
import SatellitesCard from '@/components/satellites/SatellitesCard.vue'
import SatellitesEditModal from '@/components/satellites/SatellitesEditModal.vue'
import SatellitesApiKeyModal from '@/components/satellites/SatellitesApiKeyModal.vue'
import { SatelliteStatusEnum } from '@/lib/api/satellites/interfaces'
import { SECRET_MASK } from '@/components/orbit-secrets/secretMask'

enableAutoUnmount(afterEach)

const orbit = reactive({
  getCurrentOrbitPermissions: undefined as Partial<Record<string, P[]>> | undefined,
  currentOrbitDetails: { id: 'orbit', organization_id: 'organization' },
})
const auth = reactive({ isAuth: true })
const route = reactive({
  name: 'orbit-deployments',
  params: { id: 'orbit', organizationId: 'organization', trackId: 'track' },
})
const tracks = {
  currentTrack: { name: 'Track', id: 'track' },
  setCurrentTrack: vi.fn(),
  showEditor: vi.fn(),
}
const links = { showCreator: vi.fn(), creatorVisible: true }
const deployments = {
  deployments: [],
  creatorVisible: true,
  getDeployments: vi.fn().mockResolvedValue([]),
  setDeployments: vi.fn(),
  reset: vi.fn(),
  showCreator: vi.fn(),
}
const satellites = {
  satellitesList: [],
  creatorVisible: true,
  loadSatellites: vi.fn().mockResolvedValue([]),
  setList: vi.fn(),
  showCreator: vi.fn(),
}
const secrets = {
  creatorVisible: true,
  secretsList: [{ id: 'secret', name: 'Key', value: 'abc', tags: [] }],
  loadSecrets: vi.fn(),
  showCreator: vi.fn(),
}

vi.mock('@/stores/orbits', () => ({ useOrbitsStore: () => orbit }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => auth }))
vi.mock('@/stores/tracks', () => ({ useTracksStore: () => tracks }))
vi.mock('@/stores/artifact-links/artifact-links', () => ({ useArtifactLinksStore: () => links }))
vi.mock('@/stores/deployments', () => ({ useDeploymentsStore: () => deployments }))
vi.mock('@/stores/satellites', () => ({ useSatellitesStore: () => satellites }))
vi.mock('@/stores/orbit-secrets', () => ({ useSecretsStore: () => secrets }))
vi.mock('vue-router', () => ({ useRoute: () => route, useRouter: () => ({ push: vi.fn() }) }))
vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: vi.fn() }),
  useConfirm: () => ({ require: vi.fn() }),
}))

const global = {
  stubs: { 'd-button': false },
  components: { 'd-button': { props: ['label'], template: '<button>{{ label }}</button>' } },
}
const trackProps = {
  id: 'track',
  name: 'Track',
  description: '',
  type: ArtifactTypeEnum.model,
  artifactsCount: 0,
  stages: [],
  createdAt: '',
  updatedAt: null,
  tags: [],
}

beforeEach(() => {
  orbit.getCurrentOrbitPermissions = undefined
  auth.isAuth = true
  route.name = 'orbit-deployments'
})

describe('track actions', () => {
  it.each([
    undefined,
    {},
    { track: [P.read], artifact: [P.list, P.read] },
    { track: [P.update], artifact: [P.list, P.read] },
    { track: [P.create], artifact: [P.read] },
  ])(
    'hides linking without permissions to create an entry and select artifacts: %j',
    async (permissions) => {
      orbit.getCurrentOrbitPermissions = permissions
      const wrapper = shallowMount(TrackPage)
      await flushPromises()
      expect(wrapper.find('.link-artifact-btn').exists()).toBe(false)
      expect(wrapper.findComponent(LinkArtifactCreator).exists()).toBe(false)
    },
  )

  it('reacts to link permissions and preserves the link action', async () => {
    const wrapper = shallowMount(TrackPage)
    await flushPromises()
    orbit.getCurrentOrbitPermissions = { track: [P.create], artifact: [P.list] }
    await nextTick()
    await wrapper.get('.link-artifact-btn').trigger('click')
    expect(links.showCreator).toHaveBeenCalledOnce()
    expect(wrapper.findComponent(LinkArtifactCreator).exists()).toBe(true)
    orbit.getCurrentOrbitPermissions = undefined
    await nextTick()
    expect(wrapper.findComponent(LinkArtifactCreator).exists()).toBe(false)
  })

  it('permits editing only with track:update', async () => {
    const wrapper = shallowMount(TrackCard, { props: trackProps })
    expect(wrapper.getComponent(UiRichCard).props('editAvailable')).toBe(false)
    orbit.getCurrentOrbitPermissions = { track: [P.update] }
    await nextTick()
    expect(wrapper.getComponent(UiRichCard).props('editAvailable')).toBe(true)
    wrapper.getComponent(UiRichCard).vm.$emit('edit-click')
    expect(tracks.showEditor).toHaveBeenCalledOnce()
    orbit.getCurrentOrbitPermissions = { track: [P.read] }
    await nextTick()
    expect(wrapper.getComponent(UiRichCard).props('editAvailable')).toBe(false)
  })
})

describe('resource creation controls', () => {
  it.each([
    undefined,
    {},
    { deployment: [P.read, P.update], satellite: [P.read], orbit_secret: [P.read, P.update] },
  ])('hides all creation entry points for %j', async (permissions) => {
    orbit.getCurrentOrbitPermissions = permissions
    const deploymentView = shallowMount(OrbitDeploymentsView, { global })
    const satelliteView = shallowMount(OrbitSatellitesView, { global })
    await flushPromises()
    expect(deploymentView.find('button').exists()).toBe(true) // navigation tabs remain available
    expect(deploymentView.text()).not.toContain('Create deployment')
    expect(deploymentView.findComponent(UiCardAdd).exists()).toBe(false)
    expect(deploymentView.findComponent(DeploymentsCreateModal).exists()).toBe(false)
    expect(deploymentView.findComponent(SecretCreator).exists()).toBe(false)
    expect(satelliteView.find('button').exists()).toBe(false)
    expect(satelliteView.findComponent(UiCardAdd).exists()).toBe(false)
    expect(satelliteView.findComponent(SatellitesCreateModal).exists()).toBe(false)
    route.name = 'orbit-secrets'
    await nextTick()
    expect(deploymentView.text()).not.toContain('Create secret')
  })

  it('shows each creator only for its own create permission', async () => {
    const deploymentView = shallowMount(OrbitDeploymentsView, { global })
    const satelliteView = shallowMount(OrbitSatellitesView, { global })
    await flushPromises()
    orbit.getCurrentOrbitPermissions = { deployment: [P.create] }
    await nextTick()
    expect(deploymentView.text()).toContain('Create deployment')
    expect(deploymentView.findComponent(UiCardAdd).exists()).toBe(true)
    expect(deploymentView.findComponent(DeploymentsCreateModal).exists()).toBe(true)
    expect(satelliteView.findComponent(SatellitesCreateModal).exists()).toBe(false)
    route.name = 'orbit-secrets'
    await nextTick()
    expect(deploymentView.text()).not.toContain('Create secret')
    orbit.getCurrentOrbitPermissions = { orbit_secret: [P.create], satellite: [P.create] }
    await nextTick()
    expect(deploymentView.text()).toContain('Create secret')
    expect(deploymentView.findComponent(SecretCreator).exists()).toBe(true)
    expect(satelliteView.text()).toContain('Add satellite')
    expect(satelliteView.findComponent(UiCardAdd).exists()).toBe(true)
    expect(satelliteView.findComponent(SatellitesCreateModal).exists()).toBe(true)
  })

  it('keeps creation hidden when unauthenticated even with permissions', async () => {
    auth.isAuth = false
    orbit.getCurrentOrbitPermissions = {
      deployment: [P.create],
      satellite: [P.create],
      orbit_secret: [P.create],
    }
    const deploymentView = shallowMount(OrbitDeploymentsView, { global })
    const satelliteView = shallowMount(OrbitSatellitesView, { global })
    await flushPromises()
    expect(deploymentView.text()).not.toContain('Create deployment')
    expect(deploymentView.findComponent(UiCardAdd).exists()).toBe(false)
    expect(satelliteView.find('button').exists()).toBe(false)
    expect(satelliteView.findComponent(UiCardAdd).exists()).toBe(false)
  })
})

describe('secret access', () => {
  it.each([OrbitDeploymentsView, OrbitSecretsView])(
    'passes separate update and read permissions to the secrets list',
    async (component) => {
      route.name = 'orbit-secrets'
      const wrapper = shallowMount(component, { global })
      await flushPromises()
      expect(wrapper.getComponent(SecretsList).props()).toMatchObject({
        editAvailable: false,
        copyAvailable: false,
      })
      orbit.getCurrentOrbitPermissions = { orbit_secret: [P.create, P.update] }
      await nextTick()
      expect(wrapper.getComponent(SecretsList).props()).toMatchObject({
        editAvailable: true,
        copyAvailable: false,
      })
      orbit.getCurrentOrbitPermissions = { orbit_secret: [P.read] }
      await nextTick()
      expect(wrapper.getComponent(SecretsList).props()).toMatchObject({
        editAvailable: false,
        copyAvailable: true,
      })
    },
  )

  it('honors editAvailable and copyAvailable independently', async () => {
    const wrapper = shallowMount(SecretsList, {
      props: { organizationId: 'organization', editAvailable: false, copyAvailable: false },
    })
    expect(wrapper.find('.actions button-stub').exists()).toBe(false)
    expect(wrapper.find('.eye-button').exists()).toBe(false)
    expect(wrapper.findComponent(SecretsEditor).exists()).toBe(false)
    expect(wrapper.findComponent(SecretModal).exists()).toBe(false)
    await wrapper.setProps({ editAvailable: true })
    expect(wrapper.find('.actions button-stub').exists()).toBe(true)
    expect(wrapper.find('.eye-button').exists()).toBe(false)
    await wrapper.get('.actions button-stub').trigger('click')
    expect(wrapper.getComponent(SecretsEditor).props('visible')).toBe(true)
    expect(wrapper.getComponent(SecretsEditor).props('deleteAvailable')).toBe(false)
    orbit.getCurrentOrbitPermissions = { orbit_secret: [P.delete] }
    await nextTick()
    expect(wrapper.getComponent(SecretsEditor).props('deleteAvailable')).toBe(true)
    await wrapper.setProps({ editAvailable: false, copyAvailable: true })
    expect(wrapper.findComponent(SecretsEditor).exists()).toBe(false)
    await wrapper.get('.eye-button').trigger('click')
    expect(wrapper.getComponent(SecretModal).props('visible')).toBe(true)
    await wrapper.setProps({ copyAvailable: false })
    expect(wrapper.findComponent(SecretModal).exists()).toBe(false)
  })

  it('uses the same mask for empty, short and long secret values without rendering plaintext', () => {
    const original = secrets.secretsList
    secrets.secretsList = ['', 'abc', 'a'.repeat(50)].map((value, index) => ({
      id: String(index),
      name: 'Key',
      value,
      tags: [],
    }))
    const wrapper = shallowMount(SecretsList, { props: { organizationId: 'organization' } })
    expect(wrapper.findAll('.secret-hidden').map((mask) => mask.text())).toEqual([
      SECRET_MASK,
      SECRET_MASK,
      SECRET_MASK,
    ])
    expect(wrapper.find('.secret-revealed').exists()).toBe(false)
    expect(wrapper.html()).not.toContain('abc')
    secrets.secretsList = original
  })
})

it('masks the S3 secret key while leaving the access key readable', () => {
  const wrapper = mount(S3BucketForm, {
    props: { loading: false },
    global: {
      directives: { tooltip: () => undefined },
      stubs: {
        Form: { template: '<form><slot :endpoint="{}" :bucket_name="{}" :region="{}" /></form>' },
        InputText: { template: '<input />' },
        ToggleSwitch: true,
        Button: true,
      },
    },
  })
  expect(wrapper.get('#secret_key').attributes('type')).toBe('password')
  expect(wrapper.get('#access_key').attributes('type')).toBe('text')
})

describe('resource edit controls', () => {
  it('requires satellite:update for settings and API key regeneration', async () => {
    const data = {
      id: 'satellite',
      orbit_id: 'orbit',
      name: 'Satellite',
      description: '',
      base_url: null,
      paired: true,
      capabilities: {},
      present_capabilities: [],
      created_at: '',
      updated_at: '',
      last_seen_at: '',
      status: SatelliteStatusEnum.active,
    }
    const wrapper = shallowMount(SatellitesCard, {
      props: { data },
      global: { directives: { tooltip: () => undefined } },
    })
    expect(wrapper.findComponent({ name: 'Button' }).exists()).toBe(false)
    expect(wrapper.findComponent(SatellitesEditModal).exists()).toBe(false)
    expect(wrapper.findComponent(SatellitesApiKeyModal).exists()).toBe(false)
    orbit.getCurrentOrbitPermissions = { satellite: [P.update] }
    await nextTick()
    expect(wrapper.findComponent({ name: 'Button' }).exists()).toBe(true)
    expect(wrapper.findComponent(SatellitesEditModal).exists()).toBe(true)
    expect(wrapper.findComponent(SatellitesApiKeyModal).exists()).toBe(true)
    orbit.getCurrentOrbitPermissions = { satellite: [P.read] }
    await nextTick()
    expect(wrapper.findComponent(SatellitesEditModal).exists()).toBe(false)
  })
})
