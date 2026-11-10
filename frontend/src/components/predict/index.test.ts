import { flushPromises, mount } from '@vue/test-utils'
import { ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import Predict from './index.vue'

const { startPredict, addToast, downloadFileFromBlob } = vi.hoisted(() => ({
  startPredict: vi.fn(),
  addToast: vi.fn(),
  downloadFileFromBlob: vi.fn(),
}))
const fileData = ref({ name: 'inputs.csv' })

vi.mock('@/lib/data-processing/DataProcessingWorker', () => ({
  DataProcessingWorker: { startPredict, deallocateModels: vi.fn().mockResolvedValue(undefined) },
}))
vi.mock('primevue/usetoast', () => ({ useToast: () => ({ add: addToast }) }))
vi.mock('@/lib/analytics/AnalyticsService', () => ({
  AnalyticsService: { track: vi.fn() },
  AnalyticsTrackKeysEnum: { predict: 'predict' },
}))
vi.mock('@/hooks/useDataTable', () => ({
  useDataTable: () => ({
    fileData,
    isUploadWithErrors: ref(false),
    getDataForTraining: () => ({ text: ['first', 'bad', 'last'] }),
    onSelectFile: vi.fn(),
    onRemoveFile: vi.fn(),
  }),
}))
vi.mock('@/helpers/helpers', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/helpers/helpers')>()),
  downloadFileFromBlob,
}))

function mountPredict() {
  return mount(Predict, {
    props: { task: 'prompt_optimization', modelId: 'model', manualFields: ['text'] },
    global: {
      stubs: {
        SelectButton: {
          template: `<button @click="$emit('update:modelValue', 'Upload file')">Upload file</button>`,
        },
        FileInput: {
          props: ['successMessageOnly', 'error'],
          template:
            '<div>{{ successMessageOnly }}<span v-if="error">Prediction failed</span></div>',
        },
        DButton: {
          props: ['label'],
          template: '<button :aria-label="label">{{ label }}</button>',
        },
        DFloatLabel: { template: '<div><slot /></div>' },
        DInputText: {
          props: ['modelValue'],
          template: `<input :value="modelValue" @input="$emit('update:modelValue', $event.target.value)" />`,
        },
        Textarea: { props: ['modelValue'], template: '<textarea :value="modelValue" />' },
      },
    },
  })
}

async function readBlob(blob: Blob): Promise<string> {
  return new Promise((resolve) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.readAsText(blob)
  })
}

describe('Predict', () => {
  let wrapper: ReturnType<typeof mountPredict>

  beforeEach(() => {
    startPredict.mockReset()
    fileData.value = { name: 'inputs.csv' }
    wrapper = mountPredict()
  })

  afterEach(() => wrapper.unmount())

  async function predictFile() {
    await wrapper.get('button').trigger('click')
    await wrapper.get('[aria-label="Predict"]').trigger('click')
    await flushPromises()
  }

  it('downloads aligned partial results with row errors and shows the failed count', async () => {
    startPredict.mockResolvedValue({
      predictions: [{ result: 'first' }, null, { result: 'last' }],
      prediction_errors: [null, 'Invalid structured response', null],
    })

    await predictFile()

    expect(wrapper.text()).toContain('1 of 3 rows failed')
    expect(addToast).not.toHaveBeenCalled()
    await wrapper.get('[aria-label="Download"]').trigger('click')
    const csv = await readBlob(downloadFileFromBlob.mock.calls[0][0])
    expect(csv).toBe(
      'text,prediction,prediction_error\n' +
        'first,"{""result"":""first""}",\n' +
        'bad,,Invalid structured response\n' +
        'last,"{""result"":""last""}",',
    )

    fileData.value = { name: 'replacement.csv' }
    await flushPromises()
    expect(wrapper.text()).not.toContain('rows failed')
    expect(wrapper.text()).not.toContain('Download')
  })

  it('keeps successful CSV downloads without an error column', async () => {
    startPredict.mockResolvedValue({ predictions: ['first', 'second', 'last'] })

    await predictFile()

    expect(wrapper.text()).not.toContain('rows failed')
    await wrapper.get('[aria-label="Download"]').trigger('click')
    expect(await readBlob(downloadFileFromBlob.mock.calls[0][0])).toBe(
      'text,prediction\nfirst,first\nbad,second\nlast,last',
    )
  })

  it.each(['Invalid structured response', 'Unauthorized', 'Timed out'])(
    'shows a batch error without a download for %s',
    async (message) => {
      startPredict.mockRejectedValue(new Error(message))

      await predictFile()

      expect(addToast).toHaveBeenCalledWith(expect.objectContaining({ detail: message }))
      expect(wrapper.text()).toContain('Prediction failed')
      expect(wrapper.text()).not.toContain('Download')
    },
  )

  it('keeps displaying an error for a failed manual prediction', async () => {
    startPredict.mockRejectedValue(new Error('Invalid structured response'))

    await wrapper.get('input').setValue('bad')
    await wrapper.get('[aria-label="Predict"]').trigger('click')
    await flushPromises()

    expect(addToast).toHaveBeenCalledWith(
      expect.objectContaining({ detail: 'Invalid structured response' }),
    )
    expect(wrapper.get('textarea').element.value).toBe('')
  })
})
