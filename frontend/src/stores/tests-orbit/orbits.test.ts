import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useOrbitsStore } from '@/stores/orbits'
import { api } from '@/lib/api'
import type {
  Orbit,
  OrbitDetails,
  CreateOrbitPayload,
  UpdateOrbitPayload,
  AddMemberToOrbitPayload,
  OrbitMember,
} from '@/lib/api/api.interfaces'
import { OrbitRoleEnum } from '@/components/orbits/orbits.interfaces'
import { PermissionEnum } from '@/lib/api/api.interfaces'

vi.mock('@/lib/api', () => ({
  api: {
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

const mockApi = vi.mocked(api)
const baseOrbit: Orbit = {
  id: '11111111-1111-1111-1111-111111111111',
  name: 'Default Orbit',
  organization_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  total_members: 0,
  created_at: new Date(),
  updated_at: null,
  bucket_secret_id: '0',
  total_collections: 0,
  role: OrbitRoleEnum.member,
  permissions: {
    orbit: PermissionEnum.read,
    orbit_user: PermissionEnum.read,
    model: PermissionEnum.create,
    collection: PermissionEnum.create,
  },
}

const createMockOrbit = (id: string, overrides: Partial<Orbit> = {}): Orbit => ({
  ...baseOrbit,
  id,
  name: `Orbit ${id}`,
  ...overrides,
})

const createMockMember = (
  id: string,
  orbit_id: string,
  userId: string,
  role: OrbitRoleEnum,
): OrbitMember => ({
  id,
  orbit_id,
  role,
  user: {
    email: `user${userId}@example.test`,
    full_name: `User ${userId}`,
    disabled: false,
    id: userId,
    has_api_key: false,
  } as any,
  created_at: new Date(),
  updated_at: null,
})

const createMockOrbitDetails = (id: string, overrides: Partial<OrbitDetails> = {}): OrbitDetails =>
  ({
    ...createMockOrbit(id),
    members: overrides.members ?? [
      createMockMember(
        '22222222-2222-2222-2222-222222222222',
        id,
        '33333333-3333-3333-3333-333333333333',
        OrbitRoleEnum.member,
      ),
    ],
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
      const mockOrbits = [
        createMockOrbit('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001'),
        createMockOrbit('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0002'),
      ]
      mockApi.getOrganizationOrbits.mockResolvedValueOnce(mockOrbits)
      await store.loadOrbitsList('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb')
      expect(mockApi.getOrganizationOrbits).toHaveBeenCalledWith(
        'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
      )
      expect(store.orbitsList).toEqual(mockOrbits)
    })

    it('handles API error (rejects)', async () => {
      mockApi.getOrganizationOrbits.mockRejectedValueOnce(new Error('API error'))
      await expect(store.loadOrbitsList('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb')).rejects.toThrow(
        'API error',
      )
      expect(store.orbitsList).toEqual([])
    })
  })

  describe('3 - createOrbit', () => {
    it('adds new orbit to list', async () => {
      const newOrbit = createMockOrbit('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0003', {
        name: 'New Orbit',
      })
      mockApi.createOrbit.mockResolvedValueOnce(newOrbit)
      store.orbitsList = [createMockOrbit('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001')]

      const payload: CreateOrbitPayload = {
        name: 'New Orbit',
        bucket_secret_id: '42',
        members: [],
        notify: false,
      }

      await store.createOrbit('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', payload)
      expect(mockApi.createOrbit).toHaveBeenCalledWith(
        'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        payload,
      )
      expect(store.orbitsList).toContainEqual(newOrbit)
    })

    it('does not add an orbit to the list if the API call fails', async () => {
      const initialOrbits = [createMockOrbit('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001')]
      store.orbitsList = [...initialOrbits]
      mockApi.createOrbit.mockRejectedValueOnce(new Error('Creation failed'))
      const payload: CreateOrbitPayload = {
        name: 'Failed Orbit',
        bucket_secret_id: '1',
        members: [],
        notify: false,
      }

      await expect(
        store.createOrbit('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', payload),
      ).rejects.toThrow('Creation failed')
      expect(store.orbitsList).toEqual(initialOrbits)
      expect(store.orbitsList).toHaveLength(1)
    })
  })

  describe('4 - updateOrbit', () => {
    it('updates orbit when id exists', async () => {
      store.orbitsList = [
        createMockOrbit('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001'),
        createMockOrbit('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0002'),
      ]

      const updated = createMockOrbit('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001', {
        name: 'Updated Orbit',
        bucket_secret_id: '99',
      })
      mockApi.updateOrbit.mockResolvedValueOnce(updated)

      const payload: UpdateOrbitPayload = {
        id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001',
        name: 'Updated Orbit',
        bucket_secret_id: '99',
      }

      await store.updateOrbit('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', payload)
      expect(mockApi.updateOrbit).toHaveBeenCalledWith(
        'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        payload,
      )
      expect(store.orbitsList[0]).toEqual(updated)
      expect(store.orbitsList[1]).toEqual(createMockOrbit('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0002'))
    })

    it('keeps list unchanged when id not found', async () => {
      const original = [createMockOrbit('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001')]
      store.orbitsList = [...original]
      mockApi.updateOrbit.mockResolvedValueOnce(
        createMockOrbit('ffffffff-ffff-ffff-ffff-ffffffffffff'),
      )
      const payload: UpdateOrbitPayload = {
        id: 'ffffffff-ffff-ffff-ffff-ffffffffffff',
        name: 'Nope',
        bucket_secret_id: '0 ',
      }
      await store.updateOrbit('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', payload)
      expect(store.orbitsList).toEqual(original)
    })

    it('does not update the orbit in the list if the API call fails', async () => {
      const initialOrbits = [
        createMockOrbit('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001', { name: 'Original Name' }),
        createMockOrbit('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0002'),
      ]
      store.orbitsList = [...initialOrbits]
      mockApi.updateOrbit.mockRejectedValueOnce(new Error('Update failed'))

      const payload: UpdateOrbitPayload = {
        id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001',
        name: 'Attempted Update Name',
        bucket_secret_id: '99',
      }

      await expect(
        store.updateOrbit('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', payload),
      ).rejects.toThrow('Update failed')
      expect(store.orbitsList).toEqual(initialOrbits)
      expect(store.orbitsList[0].name).toBe('Original Name')
    })
  })

  describe('5 - deleteOrbit', () => {
    it('removes orbit from list', async () => {
      store.orbitsList = [
        createMockOrbit('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001'),
        createMockOrbit('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0002'),
        createMockOrbit('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0003'),
      ]
      mockApi.deleteOrbit.mockResolvedValueOnce({ detail: 'success' })
      await store.deleteOrbit(
        'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0002',
      )
      expect(mockApi.deleteOrbit).toHaveBeenCalledWith(
        'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0002',
      )
      expect(store.orbitsList).toHaveLength(2)
      expect(
        store.orbitsList.find((o) => o.id === 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0002'),
      ).toBeUndefined()
    })

    it('does nothing if id not found', async () => {
      const original = [createMockOrbit('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001')]
      store.orbitsList = [...original]
      mockApi.deleteOrbit.mockResolvedValueOnce({ detail: 'success' })
      await store.deleteOrbit(
        'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        'ffffffff-ffff-ffff-ffff-ffffffffffff',
      )
      expect(store.orbitsList).toEqual(original)
    })

    it('does not remove the orbit from the list if the API call fails', async () => {
      const initialOrbits = [
        createMockOrbit('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001'),
        createMockOrbit('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0002'),
        createMockOrbit('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0003'),
      ]
      store.orbitsList = [...initialOrbits]
      mockApi.deleteOrbit.mockRejectedValueOnce(new Error('Deletion failed'))
      await expect(
        store.deleteOrbit(
          'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
          'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0002',
        ),
      ).rejects.toThrow('Deletion failed')
      expect(store.orbitsList).toEqual(initialOrbits)
      expect(store.orbitsList).toHaveLength(3)
    })
  })

  describe('6 - members', () => {
    it('addMemberToOrbit calls API and returns OrbitMember', async () => {
      const payload: AddMemberToOrbitPayload = {
        user_id: '33333333-3333-3333-3333-333333333333',
        orbit_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001',
        role: OrbitRoleEnum.member,
      }

      const addedMember = createMockMember(
        '44444444-4444-4444-4444-444444444444',
        'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001',
        '33333333-3333-3333-3333-333333333333',
        OrbitRoleEnum.member,
      )
      mockApi.addMemberToOrbit.mockResolvedValueOnce(addedMember)
      const result = await store.addMemberToOrbit('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', payload)
      expect(mockApi.addMemberToOrbit).toHaveBeenCalledWith(
        'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        payload,
      )
      expect(result).toEqual(addedMember)
    })

    it('getOrbitDetails returns details', async () => {
      const details = createMockOrbitDetails('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001')
      mockApi.getOrbitDetails.mockResolvedValueOnce(details)
      const result = await store.getOrbitDetails(
        'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001',
      )
      expect(mockApi.getOrbitDetails).toHaveBeenCalledWith(
        'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001',
      )
      expect(result).toEqual(details)
    })

    it('deleteMember calls API', async () => {
      mockApi.deleteOrbitMember.mockResolvedValueOnce({ detail: 'success' })
      await store.deleteMember(
        'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001',
        '33333333-3333-3333-3333-333333333333',
      )
      expect(mockApi.deleteOrbitMember).toHaveBeenCalledWith(
        'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001',
        '33333333-3333-3333-3333-333333333333',
      )
    })

    it('updateMember calls API and returns OrbitMember', async () => {
      const data = { id: '33333333-3333-3333-3333-333333333333', role: OrbitRoleEnum.admin }
      const updatedMember = createMockMember(
        '33333333-3333-3333-3333-333333333333',
        'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001',
        '33333333-3333-3333-3333-333333333333',
        OrbitRoleEnum.admin,
      )
      mockApi.updateOrbitMember.mockResolvedValueOnce(updatedMember)
      const result = await store.updateMember(
        'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001',
        data,
      )
      expect(mockApi.updateOrbitMember).toHaveBeenCalledWith(
        'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001',
        data,
      )
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

      const details = createMockOrbitDetails('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001', {
        permissions: perm,
      })
      store.setCurrentOrbitDetails(details)
      expect(store.currentOrbitDetails).toEqual(details)
      expect(store.getCurrentOrbitPermissions).toEqual(details.permissions)
    })

    it('reset clears state', () => {
      store.orbitsList = [createMockOrbit('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001')]

      store.setCurrentOrbitDetails(createMockOrbitDetails('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001'))
      store.reset()
      expect(store.orbitsList).toEqual([])
      expect(store.currentOrbitDetails).toBeNull()
      expect(store.getCurrentOrbitPermissions).toBeUndefined()
    })
  })
})
