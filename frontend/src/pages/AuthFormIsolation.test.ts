import { mount } from '@vue/test-utils'
import type { Component } from 'vue'
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
import ForgotPasswordPage from './ForgotPasswordPage.vue'
import ChangePasswordPage from './ChangePasswordPage.vue'

vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({}) }))
vi.mock('@/stores/user', () => ({ useUserStore: () => ({}) }))
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({ query: {} }),
}))
vi.mock('primevue', () => ({ useToast: () => ({ add: vi.fn() }) }))
vi.mock('primevue/usetoast', () => ({ useToast: () => ({ add: vi.fn() }) }))

function mountPage(page: Component) {
  return mount(page, {
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
        AuthorizationWrapper: { template: '<div><slot name="form" /><slot name="footer" /></div>' },
        RouterLink: { template: '<a><slot /></a>' },
      },
    },
  })
}

describe('auth form isolation', () => {
  const wrappers: ReturnType<typeof mountPage>[] = []

  afterEach(() => {
    wrappers.splice(0).forEach((wrapper) => wrapper.unmount())
  })

  it.each([
    { name: 'sign in', page: SignInPage, fields: ['email', 'password'] },
    { name: 'sign up', page: SignUpPage, fields: ['username', 'email', 'password'] },
    { name: 'forgot password', page: ForgotPasswordPage, fields: ['email'] },
    { name: 'change password', page: ChangePasswordPage, fields: ['password', 'password_confirm'] },
  ])('keeps $name fields empty in concurrent mounts and on revisit', async ({ page, fields }) => {
    const first = mountPage(page)
    wrappers.push(first)
    for (const field of fields) {
      await first.get(`input[name="${field}"]`).setValue(`private-${field}`)
    }

    const second = mountPage(page)
    wrappers.push(second)
    expect(second.getComponent(Form).props('initialValues')).not.toBe(
      first.getComponent(Form).props('initialValues'),
    )
    for (const field of fields) {
      expect((second.get(`input[name="${field}"]`).element as HTMLInputElement).value).toBe('')
      expect((first.get(`input[name="${field}"]`).element as HTMLInputElement).value).toBe(
        `private-${field}`,
      )
    }

    wrappers.splice(0).forEach((wrapper) => wrapper.unmount())
    const revisited = mountPage(page)
    wrappers.push(revisited)
    for (const field of fields) {
      expect((revisited.get(`input[name="${field}"]`).element as HTMLInputElement).value).toBe('')
    }
  })
})
