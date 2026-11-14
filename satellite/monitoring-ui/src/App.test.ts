import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import App from './App.vue'

describe('App', () => {
  it('mounts the dashboard root', () => {
    const wrapper = mount(App)
    expect(wrapper.find('[data-testid="monitoring-app"]').exists()).toBe(true)
  })
})
