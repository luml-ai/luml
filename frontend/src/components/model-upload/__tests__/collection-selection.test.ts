import { flushPromises, shallowMount } from '@vue/test-utils'
import { ref } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ModelUploadCollectionSelect from '../ModelUploadCollectionSelect.vue'

const hooks = vi.hoisted(() => ({
  setRequestInfo: vi.fn(),
  getInitialPage: vi.fn(),
  reset: vi.fn(),
  onLazyLoad: vi.fn(),
  setSearchQuery: vi.fn(),
}))
vi.mock('@/hooks/useCollectionsList', () => ({
  useCollectionsList: () => ({
    ...hooks,
    collectionsList: ref([{ id: 'c1', name: 'Collection' }]),
  }),
}))
vi.mock('primevue', async (original) => ({
  ...(await original<typeof import('primevue')>()),
  useToast: () => ({ add: vi.fn() }),
}))
afterEach(() => vi.useRealTimers())
describe('upload collection selection', () => {
  it('preserves the selection while loading and filtering the current orbit', async () => {
    vi.useFakeTimers()
    const wrapper = shallowMount(ModelUploadCollectionSelect, {
      props: { modelValue: 'c1', orbitId: 'orb', organizationId: 'org' },
    })
    expect(wrapper.get('label').attributes('for')).toBe('collection')
    expect(wrapper.getComponent({ name: 'Select' }).attributes('input-id')).toBe('collection')
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    wrapper.getComponent({ name: 'Select' }).vm.$emit('filter', { value: 'Co' })
    await vi.advanceTimersByTimeAsync(600)
    await flushPromises()
    expect(hooks.setSearchQuery).toHaveBeenLastCalledWith('Co')
    expect(hooks.getInitialPage).toHaveBeenCalledTimes(2)
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    await wrapper.setProps({ orbitId: 'another-orbit' })
    expect(wrapper.emitted('update:modelValue')).toEqual([[null]])
    expect(hooks.setSearchQuery).toHaveBeenLastCalledWith('')
    wrapper.unmount()
  })
})
