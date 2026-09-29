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

  return wrapper.getComponent(apiReferenceStub).props('configuration') as Record<string, unknown>
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
