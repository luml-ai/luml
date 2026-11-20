import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import App from './App.vue'

describe('App', () => {
  it('mounts the dashboard root', () => {
    const wrapper = mount(App, {
      global: { plugins: [createPinia(), PrimeVue], stubs: { MTabs: true } },
    })
    expect(wrapper.find('[data-testid="monitoring-app"]').exists()).toBe(true)
  })
})
