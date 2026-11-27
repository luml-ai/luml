import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import PrimeVue from 'primevue/config'
import { Form } from '@primevue/forms'
import Button from 'primevue/button'
import FloatLabel from 'primevue/floatlabel'
import Message from 'primevue/message'
import Password from 'primevue/password'
import UserChangePassword from './UserChangePassword.vue'

vi.mock('@/stores/user', () => ({ useUserStore: () => ({ changePassword: vi.fn() }) }))

describe('change password dialog', () => {
  it('names each password input through its label', () => {
    const wrapper = mount(UserChangePassword, {
      global: {
        plugins: [PrimeVue],
        components: {
          DForm: Form,
          DButton: Button,
          DFloatLabel: FloatLabel,
          DMessage: Message,
          DPassword: Password,
        },
      },
    })
    for (const [id, autocomplete] of [
      ['oldPassword', 'current-password'],
      ['newPassword', 'new-password'],
      ['confirmPassword', 'new-password'],
    ]) {
      const input = wrapper.get(`input#${id}`)
      expect(wrapper.get(`label[for="${id}"]`).text()).not.toBe('')
      expect(input.attributes('autocomplete')).toBe(autocomplete)
    }
    wrapper.unmount()
  })
})
