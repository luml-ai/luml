import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useOrbitsStore } from '@/stores/orbits'
import { dataforceApi } from '@/lib/api'
import type {
  Orbit,
  OrbitDetails,
  CreateOrbitPayload,
  UpdateOrbitPayload,
  AddMemberToOrbitPayload,
  OrbitMember,
} from '@/lib/api/DataforceApi.interfaces'
import { OrbitRoleEnum } from '@/components/orbits/orbits.interfaces'
import { PermissionEnum } from '@/lib/api/DataforceApi.interfaces'

vi.mock('@/lib/api', () => ({
  dataforceApi: {
    getOrganizationOrbits: vi.fn(),
    createOrbit: vi.fn(),
    updateOrbit: vi.fn(),
    deleteOrbit: vi.fn(),
    addMemberToOrbit: vi.fn(),
    getOrbitDetails: vi.fn(),
    deleteOrbitMember: vi.fn(),
    updateOrbitMember: vi.fn(),
  },
}))

const mockApi = vi.mocked(dataforceApi)
const baseOrbit: Orbit = {
  id: 1,
  name: 'Default Orbit',
  organization_id: 1,
  total_members: 0,
  created_at: new Date(),
  updated_at: null,
  bucket_secret_id: 0,
  total_collections: 0,
  role: OrbitRoleEnum.member,
  permissions: {
    orbit: PermissionEnum.read,
    orbit_user: PermissionEnum.read,
    model: PermissionEnum.create,
    collection: PermissionEnum.create,
  },
}

const createMockOrbit = (id: number, overrides: Partial<Orbit> = {}): Orbit => ({
  ...baseOrbit,
  id,
  name: `Orbit ${id}`,
  ...overrides,
})

const createMockMember = (
  id: number,
  orbit_id: number,
  userId: number,
  role: OrbitRoleEnum,
): OrbitMember => ({
  id,
  orbit_id,
  role,
  user: {
    email: `user${userId}@example.test`,
    full_name: `User ${userId}`,
    disabled: false,
    id: String(userId),
    has_api_key: false,
  } as any,
})

const createMockOrbitDetails = (id: number, overrides: Partial<OrbitDetails> = {}): OrbitDetails =>
  ({
    ...createMockOrbit(id),
    members: overrides.members ?? [createMockMember(101, id, 42, OrbitRoleEnum.member)],
    ...overrides,
  }) as OrbitDetails

describe('OrbitsStore', () => {
  let store: ReturnType<typeof useOrbitsStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useOrbitsStore()
    vi.clearAllMocks()
  })

  describe(' 1 - initial state', () => {
    it('has empty list and null details', () => {
      expect(store.orbitsList).toEqual([])
      expect(store.currentOrbitDetails).toBeNull()
      expect(store.getCurrentOrbitPermissions).toBeUndefined()
    })
  })

  describe('2 - loadOrbitsList', () => {
    it('loads orbits into state', async () => {
      const mockOrbits = [createMockOrbit(1), createMockOrbit(2)]
      mockApi.getOrganizationOrbits.mockResolvedValueOnce(mockOrbits)
      await store.loadOrbitsList(123)
      expect(mockApi.getOrganizationOrbits).toHaveBeenCalledWith(123)
      expect(store.orbitsList).toEqual(mockOrbits)
    })

    it('handles API error (rejects)', async () => {
      mockApi.getOrganizationOrbits.mockRejectedValueOnce(new Error('API error'))
      await expect(store.loadOrbitsList(123)).rejects.toThrow('API error')
      expect(store.orbitsList).toEqual([])
    })
  })

  describe('3 - createOrbit', () => {
    it('adds new orbit to list', async () => {
      const newOrbit = createMockOrbit(3, { name: 'New Orbit' })
      mockApi.createOrbit.mockResolvedValueOnce(newOrbit)
      store.orbitsList = [createMockOrbit(1)]

      const payload: CreateOrbitPayload = {
        name: 'New Orbit',
        bucket_secret_id: 42,
        members: [],
        notify: false,
      }

      await store.createOrbit(123, payload)
      expect(mockApi.createOrbit).toHaveBeenCalledWith(123, payload)
      expect(store.orbitsList).toContainEqual(newOrbit)
    })

    it('does not add an orbit to the list if the API call fails', async () => {
      const initialOrbits = [createMockOrbit(1)]
      store.orbitsList = [...initialOrbits]
      mockApi.createOrbit.mockRejectedValueOnce(new Error('Creation failed'))
      const payload: CreateOrbitPayload = {
        name: 'Failed Orbit',
        bucket_secret_id: 1,
        members: [],
        notify: false,
      }

      await expect(store.createOrbit(123, payload)).rejects.toThrow('Creation failed')
      expect(store.orbitsList).toEqual(initialOrbits)
      expect(store.orbitsList).toHaveLength(1)
    })
  })

  describe('4 - updateOrbit', () => {
    it('updates orbit when id exists', async () => {
      store.orbitsList = [createMockOrbit(1), createMockOrbit(2)]

      const updated = createMockOrbit(1, { name: 'Updated Orbit', bucket_secret_id: 99 })
      mockApi.updateOrbit.mockResolvedValueOnce(updated)

      const payload: UpdateOrbitPayload = {
        id: 1,
        name: 'Updated Orbit',
        bucket_secret_id: 99,
      }

      await store.updateOrbit(123, payload)
      expect(mockApi.updateOrbit).toHaveBeenCalledWith(123, payload)
      expect(store.orbitsList[0]).toEqual(updated)
      expect(store.orbitsList[1]).toEqual(createMockOrbit(2))
    })

    it('keeps list unchanged when id not found', async () => {
      const original = [createMockOrbit(1)]
      store.orbitsList = [...original]
      mockApi.updateOrbit.mockResolvedValueOnce(createMockOrbit(999))
      const payload: UpdateOrbitPayload = { id: 999, name: 'Nope', bucket_secret_id: 0 }
      await store.updateOrbit(123, payload)
      expect(store.orbitsList).toEqual(original)
    })

    it('does not update the orbit in the list if the API call fails', async () => {
      const initialOrbits = [createMockOrbit(1, { name: 'Original Name' }), createMockOrbit(2)]
      store.orbitsList = [...initialOrbits]
      mockApi.updateOrbit.mockRejectedValueOnce(new Error('Update failed'))

      const payload: UpdateOrbitPayload = {
        id: 1,
        name: 'Attempted Update Name',
        bucket_secret_id: 99,
      }

      await expect(store.updateOrbit(123, payload)).rejects.toThrow('Update failed')
      expect(store.orbitsList).toEqual(initialOrbits)
      expect(store.orbitsList[0].name).toBe('Original Name')
    })
  })

  describe('5 - deleteOrbit', () => {
    it('removes orbit from list', async () => {
      store.orbitsList = [createMockOrbit(1), createMockOrbit(2), createMockOrbit(3)]
      mockApi.deleteOrbit.mockResolvedValueOnce({ detail: 'success' })
      await store.deleteOrbit(123, 2)
      expect(mockApi.deleteOrbit).toHaveBeenCalledWith(123, 2)
      expect(store.orbitsList).toHaveLength(2)
      expect(store.orbitsList.find((o) => o.id === 2)).toBeUndefined()
    })

    it('does nothing if id not found', async () => {
      const original = [createMockOrbit(1)]
      store.orbitsList = [...original]
      mockApi.deleteOrbit.mockResolvedValueOnce({ detail: 'success' })
      await store.deleteOrbit(123, 999)
      expect(store.orbitsList).toEqual(original)
    })

    it('does not remove the orbit from the list if the API call fails', async () => {
      const initialOrbits = [createMockOrbit(1), createMockOrbit(2), createMockOrbit(3)]
      store.orbitsList = [...initialOrbits]
      mockApi.deleteOrbit.mockRejectedValueOnce(new Error('Deletion failed'))
      await expect(store.deleteOrbit(123, 2)).rejects.toThrow('Deletion failed')
      expect(store.orbitsList).toEqual(initialOrbits)
      expect(store.orbitsList).toHaveLength(3)
    })
  })

  describe('6 - members', () => {
    it('addMemberToOrbit calls API and returns OrbitMember', async () => {
      const payload: AddMemberToOrbitPayload = {
        user_id: 42,
        orbit_id: 1,
        role: OrbitRoleEnum.member,
      }

      const addedMember = createMockMember(201, 1, 42, OrbitRoleEnum.member)
      mockApi.addMemberToOrbit.mockResolvedValueOnce(addedMember)
      const result = await store.addMemberToOrbit(123, payload)
      expect(mockApi.addMemberToOrbit).toHaveBeenCalledWith(123, payload)
      expect(result).toEqual(addedMember)
    })

    it('getOrbitDetails returns details', async () => {
      const details = createMockOrbitDetails(1)
      mockApi.getOrbitDetails.mockResolvedValueOnce(details)
      const result = await store.getOrbitDetails(123, 1)
      expect(mockApi.getOrbitDetails).toHaveBeenCalledWith(123, 1)
      expect(result).toEqual(details)
    })

    it('deleteMember calls API', async () => {
      mockApi.deleteOrbitMember.mockResolvedValueOnce({ detail: 'success' })
      await store.deleteMember(123, 1, 42)
      expect(mockApi.deleteOrbitMember).toHaveBeenCalledWith(123, 1, 42)
    })

    it('updateMember calls API and returns OrbitMember', async () => {
      const data = { id: 42, role: OrbitRoleEnum.admin }
      const updatedMember = createMockMember(42, 1, 42, OrbitRoleEnum.admin)
      mockApi.updateOrbitMember.mockResolvedValueOnce(updatedMember)
      const result = await store.updateMember(123, 1, data)
      expect(mockApi.updateOrbitMember).toHaveBeenCalledWith(123, 1, data)
      expect(result).toEqual(updatedMember)
    })
  })

  describe('7 - local state helpers', () => {
    it('setCurrentOrbitDetails works', () => {
      const perm = {
        orbit: PermissionEnum.read,
        orbit_user: PermissionEnum.update,
        model: PermissionEnum.create,
        collection: PermissionEnum.delete,
      }

      const details = createMockOrbitDetails(1, { permissions: perm })
      store.setCurrentOrbitDetails(details)
      expect(store.currentOrbitDetails).toEqual(details)
      expect(store.getCurrentOrbitPermissions).toEqual(details.permissions)
    })

    it('reset clears state', () => {
      store.orbitsList = [createMockOrbit(1)]

      store.setCurrentOrbitDetails(createMockOrbitDetails(1))
      store.reset()
      expect(store.orbitsList).toEqual([])
      expect(store.currentOrbitDetails).toBeNull()
      expect(store.getCurrentOrbitPermissions).toBeUndefined()
    })
  })
})
