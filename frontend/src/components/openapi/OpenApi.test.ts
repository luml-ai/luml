import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import OpenApi from './OpenApi.vue'

vi.mock('@/stores/theme', () => ({
  useThemeStore: () => ({ getCurrentTheme: 'light' }),
}))

const apiReferenceStub = {
  name: 'ApiReference',
  props: ['configuration'],
  template: '<div data-testid="api-reference" />',
}

function configuration(serverUrl?: string) {
  const wrapper = mount(OpenApi, {
    props: { content: { openapi: '3.0.0' }, serverUrl },
    global: { stubs: { ApiReference: apiReferenceStub } },
  })

  const configuration = wrapper.getComponent(apiReferenceStub).props('configuration') as Record<
    string,
    unknown
  >
  wrapper.unmount()
  return configuration
}

describe('OpenApi', () => {
  it('configures the requested server URL', () => {
    expect(configuration('https://inference.example.com').servers).toEqual([
      { url: 'https://inference.example.com' },
    ])
  })

  it('uses an empty server list when no URL is available', () => {
    expect(configuration().servers).toEqual([])
  })
})

it('uses the satellite as the base URL', () => {
  expect(configuration('https://inference.example.com').baseServerURL).toBe(
    'https://inference.example.com',
  )
  expect(configuration().baseServerURL).toBeUndefined()
})

it('removes its body theme classes when unmounted, including pending timers', async () => {
  vi.useFakeTimers()
  const wrapper = mount(OpenApi, {
    props: { content: { openapi: '3.0.0' } },
    global: { stubs: { ApiReference: apiReferenceStub } },
  })
  vi.advanceTimersByTime(200)
  expect(document.body.classList.contains('light-mode')).toBe(true)
  wrapper.unmount()
  vi.runAllTimers()
  expect(document.body.classList.contains('light-mode')).toBe(false)
  expect(document.body.classList.contains('dark-mode')).toBe(false)
  const pending = mount(OpenApi, {
    props: { content: {} },
    global: { stubs: { ApiReference: apiReferenceStub } },
  })
  pending.unmount()
  vi.runAllTimers()
  expect(document.body.className).toBe('')
  vi.useRealTimers()
})
