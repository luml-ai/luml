import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PrimeVue from 'primevue/config'
import Message from 'primevue/message'
import AuthorizationWrapper from '../AuthorizationWrapper.vue'

const mocks = vi.hoisted(() => ({
  loginWithGoogle: vi.fn(),
  loginWithMicrosoft: vi.fn(),
  loadUser: vi.fn(),
  push: vi.fn(),
}))

vi.mock('@/stores/auth', () => ({ useAuthStore: () => mocks }))
vi.mock('@/stores/user', () => ({ useUserStore: () => mocks }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ push: mocks.push }),
}))

function renderCallback(query: string, hideSso = true) {
  window.history.replaceState({}, '', `/sign-in?${query}`)
  return mount(AuthorizationWrapper, {
    props: { title: 'Sign in', image: 'image.svg', hideSso },
    global: {
      plugins: [PrimeVue],
      components: { DMessage: Message },
      stubs: { 'd-button': true },
    },
  })
}

describe('OAuth callback', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    sessionStorage.clear()
  })

  afterEach(() => {
    window.history.replaceState({}, '', '/')
    vi.restoreAllMocks()
  })

  it.each(['google', 'microsoft'])('forwards the full %s state', async (provider) => {
    const state = `${provider}.signed.state.token`
    const wrapper = renderCallback(new URLSearchParams({ code: 'code', state }).toString())
    await flushPromises()

    const login = provider === 'google' ? mocks.loginWithGoogle : mocks.loginWithMicrosoft
    const other = provider === 'google' ? mocks.loginWithMicrosoft : mocks.loginWithGoogle
    expect(login).toHaveBeenCalledExactlyOnceWith('code', state)
    expect(other).not.toHaveBeenCalled()
    expect(mocks.loadUser).toHaveBeenCalledOnce()
    expect(mocks.push).toHaveBeenCalledWith({ name: 'home' })
    wrapper.unmount()
  })

  it.each(['code=code', 'code=code&state=unknown.token', 'state=google.token'])(
    'ignores an incomplete or unknown callback: %s',
    async (query) => {
      const wrapper = renderCallback(query)
      await flushPromises()

      expect(mocks.loginWithGoogle).not.toHaveBeenCalled()
      expect(mocks.loginWithMicrosoft).not.toHaveBeenCalled()
      expect(mocks.loadUser).not.toHaveBeenCalled()
      expect(mocks.push).not.toHaveBeenCalled()
      wrapper.unmount()
    },
  )

  it.each(['google', 'microsoft'])(
    'shows a failed %s exchange without navigating',
    async (provider) => {
      const login = provider === 'google' ? mocks.loginWithGoogle : mocks.loginWithMicrosoft
      login.mockRejectedValueOnce(new Error('invalid_grant'))
      vi.spyOn(console, 'error').mockImplementation(() => {})
      const wrapper = renderCallback(`code=code&state=${provider}`, false)
      await flushPromises()

      expect(login).toHaveBeenCalledExactlyOnceWith('code', provider)
      expect(wrapper.getComponent(Message).text()).toBe('invalid_grant')
      expect(mocks.loadUser).not.toHaveBeenCalled()
      expect(mocks.push).not.toHaveBeenCalled()
      wrapper.unmount()
    },
  )

  it.each([
    {
      error: { response: { data: { detail: 'Sign in failed' } } },
      message: 'Sign in failed',
    },
    { error: undefined, message: 'Unable to sign in. Please try again.' },
  ])('shows an exchange error with a usable message: $message', async ({ error, message }) => {
    mocks.loginWithGoogle.mockRejectedValueOnce(error)
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const wrapper = renderCallback('code=code&state=google.signed.state', false)
    await flushPromises()

    expect(wrapper.getComponent(Message).text()).toBe(message)
    expect(mocks.loadUser).not.toHaveBeenCalled()
    expect(mocks.push).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('shows an error when loading the user after an exchange fails', async () => {
    mocks.loadUser.mockRejectedValueOnce(new Error('Unable to load user'))
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const wrapper = renderCallback('code=code&state=google.signed.state', false)
    await flushPromises()

    expect(mocks.loginWithGoogle).toHaveBeenCalledOnce()
    expect(wrapper.getComponent(Message).text()).toBe('Unable to load user')
    expect(mocks.push).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
