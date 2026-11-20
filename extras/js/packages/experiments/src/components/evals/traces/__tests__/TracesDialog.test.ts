import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Tooltip from 'primevue/tooltip'
import { defineComponent, h } from 'vue'
import { mockVirtualLayout } from '@/components/ui/__tests__/virtualLayout'
import UiMultiTypeText from '@/components/ui/UiMultiTypeText.vue'
import TracesDialog from '../TracesDialog.vue'

vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: vi.fn() }),
}))

enableAutoUnmount(afterEach)

const DialogStub = {
  name: 'Dialog',
  props: ['closeOnEscape'],
  template: '<div class="dialog-stub"><slot /></div>',
}

// Both panels of the evaluation show their values through UiMultiTypeText.
const LongValueStub = defineComponent({
  name: 'LongValue',
  setup: () => () => h(UiMultiTypeText, { title: 'value', text: 'x'.repeat(3_000) }),
})

beforeEach(() => {
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
  )
  mockVirtualLayout(670)
  setActivePinia(createPinia())
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('TracesDialog', () => {
  it.each(['TracesInputs', 'TracesModels'])(
    'keeps Escape from closing the evaluation while a value viewer of %s is open',
    async (panel) => {
      const wrapper = mount(TracesDialog, {
        props: { visible: true, modelsInfo: {} },
        global: {
          plugins: [[PrimeVue, { unstyled: true }]],
          directives: { tooltip: Tooltip },
          stubs: {
            Dialog: DialogStub,
            TracesInputs: true,
            TracesModels: true,
            EvalsTabs: true,
            [panel]: LongValueStub,
          },
        },
      })
      await flushPromises()
      const evalDialog = () => wrapper.findAllComponents(DialogStub)[0]!
      expect(evalDialog().props('closeOnEscape')).toBe(true)

      const showAll = wrapper.findAll('button').find((button) => button.text() === 'Show all')
      await showAll!.trigger('click')
      expect(evalDialog().props('closeOnEscape')).toBe(false)

      wrapper.findAllComponents(DialogStub)[1]!.vm.$emit('update:visible', false)
      await flushPromises()
      expect(evalDialog().props('closeOnEscape')).toBe(true)
    },
  )
})
