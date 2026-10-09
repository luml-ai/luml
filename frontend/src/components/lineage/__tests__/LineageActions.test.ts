import { shallowMount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import LineageActions from '../LineageActions.vue'

const store = vi.hoisted(() => ({
  hasNodes: true,
  isLoading: false,
  resetPositions: vi.fn(),
}))

vi.mock('@/stores/lineage', () => ({ useLineageStore: () => store }))

const ButtonStub = defineComponent({
  name: 'Button',
  props: { disabled: Boolean },
  emits: ['click'],
  template:
    '<button :disabled="disabled" @click="$emit(\'click\')"><slot /><slot name="icon" /></button>',
})

function mountActions() {
  return shallowMount(LineageActions, {
    global: { stubs: { Button: ButtonStub } },
  })
}

describe('LineageActions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    store.hasNodes = true
    store.isLoading = false
  })

  it('allows resetting a loaded graph even when there are no edits', async () => {
    const wrapper = mountActions()
    const reset = wrapper
      .findAll('button')
      .find((button) => button.text().includes('Reset positions'))

    expect(reset?.attributes('disabled')).toBeUndefined()
    await reset?.trigger('click')
    expect(store.resetPositions).toHaveBeenCalledOnce()
  })

  it('disables resetting while the graph is loading or empty', () => {
    store.isLoading = true
    const loading = mountActions()
      .findAll('button')
      .find((button) => button.text().includes('Reset positions'))
    expect(loading?.attributes('disabled')).toBeDefined()

    store.isLoading = false
    store.hasNodes = false
    const empty = mountActions()
      .findAll('button')
      .find((button) => button.text().includes('Reset positions'))
    expect(empty?.attributes('disabled')).toBeDefined()
  })

  it('offers no depth selector: the whole graph is always shown', () => {
    const wrapper = mountActions()

    expect(wrapper.text()).not.toContain('Depth')
    expect(wrapper.find('select').exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'Select' }).exists()).toBe(false)
  })
})
