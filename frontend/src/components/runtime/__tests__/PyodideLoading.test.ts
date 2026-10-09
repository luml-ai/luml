import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PrimeVue from 'primevue/config'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'

const { compute, addToast, training, deallocate } = vi.hoisted(() => ({
  compute: vi.fn(),
  addToast: vi.fn(),
  training: vi.fn(),
  deallocate: vi.fn(),
}))

vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: addToast }),
}))
vi.mock('primevue/usetoast', () => ({ useToast: () => ({ add: addToast }) }))
vi.mock('@/lib/data-processing/DataProcessingWorker', () => ({
  DataProcessingWorker: {
    computePythonModel: compute,
    startTraining: training,
    deallocateModels: deallocate,
  },
}))
vi.mock('@/lib/analytics/AnalyticsService', () => ({
  AnalyticsService: { track: vi.fn() },
  AnalyticsTrackKeysEnum: {},
}))
vi.mock('@/hooks/useDataTable', async () => {
  const { ref } = await import('vue')
  return {
    useDataTable: () => ({
      isUploadWithErrors: ref(false),
      fileData: ref({}),
      onSelectFile: vi.fn(),
      onRemoveFile: vi.fn(),
      getDataForTraining: vi.fn(),
    }),
  }
})

import Predict from '../dashboard/prompt-optimization/RuntimeDashboardPromptOptimizationPredict.vue'
import UploadData from '../UploadData.vue'
import FileInput from '@/components/ui/FileInput.vue'
import { useModelTraining } from '@/hooks/useModelTraining'
import { Tasks } from '@/lib/data-processing/interfaces'

beforeEach(() => vi.clearAllMocks())

const global = {
  plugins: [PrimeVue],
  components: { DButton: Button },
  stubs: { FileInput: true, SelectButton: true, FloatLabel: { template: '<div><slot /></div>' } },
}

describe('first-use loading feedback', () => {
  it('keeps the manual runtime prediction spinner active while Pyodide is pending', async () => {
    let resolve!: (value: unknown) => void
    compute.mockReturnValue(
      new Promise((done) => {
        resolve = done
      }),
    )
    const wrapper = mount(Predict, {
      props: {
        manualFields: ['text'],
        modelId: 'model',
        dynamicAttributes: {},
        providerConnected: true,
      },
      global,
    })
    await wrapper.getComponent(InputText).setValue('input')
    await wrapper.getComponent(Button).trigger('click')
    expect(wrapper.getComponent(Button).props('loading')).toBe(true)
    resolve({ status: 'success', predictions: { out: 'prediction' } })
    await flushPromises()
    expect(wrapper.getComponent(Button).props('loading')).toBe(false)
    expect(wrapper.get('textarea').element.value).toContain('prediction')
    wrapper.unmount()
  })

  it('clears prediction loading and reports initialization failures', async () => {
    compute.mockRejectedValue(new Error('Download failed'))
    const wrapper = mount(Predict, {
      props: {
        manualFields: ['text'],
        modelId: 'model',
        dynamicAttributes: {},
        providerConnected: true,
      },
      global,
    })
    await wrapper.getComponent(InputText).setValue('input')
    await wrapper.getComponent(Button).trigger('click')
    await flushPromises()
    expect(wrapper.getComponent(Button).props('loading')).toBe(false)
    expect(addToast).toHaveBeenCalledWith(expect.objectContaining({ detail: 'Download failed' }))
    wrapper.unmount()
  })

  it('keeps FNNX upload loading until model initialization completes', async () => {
    let resolve!: () => void
    const uploadCallback = vi.fn(
      () =>
        new Promise<void>((done) => {
          resolve = done
        }),
    )
    const wrapper = mount(UploadData, {
      props: { uploadCallback, removeCallback: vi.fn() },
      global,
    })
    wrapper.getComponent(FileInput).vm.$emit('select-file', new File(['model'], 'model.luml'))
    await flushPromises()
    expect(wrapper.getComponent(FileInput).props('loading')).toBe(true)
    expect(wrapper.findAll('button').at(-1)!.attributes('disabled')).toBeDefined()
    resolve()
    await flushPromises()
    expect(wrapper.getComponent(FileInput).props('loading')).toBe(false)
    expect(wrapper.findAll('button').at(-1)!.attributes('disabled')).toBeUndefined()
    wrapper.unmount()
  })

  it('keeps express training loading until the worker finishes initialization and training', async () => {
    let reject!: (reason: Error) => void
    training.mockReturnValue(
      new Promise((_resolve, fail) => {
        reject = fail
      }),
    )
    let hook!: ReturnType<typeof useModelTraining>
    const wrapper = mount(
      defineComponent({
        setup() {
          hook = useModelTraining('tabular')
          return () => null
        },
      }),
    )
    const pending = hook.startTraining({ data: {}, target: 'y', task: Tasks.TABULAR_REGRESSION })
    expect(hook.isLoading.value).toBe(true)
    reject(new Error('Download failed'))
    await pending
    expect(hook.isLoading.value).toBe(false)
    expect(addToast).toHaveBeenCalledWith(expect.objectContaining({ detail: 'Download failed' }))
    wrapper.unmount()
  })
})

describe('runtime upload cleanup', () => {
  it('keeps removal pending until cleanup succeeds and clears the uploaded file', async () => {
    let resolve!: () => void
    const removeCallback = vi.fn(
      () =>
        new Promise<void>((done) => {
          resolve = done
        }),
    )
    const wrapper = mount(UploadData, {
      props: { uploadCallback: vi.fn(), removeCallback },
      global,
    })
    wrapper.getComponent(FileInput).vm.$emit('select-file', new File(['model'], 'model.luml'))
    await flushPromises()
    wrapper.getComponent(FileInput).vm.$emit('remove-file')
    await flushPromises()
    expect(wrapper.getComponent(FileInput).props('loading')).toBe(true)
    expect(wrapper.findAll('button').at(-1)!.attributes('disabled')).toBeDefined()
    resolve()
    await flushPromises()
    expect(wrapper.getComponent(FileInput).props('file')).toEqual({})
    expect(wrapper.getComponent(FileInput).props('loading')).toBe(false)
    wrapper.unmount()
  })

  it('reports cleanup failures instead of discarding the file', async () => {
    const wrapper = mount(UploadData, {
      props: {
        uploadCallback: vi.fn(),
        removeCallback: vi.fn().mockRejectedValue(new Error('Cleanup failed')),
      },
      global,
    })
    wrapper.getComponent(FileInput).vm.$emit('select-file', new File(['model'], 'model.luml'))
    await flushPromises()
    wrapper.getComponent(FileInput).vm.$emit('remove-file')
    await flushPromises()
    expect(addToast).toHaveBeenCalledWith(expect.objectContaining({ detail: 'Cleanup failed' }))
    expect(wrapper.getComponent(FileInput).props('file')).toEqual({ name: 'model.luml', size: 5 })
    expect(wrapper.getComponent(FileInput).props('error')).toBe(true)
    expect(wrapper.getComponent(FileInput).props('loading')).toBe(false)
    wrapper.unmount()
  })
})

it('ignores another upload while model creation is pending', async () => {
  let resolve!: () => void
  const uploadCallback = vi.fn(
    () =>
      new Promise<void>((done) => {
        resolve = done
      }),
  )
  const wrapper = mount(UploadData, { props: { uploadCallback, removeCallback: vi.fn() }, global })
  wrapper.getComponent(FileInput).vm.$emit('select-file', new File(['first'], 'first.luml'))
  await flushPromises()
  wrapper.getComponent(FileInput).vm.$emit('select-file', new File(['second'], 'second.luml'))
  await flushPromises()
  expect(uploadCallback).toHaveBeenCalledTimes(1)
  resolve()
  await flushPromises()
  wrapper.unmount()
})

it('disables continue after a replacement upload fails', async () => {
  const uploadCallback = vi
    .fn()
    .mockResolvedValueOnce(undefined)
    .mockRejectedValueOnce(new Error('Invalid model'))
  const wrapper = mount(UploadData, { props: { uploadCallback, removeCallback: vi.fn() }, global })
  wrapper.getComponent(FileInput).vm.$emit('select-file', new File(['first'], 'first.luml'))
  await flushPromises()
  wrapper.getComponent(FileInput).vm.$emit('select-file', new File(['invalid'], 'invalid.luml'))
  await flushPromises()
  expect(wrapper.findAll('button').at(-1)!.attributes('disabled')).toBeDefined()
  wrapper.unmount()
})
