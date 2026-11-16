import { createPinia, setActivePinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useAuthStore } from '../auth'
import { useUserStore } from '../user'
import { useOrganizationStore } from '../organization'
import { useOrbitsStore } from '../orbits'
import { useCollectionsStore } from '../collections'
import { useTracksStore } from '../tracks'
import { useDeploymentsStore } from '../deployments'
import { useSecretsStore } from '../orbit-secrets'
import { useInvitationsStore } from '../invitations'
import { LocalStorageService } from '@/utils/services/LocalStorageService'
import type { Organization } from '@/lib/api/api.interfaces'
import type { IUser } from '../user.interfaces'

const api = vi.hoisted(() => ({
  getMe: vi.fn(),
  logout: vi.fn(),
  getInvitations: vi.fn(),
  getOrganizations: vi.fn(),
  getOrganizationOrbits: vi.fn(),
  orbitCollections: { getCollection: vi.fn(), getCollectionsTags: vi.fn() },
  orbitTracks: { getTrack: vi.fn(), listStages: vi.fn() },
  orbitSecrets: { getSecrets: vi.fn() },
}))
vi.mock('@/lib/api', () => ({ api }))
vi.mock('@/lib/analytics/AnalyticsService', () => ({
  AnalyticsService: { identify: vi.fn() },
}))
vi.mock('vue-router', () => ({
  useRoute: () => ({ meta: {}, params: { organizationId: 'org-1', id: 'orbit-1' } }),
  useRouter: () => ({ push: vi.fn() }),
}))

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}

describe('logout state cleanup', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.resetAllMocks()
    api.getMe.mockResolvedValue({ id: 'user-1' })
    api.getInvitations.mockResolvedValue([])
    api.getOrganizations.mockResolvedValue([])
    api.getOrganizationOrbits.mockResolvedValue([])
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => vi.restoreAllMocks())

  function stores() {
    return {
      auth: useAuthStore(),
      user: useUserStore(),
      organization: useOrganizationStore(),
      orbits: useOrbitsStore(),
      collections: useCollectionsStore(),
      tracks: useTracksStore(),
      deployments: useDeploymentsStore(),
      secrets: useSecretsStore(),
      invitations: useInvitationsStore(),
    }
  }

  it.each([false, true])('clears all session data when logout fails: %s', async (fails) => {
    const s = stores()
    await s.auth.checkIsLoggedIn()
    await flushPromises()
    s.organization.availableOrganizations = [{ id: 'org-1' }] as Organization[]
    s.organization.setCurrentOrganizationId('org-1')
    s.organization.organizationDetails = { id: 'org-1' } as NonNullable<
      typeof s.organization.organizationDetails
    >
    s.orbits.orbitsList = [{ id: 'orbit-1' }] as typeof s.orbits.orbitsList
    s.orbits.currentOrbitId = 'orbit-1'
    s.orbits.currentOrbitDetails = { id: 'orbit-1' } as NonNullable<
      typeof s.orbits.currentOrbitDetails
    >
    LocalStorageService.set('currentOrbitId', 'orbit-1')
    s.collections.collectionsList = [{ id: 'collection-1' }] as typeof s.collections.collectionsList
    s.collections.currentCollection = s.collections.collectionsList[0]
    s.collections.collectionsTags = ['private']
    s.collections.showCreator()
    s.tracks.tracksList = [{ id: 'track-1' }] as typeof s.tracks.tracksList
    s.tracks.currentTrack = s.tracks.tracksList[0]
    s.tracks.trackStages = [{ id: 'stage-1' }] as typeof s.tracks.trackStages
    s.tracks.showEditor({ id: 'track-1', name: 'Private', description: undefined, stages: [] })
    s.tracks.showCreator()
    s.deployments.setDeployments([{ id: 'deployment-1' }] as typeof s.deployments.deployments)
    s.deployments.showCreator()
    s.secrets.secretsList = [{ id: 'secret-1' }] as typeof s.secrets.secretsList
    s.secrets.showCreator()
    s.invitations.invitations = [{ id: 'invitation-1' }] as typeof s.invitations.invitations
    if (fails) api.logout.mockRejectedValue(new Error('Network unavailable'))

    await s.auth.logout()

    expect(s.auth.isAuth).toBe(false)
    expect(s.user.getUserId).toBeUndefined()
    expect(s.organization.availableOrganizations).toEqual([])
    expect(s.organization.currentOrganization).toBeNull()
    expect(s.organization.organizationDetails).toBeNull()
    expect(s.orbits.orbitsList).toEqual([])
    expect(s.orbits.currentOrbitId).toBeNull()
    expect(s.orbits.currentOrbitDetails).toBeNull()
    expect(localStorage.getItem('currentOrganizationId')).toBeNull()
    expect(localStorage.getItem('currentOrbitId')).toBeNull()
    expect(s.collections.collectionsList).toEqual([])
    expect(s.collections.currentCollection).toBeNull()
    expect(s.collections.collectionsTags).toEqual([])
    expect(s.collections.creatorVisible).toBe(false)
    expect(s.tracks.tracksList).toEqual([])
    expect(s.tracks.currentTrack).toBeNull()
    expect(s.tracks.trackStages).toEqual([])
    expect(s.tracks.editableTrack).toBeNull()
    expect(s.tracks.creatorVisible).toBe(false)
    expect(s.deployments.deployments).toEqual([])
    expect(s.deployments.creatorVisible).toBe(false)
    expect(s.secrets.secretsList).toEqual([])
    expect(s.secrets.creatorVisible).toBe(false)
    expect(s.invitations.invitations).toEqual([])
  })

  it('resets persisted and store state even without a loaded user', async () => {
    const s = stores()
    LocalStorageService.set('currentOrganizationId', 'org-1')
    LocalStorageService.set('currentOrbitId', 'orbit-1')
    s.secrets.secretsList = [{ id: 'secret-1' }] as typeof s.secrets.secretsList

    await s.auth.logout()

    expect(localStorage.getItem('currentOrganizationId')).toBeNull()
    expect(localStorage.getItem('currentOrbitId')).toBeNull()
    expect(s.secrets.secretsList).toEqual([])
  })

  it('does not restore the user after logout while a session check is pending', async () => {
    const s = stores()
    const pending = deferred<IUser>()
    api.getMe.mockReturnValue(pending.promise)
    const check = s.auth.checkIsLoggedIn()

    await s.auth.logout()
    pending.resolve({ id: 'old-user' } as IUser)
    await check
    await flushPromises()

    expect(s.user.getUserId).toBeUndefined()
    expect(s.auth.isAuth).toBe(false)
    expect(api.getInvitations).not.toHaveBeenCalled()
    expect(api.getOrganizations).not.toHaveBeenCalled()
  })

  it('does not start organization loading when invitations finish after logout', async () => {
    const s = stores()
    const pending = deferred<[]>()
    api.getInvitations.mockReturnValue(pending.promise)
    await s.auth.checkIsLoggedIn()
    await flushPromises()

    await s.auth.logout()
    pending.resolve([])
    await flushPromises()

    expect(api.getOrganizations).not.toHaveBeenCalled()
    expect(s.invitations.isLoaded).toBe(false)
  })

  it('does not restore organizations or storage when their list arrives after logout', async () => {
    const s = stores()
    const pending = deferred<Organization[]>()
    api.getOrganizations.mockReturnValue(pending.promise)
    await s.auth.checkIsLoggedIn()
    await flushPromises()
    expect(api.getOrganizations).toHaveBeenCalledOnce()

    await s.auth.logout()
    pending.resolve([{ id: 'old-organization' }] as Organization[])
    await flushPromises()

    expect(s.organization.availableOrganizations).toEqual([])
    expect(s.organization.currentOrganization).toBeNull()
    expect(localStorage.getItem('currentOrganizationId')).toBeNull()
    expect(api.getOrganizationOrbits).not.toHaveBeenCalled()
  })

  it('does not restore collections, tracks, stages, tags or secrets from pending reads', async () => {
    const s = stores()
    const collection = deferred<NonNullable<typeof s.collections.currentCollection>>()
    const tags = deferred<string[]>()
    const track = deferred<NonNullable<typeof s.tracks.currentTrack>>()
    const stages = deferred<typeof s.tracks.trackStages>()
    const secrets = deferred<typeof s.secrets.secretsList>()
    api.orbitCollections.getCollection.mockReturnValue(collection.promise)
    api.orbitCollections.getCollectionsTags.mockReturnValue(tags.promise)
    api.orbitTracks.getTrack.mockReturnValue(track.promise)
    api.orbitTracks.listStages.mockReturnValue(stages.promise)
    api.orbitSecrets.getSecrets.mockReturnValue(secrets.promise)
    const requests = [
      s.collections.setCurrentCollection('collection-1'),
      s.collections.getCollectionsTags(),
      s.tracks.setCurrentTrack('track-1'),
      s.tracks.listStages('track-1'),
      s.secrets.loadSecrets('org-1', 'orbit-1'),
    ]

    await s.auth.logout()
    collection.resolve({ id: 'old-collection' } as NonNullable<
      typeof s.collections.currentCollection
    >)
    tags.resolve(['private'])
    track.resolve({ id: 'old-track' } as NonNullable<typeof s.tracks.currentTrack>)
    stages.resolve([{ id: 'old-stage' }] as typeof s.tracks.trackStages)
    secrets.resolve([{ id: 'old-secret' }] as typeof s.secrets.secretsList)
    await Promise.all(requests)

    expect(s.collections.currentCollection).toBeNull()
    expect(s.collections.collectionsTags).toEqual([])
    expect(s.tracks.currentTrack).toBeNull()
    expect(s.tracks.trackStages).toEqual([])
    expect(s.secrets.secretsList).toEqual([])
    expect(api.orbitTracks.listStages).toHaveBeenCalledOnce()
  })
})
