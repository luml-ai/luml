import { flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import CollectionCreator from './CollectionCreator.vue'

const mocks = vi.hoisted(() => ({
  collectionsList: [{ tags: null }, { tags: ['production'] }],
  createCollection: vi.fn(),
  toastAdd: vi.fn(),
}))

vi.mock('@/stores/collections', () => ({
  useCollectionsStore: () => mocks,
}))

vi.mock('primevue', async (importOriginal) => ({
  ...((await importOriginal()) as Record<string, unknown>),
  useToast: () => ({ add: mocks.toastAdd }),
}))

describe('CollectionCreator tags', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it.each([
    { query: 'prod', suggestions: ['prod', 'production'] },
    { query: 'new-tag', suggestions: ['new-tag'] },
  ])(
    'suggests tags for "$query" when another collection has null tags',
    async ({ query, suggestions }) => {
      const wrapper = mount(CollectionCreator, {
        props: { visible: true },
        global: {
          plugins: [PrimeVue],
          stubs: { Dialog: { template: '<div><slot /></div>' }, Select: true },
        },
      })

      try {
        await wrapper.get('input[placeholder="Type to add tags"]').setValue(query)
        await vi.advanceTimersByTimeAsync(300)
        await flushPromises()

        const options = document.querySelectorAll('.p-autocomplete-overlay [role="option"]')
        expect(Array.from(options, (option) => option.textContent?.trim())).toEqual(suggestions)
      } finally {
        wrapper.unmount()
      }
    },
  )
})
