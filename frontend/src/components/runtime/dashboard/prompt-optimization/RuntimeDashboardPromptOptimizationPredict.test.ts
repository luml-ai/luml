import { flushPromises, shallowMount } from '@vue/test-utils'
import { fromCSV } from 'arquero'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { downloadFileFromBlob } from '@/helpers/helpers'
import RuntimeDashboardPromptOptimizationPredict from './RuntimeDashboardPromptOptimizationPredict.vue'

const { getDataForTraining, computePythonModel, addToast } = vi.hoisted(() => ({
  getDataForTraining: vi.fn(),
  computePythonModel: vi.fn(),
  addToast: vi.fn(),
}))

vi.mock('@/hooks/useDataTable', async () => {
  const { ref } = await import('vue')
  return {
    useDataTable: () => ({
      isUploadWithErrors: ref(false),
      fileData: ref({ name: 'inputs.csv', size: 100 }),
      onSelectFile: vi.fn(),
      onRemoveFile: vi.fn(),
      getDataForTraining,
    }),
  }
})

vi.mock('@/lib/data-processing/DataProcessingWorker', () => ({
  DataProcessingWorker: { computePythonModel },
}))

vi.mock('@/lib/analytics/AnalyticsService', () => ({
  AnalyticsService: { track: vi.fn() },
  AnalyticsTrackKeysEnum: { predict: 'predict' },
}))

vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  useToast: () => ({ add: addToast }),
}))

vi.mock('@/helpers/helpers', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/helpers/helpers')>()),
  downloadFileFromBlob: vi.fn(),
}))

async function mountPredict() {
  const wrapper = shallowMount(RuntimeDashboardPromptOptimizationPredict, {
    props: {
      manualFields: ['text', 'lang'],
      modelId: 'm1',
      dynamicAttributes: { temperature: 0.5 },
      providerConnected: true,
    },
    global: {
      stubs: {
        SelectButton: {
          emits: ['update:modelValue'],
          template:
            '<button data-testid="upload-mode" @click="$emit(\'update:modelValue\', \'Upload file\')">Upload file</button>',
        },
        Button: {
          props: ['label', 'disabled', 'loading'],
          template: '<button :disabled="disabled" :data-loading="loading">{{ label }}</button>',
        },
      },
    },
  })
  await wrapper.get('[data-testid="upload-mode"]').trigger('click')
  return wrapper
}

async function readDownload() {
  const blob = vi.mocked(downloadFileFromBlob).mock.calls[0][0]
  const csv = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = () => reject(reader.error)
    reader.readAsText(blob)
  })
  return fromCSV(csv).objects()
}

describe('RuntimeDashboardPromptOptimizationPredict CSV predictions', () => {
  beforeEach(() => {
    getDataForTraining.mockReset()
    computePythonModel.mockReset()
    getDataForTraining.mockReturnValue({
      text: ['row one', 'row two', 'row three'],
      lang: ['en', 'de', 'fr'],
    })
    computePythonModel.mockResolvedValue({ status: 'success', predictions: { out: 'prediction' } })
  })

  it('predicts every row and exports all input/prediction pairs in CSV order', async () => {
    computePythonModel
      .mockResolvedValueOnce({ status: 'success', predictions: { out: 'Yes, "approved"\nnext' } })
      .mockResolvedValueOnce({ status: 'success', predictions: { out: { text: 'second result' } } })
      .mockResolvedValueOnce({ status: 'success', predictions: { out: 'third result' } })
    const wrapper = await mountPredict()

    await wrapper.get('.upload button').trigger('click')
    await flushPromises()

    expect(computePythonModel).toHaveBeenCalledTimes(3)
    expect(computePythonModel.mock.calls).toEqual([
      [
        {
          inputs: { in: { text: 'row one', lang: 'en' } },
          model_id: 'm1',
          dynamic_attributes: { temperature: 0.5 },
        },
      ],
      [
        {
          inputs: { in: { text: 'row two', lang: 'de' } },
          model_id: 'm1',
          dynamic_attributes: { temperature: 0.5 },
        },
      ],
      [
        {
          inputs: { in: { text: 'row three', lang: 'fr' } },
          model_id: 'm1',
          dynamic_attributes: { temperature: 0.5 },
        },
      ],
    ])
    expect(wrapper.get('.upload button').text()).toBe('Download')
    await wrapper.get('.upload button').trigger('click')

    expect(downloadFileFromBlob).toHaveBeenCalledWith(expect.any(Blob), 'dfs-predictions')
    expect(await readDownload()).toEqual([
      { inputs: '{"text":"row one","lang":"en"}', prediction: 'Yes, "approved"\nnext' },
      { inputs: '{"text":"row two","lang":"de"}', prediction: '{"text":"second result"}' },
      { inputs: '{"text":"row three","lang":"fr"}', prediction: 'third result' },
    ])
    expect(addToast).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('keeps a single row and numeric input values intact', async () => {
    getDataForTraining.mockReturnValue({ text: ['single row'], count: [0] })
    const wrapper = await mountPredict()

    await wrapper.get('.upload button').trigger('click')
    await flushPromises()
    await wrapper.get('.upload button').trigger('click')

    expect(computePythonModel).toHaveBeenCalledTimes(1)
    expect(computePythonModel).toHaveBeenCalledWith({
      inputs: { in: { text: 'single row', count: 0 } },
      model_id: 'm1',
      dynamic_attributes: { temperature: 0.5 },
    })
    expect(await readDownload()).toEqual([
      { inputs: '{"text":"single row","count":0}', prediction: 'prediction' },
    ])
    wrapper.unmount()
  })

  it.each([{}, { text: [] }])(
    'rejects an empty dataset %j without predicting or exporting',
    async (data) => {
      getDataForTraining.mockReturnValue(data)
      const wrapper = await mountPredict()

      await wrapper.get('.upload button').trigger('click')
      await flushPromises()

      expect(computePythonModel).not.toHaveBeenCalled()
      expect(addToast).toHaveBeenCalledWith(
        expect.objectContaining({ detail: 'The CSV file has no rows to predict.' }),
      )
      expect(wrapper.get('.upload button').text()).toBe('Predict')
      expect(wrapper.get('.upload button').attributes('data-loading')).toBe('false')
      expect(wrapper.findComponent({ name: 'FileInput' }).props('error')).toBe(true)
      expect(downloadFileFromBlob).not.toHaveBeenCalled()
      wrapper.unmount()
    },
  )

  it('keeps the other rows after a rejected request and reports the failure in the file', async () => {
    computePythonModel.mockResolvedValueOnce({
      status: 'success',
      predictions: { out: 'first result' },
    })
    computePythonModel.mockRejectedValueOnce(new Error('Prediction failed'))
    const wrapper = await mountPredict()

    await wrapper.get('.upload button').trigger('click')
    await flushPromises()

    expect(computePythonModel).toHaveBeenCalledTimes(3)
    expect(addToast).toHaveBeenCalledTimes(1)
    expect(addToast).toHaveBeenCalledWith(
      expect.objectContaining({
        severity: 'warn',
        detail:
          '1 of 3 rows failed. Their errors are in the prediction column of the downloaded file.',
      }),
    )
    expect(wrapper.findComponent({ name: 'FileInput' }).props('error')).toBe(false)
    expect(wrapper.get('.upload button').text()).toBe('Download')
    await wrapper.get('.upload button').trigger('click')
    expect(await readDownload()).toEqual([
      { inputs: '{"text":"row one","lang":"en"}', prediction: 'first result' },
      { inputs: '{"text":"row two","lang":"de"}', prediction: 'Error: Prediction failed' },
      { inputs: '{"text":"row three","lang":"fr"}', prediction: 'prediction' },
    ])
    wrapper.unmount()
  })

  it('does not offer a download when every row fails and allows retry', async () => {
    computePythonModel
      .mockRejectedValueOnce(new Error('Provider is down'))
      .mockRejectedValueOnce(new Error('Provider is down'))
      .mockRejectedValueOnce(new Error('Provider is down'))
    const wrapper = await mountPredict()

    await wrapper.get('.upload button').trigger('click')
    await flushPromises()

    expect(computePythonModel).toHaveBeenCalledTimes(3)
    expect(addToast).toHaveBeenCalledTimes(1)
    expect(addToast).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'error', detail: 'Provider is down' }),
    )
    expect(wrapper.get('.upload button').text()).toBe('Predict')
    expect(wrapper.get('.upload button').attributes('data-loading')).toBe('false')
    expect(wrapper.findComponent({ name: 'FileInput' }).props('error')).toBe(true)
    expect(downloadFileFromBlob).not.toHaveBeenCalled()

    await wrapper.get('.upload button').trigger('click')
    await flushPromises()
    expect(computePythonModel).toHaveBeenCalledTimes(6)
    expect(wrapper.findComponent({ name: 'FileInput' }).props('error')).toBe(false)
    await wrapper.get('.upload button').trigger('click')
    expect(await readDownload()).toHaveLength(3)
    wrapper.unmount()
  })
})
