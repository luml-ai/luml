import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
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

function renderCallback(query: string) {
  window.history.replaceState({}, '', `/sign-in?${query}`)
  return mount(AuthorizationWrapper, {
    props: { title: 'Sign in', image: 'image.svg', hideSso: true },
    global: { stubs: { 'd-button': true, 'd-message': true } },
  })
}

describe('OAuth callback', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    sessionStorage.clear()
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
})
