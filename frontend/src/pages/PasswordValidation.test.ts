import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import PrimeVue from 'primevue/config'
import { Form } from '@primevue/forms'
import Button from 'primevue/button'
import FloatLabel from 'primevue/floatlabel'
import IconField from 'primevue/iconfield'
import InputIcon from 'primevue/inputicon'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Password from 'primevue/password'
import SignInPage from './SignInPage.vue'
import SignUpPage from './SignUpPage.vue'
import ChangePasswordPage from './ChangePasswordPage.vue'
import UserChangePassword from '@/components/user/UserChangePassword.vue'

const { signIn, signUp, resetPassword, changePassword } = vi.hoisted(() => ({
  signIn: vi.fn(),
  signUp: vi.fn(),
  resetPassword: vi.fn(),
  changePassword: vi.fn(),
}))

vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ signIn, signUp }) }))
vi.mock('@/stores/user', () => ({
  useUserStore: () => ({ resetPassword, changePassword }),
}))
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({ query: {} }),
}))
vi.mock('primevue', () => ({ useToast: () => ({ add: vi.fn() }) }))

describe.each([
  {
    name: 'sign in',
    page: SignInPage,
    fields: ['password'],
    otherValues: { email: 'user@example.com' },
    request: signIn,
    payload: (password: string) => [{ email: 'user@example.com', password }],
  },
  {
    name: 'sign up',
    page: SignUpPage,
    fields: ['password'],
    otherValues: { username: 'Test User', email: 'user@example.com' },
    request: signUp,
    payload: (password: string) => [
      { full_name: 'Test User', email: 'user@example.com', password },
    ],
  },
  {
    name: 'reset password',
    page: ChangePasswordPage,
    fields: ['password', 'password_confirm'],
    otherValues: {},
    request: resetPassword,
    payload: (password: string) => ['test-reset-link', password],
  },
  {
    name: 'change password',
    page: UserChangePassword,
    fields: ['current_password', 'new_password', 'confirmPassword'],
    otherValues: {},
    request: changePassword,
    payload: (password: string) => [{ current_password: password, new_password: password }],
  },
])('$name password length', ({ page, fields, otherValues, request, payload }) => {
  let wrapper: ReturnType<typeof mount> | undefined

  afterEach(() => {
    wrapper?.unmount()
    window.history.replaceState({}, '', '/')
    sessionStorage.clear()
  })

  it.each([128, 129])('validates length %i before sending a request', async (length) => {
    window.history.replaceState({}, '', '/change-password?token=test-reset-link')
    wrapper = mount(page, {
      global: {
        plugins: [PrimeVue],
        components: {
          DForm: Form,
          DButton: Button,
          DFloatLabel: FloatLabel,
          DIconField: IconField,
          DInputIcon: InputIcon,
          DInputText: InputText,
          DMessage: Message,
          DPassword: Password,
        },
        stubs: {
          AuthorizationWrapper: {
            template: '<div><slot name="form" /><slot name="footer" /></div>',
          },
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })
    for (const [field, value] of Object.entries(otherValues)) {
      await wrapper.get(`input[name="${field}"]`).setValue(value)
    }
    const password = 'a'.repeat(length)
    for (const field of fields) {
      await wrapper.get(`input[name="${field}"]`).setValue(password)
    }

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    if (length === 129) {
      expect(wrapper.findAllComponents(Message).map((message) => message.text())).toEqual(
        fields.map(() => 'Password must be between 8 and 128 characters'),
      )
      expect(request).not.toHaveBeenCalled()
    } else {
      expect(wrapper.findAllComponents(Message)).toHaveLength(0)
      expect(request).toHaveBeenCalledExactlyOnceWith(...payload(password))
    }
  })
})
