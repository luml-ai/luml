import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PrimeVue from 'primevue/config'
import { Form } from '@primevue/forms'
import Button from 'primevue/button'
import FloatLabel from 'primevue/floatlabel'
import Message from 'primevue/message'
import Password from 'primevue/password'
import ChangePasswordPage from './ChangePasswordPage.vue'
import { passwordResetSuccessToast } from '@/lib/primevue/data/toasts'

const { resetPassword, addToast, push } = vi.hoisted(() => ({
  resetPassword: vi.fn(),
  addToast: vi.fn(),
  push: vi.fn(),
}))

vi.mock('@/stores/user', () => ({
  useUserStore: () => ({ resetPassword }),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
}))

vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: addToast }),
}))

function mountPage() {
  return mount(ChangePasswordPage, {
    global: {
      plugins: [PrimeVue],
      components: {
        DForm: Form,
        DButton: Button,
        DFloatLabel: FloatLabel,
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

describe('ChangePasswordPage', () => {
  let wrapper: ReturnType<typeof mountPage> | undefined

  beforeEach(() => {
    resetPassword.mockReset().mockResolvedValue(undefined)
    addToast.mockReset()
    push.mockReset()
  })

  afterEach(() => {
    wrapper?.unmount()
    window.history.replaceState({}, '', '/')
    vi.restoreAllMocks()
  })

  it.each(['/change-password', '/change-password?token='])(
    'shows a missing reset link error at %s and does not reset the password',
    async (url) => {
      window.history.replaceState({}, '', url)
      wrapper = mountPage()

      expect(wrapper.text()).toContain('Invalid or missing reset link')

      await wrapper.get('input[name="password"]').setValue('new-password')
      await wrapper.get('input[name="password_confirm"]').setValue('new-password')
      await wrapper.get('form').trigger('submit')
      await flushPromises()

      expect(wrapper.text()).toContain('Invalid or missing reset link')
      expect(resetPassword).not.toHaveBeenCalled()
      expect(addToast).not.toHaveBeenCalled()
      expect(push).not.toHaveBeenCalled()
    },
  )

  it('resets the password and returns to sign in with a token and matching passwords', async () => {
    window.history.replaceState({}, '', '/change-password?token=test-reset-link')
    wrapper = mountPage()

    expect(wrapper.text()).not.toContain('Invalid or missing reset link')

    await wrapper.get('input[name="password"]').setValue('new-password')
    await wrapper.get('input[name="password_confirm"]').setValue('new-password')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(resetPassword).toHaveBeenCalledExactlyOnceWith('test-reset-link', 'new-password')
    expect(addToast).toHaveBeenCalledExactlyOnceWith(passwordResetSuccessToast)
    expect(push).toHaveBeenCalledExactlyOnceWith({ name: 'sign-in' })
  })

  it('does not reset the password when the passwords do not match', async () => {
    window.history.replaceState({}, '', '/change-password?token=test-reset-link')
    wrapper = mountPage()

    await wrapper.get('input[name="password"]').setValue('new-password')
    await wrapper.get('input[name="password_confirm"]').setValue('different-password')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('Passwords must match')
    expect(resetPassword).not.toHaveBeenCalled()
    expect(addToast).not.toHaveBeenCalled()
    expect(push).not.toHaveBeenCalled()
  })

  it('does not report success or navigate when the reset request fails', async () => {
    window.history.replaceState({}, '', '/change-password?token=test-reset-link')
    resetPassword.mockRejectedValueOnce(new Error('Reset failed'))
    vi.spyOn(console, 'error').mockImplementation(() => {})
    wrapper = mountPage()

    await wrapper.get('input[name="password"]').setValue('new-password')
    await wrapper.get('input[name="password_confirm"]').setValue('new-password')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(resetPassword).toHaveBeenCalledExactlyOnceWith('test-reset-link', 'new-password')
    expect(addToast).not.toHaveBeenCalled()
    expect(push).not.toHaveBeenCalled()
  })
})
