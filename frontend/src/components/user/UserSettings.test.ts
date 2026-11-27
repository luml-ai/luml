import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, defineStore } from 'pinia'
import { computed } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import PrimeVue from 'primevue/config'
import { Form } from '@primevue/forms'
import Button from 'primevue/button'
import FloatLabel from 'primevue/floatlabel'
import IconField from 'primevue/iconfield'
import InputIcon from 'primevue/inputicon'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import UserSettings from './UserSettings.vue'

const state = vi.hoisted(() => ({ sso: false, updateUser: vi.fn() }))
vi.mock('@/stores/user', () => ({ useUserStore: () => useTestUser() }))
vi.mock('primevue/usetoast', () => ({ useToast: () => ({ add: vi.fn() }) }))
vi.mock('@/hooks/useInputIcon', () => ({
  useInputIcon: () => ({ getCurrentInputIcon: () => null, onIconClick: vi.fn() }),
}))
const useTestUser = defineStore('settings-test', () => ({
  getUserFullName: computed(() => 'Original Name'),
  getUserEmail: computed(() => 'old@example.com'),
  getUserAvatar: computed(() => null),
  isUserLoggedWithSSO: computed(() => state.sso),
  isUserDisabled: computed(() => false),
  updateUser: state.updateUser,
}))
function mountSettings() {
  return mount(UserSettings, {
    global: {
      plugins: [createPinia(), PrimeVue],
      components: {
        DForm: Form,
        DButton: Button,
        DFloatLabel: FloatLabel,
        DIconField: IconField,
        DInputIcon: InputIcon,
        DInputText: InputText,
        DMessage: Message,
      },
      stubs: { DAvatar: true, DeleteAccountModal: true },
    },
  })
}

describe('profile email', () => {
  let wrapper: ReturnType<typeof mountSettings> | undefined
  afterEach(() => {
    wrapper?.unmount()
    state.updateUser.mockReset()
    state.sso = false
  })

  it.each([
    ['Change email', '#email', 'showChangeEmail'],
    ['Change password', '#password', 'showChangePassword'],
  ] as const)(
    'opens %s from the pencil in a read-only field without submitting the profile',
    async (label, field, event) => {
      wrapper = mountSettings()
      expect(wrapper.get(field).attributes('readonly')).toBeDefined()
      const change = wrapper.get(`button[aria-label="${label}"]`)
      expect(change.attributes('type')).toBe('button')
      await change.trigger('click')
      expect(wrapper.emitted(event)).toHaveLength(1)
      expect(state.updateUser).not.toHaveBeenCalled()
    },
  )

  it('shows the password masked, never as a password input', () => {
    wrapper = mountSettings()
    const password = wrapper.get<HTMLInputElement>('#password')
    expect(password.attributes('type')).not.toBe('password')
    expect(password.element.value).toBe('••••••••')
  })

  it('submits only the changed full name', async () => {
    state.updateUser.mockResolvedValueOnce({ detail: 'Updated' })
    wrapper = mountSettings()
    await wrapper.get('input[name="username"]').setValue('Updated Name')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(state.updateUser).toHaveBeenCalledExactlyOnceWith({ full_name: 'Updated Name' })
  })

  it('shows a provider hint with no change action for SSO accounts', () => {
    state.sso = true
    wrapper = mountSettings()
    expect(wrapper.text()).toContain('Email is managed by your sign-in provider.')
    expect(wrapper.find('button[aria-label="Change email"]').exists()).toBe(false)
    expect(wrapper.find('button[aria-label="Change password"]').exists()).toBe(false)
    expect(wrapper.find('#password').exists()).toBe(false)
    expect(wrapper.get('#email').attributes('readonly')).toBeDefined()
  })
})
