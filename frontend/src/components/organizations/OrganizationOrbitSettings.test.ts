import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PrimeVue from 'primevue/config'
import { Dialog } from 'primevue'
import type { Member, OrbitMember } from '@/lib/api/api.interfaces'
import { OrganizationRoleEnum } from './organization.interfaces'
import { OrbitRoleEnum } from '../orbits/orbits.interfaces'
import OrganizationOrbitSettings from './OrganizationOrbitSettings.vue'

const mocks = vi.hoisted(() => ({
  getOrbitDetails: vi.fn(),
  addMemberToOrbit: vi.fn(),
  updateMember: vi.fn(),
  deleteMember: vi.fn(),
  toast: vi.fn(),
}))

const member = (id: string): Member => ({
  id: `organization-member-${id}`,
  organization_id: 'organization',
  role: OrganizationRoleEnum.member,
  user: {
    id,
    email: `${id}@example.com`,
    full_name: id,
    photo: '',
    disabled: false,
    has_api_key: false,
  },
  created_at: new Date('2025-01-01'),
  updated_at: null,
})

const orbitMember = (id: string): OrbitMember => ({
  ...member(id),
  id: `orbit-member-${id}`,
  orbit_id: 'orbit',
  role: OrbitRoleEnum.member,
})

const organizationStore = {
  currentOrganization: { id: 'organization' },
  organizationDetails: {
    id: 'organization',
    members: [member('existing'), member('new'), member('other'), member('self')],
  },
}

vi.mock('@/stores/orbits', () => ({ useOrbitsStore: () => mocks }))
vi.mock('@/stores/organization', () => ({ useOrganizationStore: () => organizationStore }))
vi.mock('@/stores/user', () => ({ useUserStore: () => ({ getUserId: 'self' }) }))
vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: mocks.toast }),
  useConfirm: () => ({ require: vi.fn() }),
}))

describe('OrganizationOrbitSettings', () => {
  let wrapper: ReturnType<typeof mount>
  let savedMember: OrbitMember

  beforeEach(() => {
    vi.resetAllMocks()
    savedMember = orbitMember('existing')
    mocks.getOrbitDetails.mockResolvedValue({ members: [savedMember] })
    mocks.addMemberToOrbit.mockImplementation(async (_organizationId, payload) =>
      orbitMember(payload.user_id),
    )
    mocks.updateMember.mockResolvedValue({})
    wrapper = mount(OrganizationOrbitSettings, {
      props: { orbitId: 'orbit' },
      global: {
        stubs: {
          Dialog: {
            props: ['visible'],
            template: '<div v-if="visible"><slot /><slot name="footer" /></div>',
          },
          Button: {
            props: ['disabled', 'loading'],
            emits: ['click'],
            template:
              '<button :disabled="disabled || loading" @click="$emit(\'click\')"><slot /></button>',
          },
          AutoComplete: {
            name: 'AutoComplete',
            props: ['modelValue', 'suggestions', 'disabled'],
            emits: ['update:modelValue', 'complete'],
            template: '<input :disabled="disabled" />',
          },
          Select: {
            props: ['modelValue', 'options', 'disabled'],
            emits: ['update:modelValue'],
            template:
              '<select :value="modelValue" :disabled="disabled" @change="$emit(\'update:modelValue\', $event.target.value)"><option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option></select>',
          },
          Avatar: true,
        },
      },
    })
  })

  afterEach(() => wrapper.unmount())

  const button = (label: string) => {
    const result = wrapper.findAll('button').find((item) => item.text() === label)
    if (!result) throw new Error(`Button not found: ${label}`)
    return result
  }
  const autocomplete = () => wrapper.findComponent({ name: 'AutoComplete' })
  const open = async () => {
    await wrapper.find('button').trigger('click')
    await flushPromises()
  }
  const selectUsers = async (...ids: string[]) => {
    autocomplete().vm.$emit('update:modelValue', ids.map(member))
    await flushPromises()
  }

  it('explains the add action and when role changes are saved', async () => {
    await open()
    expect(wrapper.text()).toContain('Click Add members to add selected users immediately.')
    expect(wrapper.text()).toContain('Role changes require Save changes.')
  })

  it('enables adding only after selecting users, regardless of search suggestions', async () => {
    await open()
    autocomplete().vm.$emit('complete', { query: 'new' })
    await flushPromises()
    expect(autocomplete().props('suggestions')).toHaveLength(1)
    expect(button('Add members').attributes('disabled')).toBeDefined()

    autocomplete().vm.$emit('complete', { query: 'no match' })
    await selectUsers('new')
    expect(autocomplete().props('suggestions')).toHaveLength(0)
    expect(button('Add members').attributes('disabled')).toBeUndefined()
    expect(mocks.addMemberToOrbit).not.toHaveBeenCalled()
  })

  it('adds selected members immediately and does not require a redundant save', async () => {
    await open()
    await selectUsers('new')
    await button('Add members').trigger('click')
    await flushPromises()

    expect(mocks.addMemberToOrbit).toHaveBeenCalledWith('organization', {
      orbit_id: 'orbit',
      user_id: 'new',
      role: OrbitRoleEnum.member,
    })
    expect(wrapper.findAll('select')).toHaveLength(2)
    expect(autocomplete().props('modelValue')).toEqual([])
    expect(button('Add members').attributes('disabled')).toBeDefined()
    expect(button('Save changes').attributes('disabled')).toBeDefined()
    expect(mocks.updateMember).not.toHaveBeenCalled()
    expect(mocks.toast).toHaveBeenCalledWith(
      expect.objectContaining({ detail: 'Members added to orbit' }),
    )
  })

  it('keeps role edits local until Save changes is clicked and updates only changed roles', async () => {
    await open()
    await selectUsers('new')
    await button('Add members').trigger('click')
    await flushPromises()
    await wrapper.find('select').setValue(OrbitRoleEnum.admin)

    expect(savedMember.role).toBe(OrbitRoleEnum.member)
    expect(mocks.updateMember).not.toHaveBeenCalled()
    expect(button('Save changes').attributes('disabled')).toBeUndefined()
    await button('Save changes').trigger('click')
    await flushPromises()
    expect(mocks.updateMember).toHaveBeenCalledTimes(1)
    expect(mocks.updateMember).toHaveBeenCalledWith('organization', 'orbit', {
      id: savedMember.id,
      role: OrbitRoleEnum.admin,
    })
    expect(wrapper.find('select').exists()).toBe(false)
  })

  it('requires Save changes for a role edit on a newly added member', async () => {
    await open()
    await selectUsers('new')
    await button('Add members').trigger('click')
    await flushPromises()
    await wrapper.get('.table-body .table-row:nth-child(2) select').setValue(OrbitRoleEnum.admin)
    await button('Save changes').trigger('click')
    await flushPromises()
    expect(mocks.updateMember).toHaveBeenCalledWith('organization', 'orbit', {
      id: 'orbit-member-new',
      role: OrbitRoleEnum.admin,
    })
  })

  it('disables saving when a role edit is reverted', async () => {
    await open()
    await wrapper.find('select').setValue(OrbitRoleEnum.admin)
    await wrapper.find('select').setValue(OrbitRoleEnum.member)
    expect(button('Save changes').attributes('disabled')).toBeDefined()
  })

  it('retains failed additions for retry without adding successful members twice', async () => {
    mocks.addMemberToOrbit.mockRejectedValueOnce(new Error('Add failed'))
    await open()
    await selectUsers('new', 'other')
    await button('Add members').trigger('click')
    await flushPromises()

    expect(wrapper.findAll('select')).toHaveLength(2)
    expect(autocomplete().props('modelValue')).toEqual([member('new')])
    expect(button('Save changes').attributes('disabled')).toBeDefined()
    expect(mocks.toast).toHaveBeenCalledWith(expect.objectContaining({ severity: 'error' }))
    await button('Add members').trigger('click')
    await flushPromises()
    expect(mocks.addMemberToOrbit).toHaveBeenCalledTimes(3)
    expect(wrapper.findAll('select')).toHaveLength(3)
    expect(autocomplete().props('modelValue')).toEqual([])
  })

  it('retains role changes when saving fails so the user can retry', async () => {
    mocks.updateMember.mockRejectedValueOnce(new Error('Save failed'))
    await open()
    await wrapper.find('select').setValue(OrbitRoleEnum.admin)
    await button('Save changes').trigger('click')
    await flushPromises()
    expect((wrapper.find('select').element as HTMLSelectElement).value).toBe(OrbitRoleEnum.admin)
    expect(button('Save changes').attributes('disabled')).toBeUndefined()
    expect(mocks.toast).toHaveBeenCalledWith(expect.objectContaining({ severity: 'error' }))
    await button('Save changes').trigger('click')
    await flushPromises()
    expect(mocks.updateMember).toHaveBeenCalledTimes(2)
    expect(wrapper.find('select').exists()).toBe(false)
  })

  it('prevents edits and repeated additions while an add request is pending', async () => {
    let resolveAdd!: (value: OrbitMember) => void
    mocks.addMemberToOrbit.mockReturnValueOnce(new Promise((resolve) => (resolveAdd = resolve)))
    await open()
    await selectUsers('new')
    await button('Add members').trigger('click')
    expect(button('Add members').attributes('disabled')).toBeDefined()
    expect(button('Save changes').attributes('disabled')).toBeDefined()
    expect(wrapper.find('select').attributes('disabled')).toBeDefined()
    expect(autocomplete().props('disabled')).toBe(true)
    resolveAdd(orbitMember('new'))
    await flushPromises()
    expect(wrapper.find('select').attributes('disabled')).toBeUndefined()
  })

  it('excludes current members and the signed-in user from suggestions by user id', async () => {
    await open()
    autocomplete().vm.$emit('complete', { query: '' })
    await flushPromises()
    expect(
      autocomplete()
        .props('suggestions')
        .map((item: Member) => item.user.id),
    ).toEqual(['new', 'other'])
  })

  describe('Escape with the PrimeVue dialog', () => {
    beforeEach(() => {
      wrapper.unmount()
      wrapper = mount(OrganizationOrbitSettings, {
        props: { orbitId: 'orbit' },
        global: {
          plugins: [PrimeVue],
          stubs: {
            transition: false,
            teleport: true,
            AutoComplete: true,
            Select: true,
            Avatar: true,
          },
        },
      })
    })

    it('stays open while initially loading and closes on Escape after loading completes', async () => {
      let resolveDetails!: (value: { members: OrbitMember[] }) => void
      mocks.getOrbitDetails.mockReturnValueOnce(
        new Promise((resolve) => (resolveDetails = resolve)),
      )
      await open()
      expect(wrapper.find('[role="dialog"]').exists()).toBe(true)

      document.dispatchEvent(new KeyboardEvent('keydown', { code: 'Escape' }))
      await flushPromises()
      expect(wrapper.findComponent(Dialog).props('visible')).toBe(true)

      resolveDetails({ members: [savedMember] })
      await flushPromises()
      document.dispatchEvent(new KeyboardEvent('keydown', { code: 'Escape' }))
      await flushPromises()
      await vi.waitFor(() => expect(wrapper.find('[role="dialog"]').exists()).toBe(false))
    })

    it('prevents Escape from closing during an addition and allows closing after it finishes', async () => {
      let resolveAdd!: (value: OrbitMember) => void
      mocks.addMemberToOrbit.mockReturnValueOnce(new Promise((resolve) => (resolveAdd = resolve)))
      await open()
      await selectUsers('new')
      await button('Add members').trigger('click')

      document.dispatchEvent(new KeyboardEvent('keydown', { code: 'Escape' }))
      await flushPromises()
      expect(wrapper.findComponent(Dialog).props('visible')).toBe(true)

      resolveAdd(orbitMember('new'))
      await flushPromises()
      expect(wrapper.text()).toContain('new')
      document.dispatchEvent(new KeyboardEvent('keydown', { code: 'Escape' }))
      await flushPromises()
      await vi.waitFor(() => expect(wrapper.find('[role="dialog"]').exists()).toBe(false))
    })
  })
})
