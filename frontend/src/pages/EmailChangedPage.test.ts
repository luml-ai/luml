import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PrimeVue from 'primevue/config'
import Button from 'primevue/button'
import EmailChangedPage from './EmailChangedPage.vue'

const { route, push, clearSession } = vi.hoisted(() => ({
  route: { query: {} as Record<string, string> },
  push: vi.fn(),
  clearSession: vi.fn(),
}))
vi.mock('vue-router', () => ({ useRoute: () => route, useRouter: () => ({ push }) }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ clearSession }) }))

function mountPage(status?: string) {
  route.query = status ? { status } : {}
  return mount(EmailChangedPage, {
    global: {
      plugins: [PrimeVue],
      components: { DButton: Button },
      stubs: {
        AuthorizationWrapper: {
          props: ['title', 'subTitle'],
          template: '<div><h1>{{ title }}</h1><p>{{ subTitle }}</p><slot name="form" /></div>',
        },
      },
    },
  })
}

describe('email change result page', () => {
  beforeEach(() => {
    push.mockReset()
    clearSession.mockReset()
  })

  it('reports the change, ends the local session and leads to sign-in', async () => {
    const wrapper = mountPage('changed')
    expect(wrapper.text()).toContain('Email changed')
    expect(wrapper.text()).toContain('Sign in with your new address')
    expect(clearSession).toHaveBeenCalledOnce()
    await wrapper.get('button').trigger('click')
    expect(push).toHaveBeenCalledWith({ name: 'sign-in' })
  })

  it.each([
    ['in-use', 'already used by another account'],
    ['invalid', 'expired or is no longer valid'],
    [undefined, 'expired or is no longer valid'],
    ['anything', 'expired or is no longer valid'],
  ])('explains a failed change for status %s and keeps the session', (status, text) => {
    const wrapper = mountPage(status)
    expect(wrapper.text()).toContain('Email not changed')
    expect(wrapper.text()).toContain(text)
    expect(clearSession).not.toHaveBeenCalled()
  })
})
