import { flushPromises, mount } from '@vue/test-utils'
import { fromCSV } from 'arquero'
import { afterEach, describe, expect, it, vi } from 'vitest'
import PredictFile from './PredictFile.vue'

const { toastAdd, getDataForTraining } = vi.hoisted(() => ({
  toastAdd: vi.fn(),
  getDataForTraining: vi.fn(),
}))

vi.mock('primevue', () => ({ useToast: () => ({ add: toastAdd }) }))
vi.mock('@/hooks/useDataTable', async () => {
  const { ref } = await import('vue')
  return {
    useDataTable: () => ({
      isUploadWithErrors: ref(false),
      fileData: ref({ name: 'inputs.csv', size: 12 }),
      onSelectFile: vi.fn(),
      getDataForTraining,
      onRemoveFile: vi.fn(),
    }),
  }
})

const mountPredictFile = (predictCallback: () => Promise<unknown>) =>
  mount(PredictFile, {
    props: { predictCallback },
    global: {
      stubs: {
        FileInput: true,
        DButton: {
          props: ['label', 'disabled'],
          template: '<button :disabled="disabled">{{ label }}</button>',
        },
      },
    },
  })

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('runtime tabular file predictions', () => {
  it.each([
    {
      name: 'a flat numeric array',
      result: [0.12, 0.87, 0.5],
      input: { feature: [1, 2, 3] },
      expected: [{ prediction: 0.12 }, { prediction: 0.87 }, { prediction: 0.5 }],
    },
    {
      name: 'a typed array',
      result: new Float32Array([0.125, 0.875]),
      input: { feature: [1, 2] },
      expected: [{ prediction: 0.125 }, { prediction: 0.875 }],
    },
    {
      name: 'string labels containing CSV delimiters',
      result: ['Yes, approved', 'He said "no"\nthen left'],
      input: { feature: [1, 2] },
      expected: [{ prediction: 'Yes, approved' }, { prediction: 'He said "no"\nthen left' }],
    },
    {
      name: 'a single zero prediction',
      result: [0],
      input: { feature: [1] },
      expected: [{ prediction: 0 }],
    },
    {
      name: 'an empty array',
      result: [],
      input: { feature: [] },
      expected: [],
    },
  ])('downloads one prediction per input row for $name', async ({ result, input, expected }) => {
    getDataForTraining.mockReturnValue(input)
    const predictCallback = vi.fn().mockResolvedValue(result)
    const createObjectURL = vi.fn<(blob: Blob) => string>(() => 'blob:predictions')
    const revokeObjectURL = vi.fn()
    vi.stubGlobal('URL', { createObjectURL, revokeObjectURL })
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const wrapper = mountPredictFile(predictCallback)

    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(predictCallback).toHaveBeenCalledWith(input)
    expect(wrapper.get('button').text()).toBe('Download')
    await wrapper.get('button').trigger('click')

    const blob = createObjectURL.mock.calls[0]?.[0] as Blob
    expect(blob).toBeInstanceOf(Blob)
    expect(blob.type).toBe('text/csv;charset=utf-8;')
    const csv = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(reader.result as string)
      reader.onerror = () => reject(reader.error)
      reader.readAsText(blob)
    })
    expect(csv.split('\n')[0]).toBe('prediction')
    if (expected.length) {
      const table = fromCSV(csv)
      expect(table.columnNames()).toEqual(['prediction'])
      expect(table.objects()).toEqual(expected)
    } else {
      expect(csv).toBe('prediction')
    }
    expect(toastAdd).not.toHaveBeenCalled()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:predictions')
    wrapper.unmount()
  })

  it('reports prediction failures without offering a download', async () => {
    getDataForTraining.mockReturnValue({ feature: [1] })
    const wrapper = mountPredictFile(vi.fn().mockRejectedValue('Prediction failed'))

    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(wrapper.get('button').text()).toBe('Predict')
    expect(toastAdd).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'error', detail: 'Prediction failed' }),
    )
    wrapper.unmount()
  })
})
