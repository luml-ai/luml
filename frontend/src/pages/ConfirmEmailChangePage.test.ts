import { flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PrimeVue from 'primevue/config'
import Button from 'primevue/button'
import Message from 'primevue/message'
import ConfirmEmailChangePage from './ConfirmEmailChangePage.vue'

const { confirmEmailChange, clearSession } = vi.hoisted(() => ({
  confirmEmailChange: vi.fn(),
  clearSession: vi.fn(),
}))
vi.mock('@/lib/api', () => ({ api: { confirmEmailChange } }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ clearSession }) }))

const token = `header.${btoa(JSON.stringify({ type: 'email_change', new_email: 'new@example.com' }))}.signature`
function mountPage() {
  return mount(ConfirmEmailChangePage, {
    global: {
      plugins: [PrimeVue],
      components: { DButton: Button, DMessage: Message },
      stubs: {
        AuthorizationWrapper: { template: '<div><slot name="form" /><slot name="footer" /></div>' },
        RouterLink: RouterLinkStub,
      },
    },
  })
}

describe('email change confirmation', () => {
  let wrapper: ReturnType<typeof mountPage> | undefined
  beforeEach(() => {
    confirmEmailChange.mockReset().mockResolvedValue(undefined)
    clearSession.mockReset()
    window.history.replaceState({}, '', `/confirm-email-change?token=${encodeURIComponent(token)}`)
  })
  afterEach(() => {
    wrapper?.unmount()
    window.history.replaceState({}, '', '/')
  })

  it('shows the address without consuming the token on page load', async () => {
    wrapper = mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('new@example.com')
    expect(confirmEmailChange).not.toHaveBeenCalled()
    expect(clearSession).not.toHaveBeenCalled()
  })

  it('confirms only on click and clears the session before linking to sign-in', async () => {
    wrapper = mountPage()
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(confirmEmailChange).toHaveBeenCalledExactlyOnceWith(token)
    expect(clearSession).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('Email changed successfully. Sign in with your new address.')
    expect(wrapper.find('button').exists()).toBe(false)
    expect(wrapper.getComponent(RouterLinkStub).props('to')).toEqual({ name: 'sign-in' })
  })

  it.each(['', 'bad', 'a.e30.c'])('rejects malformed or missing links: %s', async (invalid) => {
    window.history.replaceState({}, '', `/confirm-email-change?token=${invalid}`)
    wrapper = mountPage()
    expect(wrapper.text()).toContain('Email change link is expired, already used or invalid')
    expect(wrapper.find('button').exists()).toBe(false)
    expect(confirmEmailChange).not.toHaveBeenCalled()
  })

  it.each(['Email change link is expired, already used or invalid', 'Address already in use'])(
    'shows confirmation failure: %s',
    async (detail) => {
      confirmEmailChange.mockRejectedValueOnce({ response: { data: { detail } } })
      wrapper = mountPage()
      await wrapper.get('button').trigger('click')
      await flushPromises()
      expect(wrapper.text()).toContain(detail)
      expect(clearSession).not.toHaveBeenCalled()
    },
  )
})
