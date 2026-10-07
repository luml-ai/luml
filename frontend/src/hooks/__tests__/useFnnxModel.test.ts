import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { fromBuffer, initialize, deinitialize, warmup, getManifest } = vi.hoisted(() => ({
  fromBuffer: vi.fn(),
  initialize: vi.fn(),
  deinitialize: vi.fn(),
  warmup: vi.fn(),
  getManifest: vi.fn(),
}))

vi.mock('@fnnx-ai/web', () => ({ Model: { fromBuffer } }))
vi.mock('@/lib/fnnx/FnnxService', () => ({
  FnnxService: { getTypeTag: () => 'prompt_optimization' },
}))
vi.mock('@/lib/data-processing/DataProcessingWorker', () => ({
  DataProcessingWorker: { initPythonModel: initialize, deinitPythonModel: deinitialize },
}))

import { useFnnxModel } from '../useFnnxModel'

const buffer = new ArrayBuffer(1)
const file = Object.assign(new File(['model'], 'model.luml'), { arrayBuffer: async () => buffer })

beforeEach(() => {
  vi.clearAllMocks()
  fromBuffer.mockResolvedValue({ getManifest, warmup })
  getManifest.mockReturnValue({ variant: 'pyfunc' })
})

describe('FNNX first-use initialization', () => {
  it('keeps uploading pending until the Python worker is ready and the model is initialized', async () => {
    let resolve!: (value: unknown) => void
    initialize.mockReturnValue(
      new Promise((done) => {
        resolve = done
      }),
    )
    const hook = useFnnxModel()
    const complete = vi.fn()
    const pending = hook.createModelFromFile(file).then(complete)
    await flushPromises()
    expect(initialize).toHaveBeenCalledWith(buffer)
    expect(complete).not.toHaveBeenCalled()
    expect(hook.modelId.value).toBeNull()
    resolve({ status: 'success', model_id: 'model' })
    await pending
    expect(hook.modelId.value).toBe('model')
    expect(complete).toHaveBeenCalledTimes(1)
  })

  it('propagates initialization errors to the upload loading and error handler', async () => {
    initialize.mockRejectedValue(new Error('Download failed'))
    await expect(useFnnxModel().createModelFromFile(file)).rejects.toThrow('Download failed')
  })

  it('warms up non-Python models without initializing Pyodide', async () => {
    getManifest.mockReturnValue({ variant: 'onnx' })
    await useFnnxModel().createModelFromFile(file)
    expect(warmup).toHaveBeenCalledTimes(1)
    expect(initialize).not.toHaveBeenCalled()
  })

  it('does not initialize Pyodide when cleaning up without a model', async () => {
    await useFnnxModel().deinit()
    expect(deinitialize).not.toHaveBeenCalled()
    expect(initialize).not.toHaveBeenCalled()
  })
})
