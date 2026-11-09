import { enableAutoUnmount, flushPromises, mount, shallowMount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import UiCopyButton from './UiCopyButton.vue'
import UiMultiTypeText from './multi-type-text/UiMultiTypeText.vue'
import DeploymentErrorModal from '../deployments/error/DeploymentErrorModal.vue'
import UploadData from './UploadData.vue'
import UICustomToast from './UICustomToast.vue'

const mocks = vi.hoisted(() => ({ toast: vi.fn(), push: vi.fn() }))
vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: mocks.toast }),
}))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: mocks.push }) }))

enableAutoUnmount(afterEach)
const copiedIcon = '.lucide-copy-check-icon, .lucide-check-icon'
const button = {
  template:
    '<button @click="$emit(\'click\', $event)"><slot /><slot name="icon" />{{ label }}</button>',
  props: ['label'],
  emits: ['click'],
}
const global = {
  stubs: {
    Button: button,
    'd-button': button,
    Dialog: { template: '<div><slot /><slot name="footer" /></div>' },
    Select: true,
    FileInput: true,
  },
  directives: { tooltip: () => {} },
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.push.mockResolvedValue(undefined)
})
afterEach(() => vi.unstubAllGlobals())

describe('clipboard feedback', () => {
  it.each([
    ['copy button', UiCopyButton, { text: 'text' }],
    ['multi type text', UiMultiTypeText, { text: { value: 'text' }, title: 'Result' }],
    [
      'deployment error',
      DeploymentErrorModal,
      { error: 'Failure', reason: 'Error', visible: true },
    ],
  ] as const)(
    'reports rejected writes in %s without showing copied feedback',
    async (_, component, props) => {
      vi.stubGlobal('navigator', {
        clipboard: {
          writeText: vi.fn().mockRejectedValue(new DOMException('Denied', 'NotAllowedError')),
        },
      })
      const wrapper = mount(component as typeof UiCopyButton, {
        props: props as { text: string },
        global,
      })
      await wrapper.get('button').trigger('click')
      await flushPromises()
      expect(wrapper.find(copiedIcon).exists()).toBe(false)
      expect(mocks.toast).toHaveBeenCalledWith(
        expect.objectContaining({ severity: 'error', detail: 'Failed to copy to clipboard' }),
      )
    },
  )

  it('shows copied feedback only after the clipboard write succeeds', async () => {
    let finish!: () => void
    vi.stubGlobal('navigator', {
      clipboard: {
        writeText: vi.fn().mockReturnValue(
          new Promise<void>((resolve) => {
            finish = resolve
          }),
        ),
      },
    })
    const wrapper = mount(UiCopyButton, { props: { text: 'text' }, global })
    await wrapper.get('button').trigger('click')
    expect(wrapper.find(copiedIcon).exists()).toBe(false)
    finish()
    await flushPromises()
    expect(wrapper.find(copiedIcon).exists()).toBe(true)
  })
})

describe('sample dataset loading', () => {
  const props = {
    isTableExist: false,
    errors: { size: false, columns: false, rows: false },
    file: {},
    minColumnsCount: 2,
    minRowsCount: 2,
    resources: [],
    sampleFileName: 'sample.csv',
  }
  it.each([404, 403, 500])('does not emit a %s response body as CSV', async (status) => {
    const text = vi.fn().mockResolvedValue('<html>Error</html>')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status, text }))
    const wrapper = mount(UploadData, { props, global })
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(wrapper.emitted('selectFile')).toBeUndefined()
    expect(text).not.toHaveBeenCalled()
    expect(mocks.toast).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'error', detail: 'Failed to load sample dataset' }),
    )
  })
  it('emits a successfully fetched CSV', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, text: async () => 'a,b\n1,2' }))
    const wrapper = mount(UploadData, { props, global })
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(wrapper.emitted('selectFile')?.[0]?.[0]).toMatchObject({
      name: 'sample.csv',
      type: 'text/csv',
    })
    expect(mocks.toast).not.toHaveBeenCalled()
  })
  it('reports network failures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Network failed')))
    const wrapper = mount(UploadData, { props, global })
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(wrapper.emitted('selectFile')).toBeUndefined()
    expect(mocks.toast).toHaveBeenCalledWith(expect.objectContaining({ severity: 'error' }))
  })
})

describe('toast action routes', () => {
  function mountToast(params: string) {
    return shallowMount(UICustomToast, {
      global: {
        stubs: {
          Toast: {
            template: '<div><slot name="message" :message="message" /></div>',
            data: () => ({
              message: {
                severity: 'info',
                detail: `<a class="toast-action-link" data-route="orbits" data-params='${params}'>Open</a>`,
              },
            }),
          },
        },
      },
    })
  }
  it.each(['{organizationId: org1}', 'null', '[]', '42'])(
    'ignores malformed route parameters %s',
    async (params) => {
      const wrapper = mountToast(params)
      await wrapper.get('a').trigger('click')
      expect(mocks.push).not.toHaveBeenCalled()
    },
  )
  it('navigates with valid JSON route parameters', async () => {
    const wrapper = mountToast('{"organizationId":"org1"}')
    await wrapper.get('a').trigger('click')
    expect(mocks.push).toHaveBeenCalledWith({ name: 'orbits', params: { organizationId: 'org1' } })
  })
})
