import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'
import UserToolbar from '../UserToolbar.vue'
import ApiKeyModal from '../ApiKeyModal.vue'

const route = reactive({ name: 'home' as string })
const router = { replace: vi.fn() }

vi.mock('vue-router', () => ({ useRoute: () => route, useRouter: () => router }))
vi.mock('primevue/usetoast', () => ({ useToast: () => ({ add: vi.fn() }) }))

function mountToolbar() {
  return mount(UserToolbar, {
    global: {
      stubs: {
        UserInvitations: true,
        UserSettings: true,
        UserChangePassword: true,
        ApiKeyModal: true,
        DButton: true,
        DAvatar: true,
        DDialog: true,
        DMenu: true,
      },
    },
  })
}

describe('UserToolbar API key deep link', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    route.name = 'home'
    router.replace.mockClear()
  })

  it('keeps the API key modal closed on other pages', () => {
    const wrapper = mountToolbar()

    expect(wrapper.findComponent(ApiKeyModal).props('show')).toBe(false)
  })

  it('opens the API key modal when navigating to the api-key route', async () => {
    const wrapper = mountToolbar()

    route.name = 'api-key'
    await flushPromises()

    expect(wrapper.findComponent(ApiKeyModal).props('show')).toBe(true)
  })

  it('opens the modal when the page loads on the api-key route', () => {
    route.name = 'api-key'
    const wrapper = mountToolbar()

    expect(wrapper.findComponent(ApiKeyModal).props('show')).toBe(true)
  })

  it('goes home when the modal opened from the link is closed', async () => {
    route.name = 'api-key'
    const wrapper = mountToolbar()

    wrapper.findComponent(ApiKeyModal).vm.$emit('update:show', false)
    await flushPromises()

    expect(router.replace).toHaveBeenCalledWith({ name: 'home' })
  })
})
