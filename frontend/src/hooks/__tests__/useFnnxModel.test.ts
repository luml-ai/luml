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

describe('FNNX model cleanup', () => {
  beforeEach(() => {
    initialize.mockResolvedValue({ status: 'success', model_id: 'first' })
    deinitialize.mockResolvedValue({ status: 'success' })
  })

  it('deinitializes the previous Python model before uploading a replacement', async () => {
    const hook = useFnnxModel()
    await hook.createModelFromFile(file)
    initialize.mockResolvedValue({ status: 'success', model_id: 'second' })
    await hook.createModelFromFile(file)
    expect(deinitialize).toHaveBeenCalledExactlyOnceWith('first')
    expect(deinitialize.mock.invocationCallOrder[0]).toBeLessThan(
      initialize.mock.invocationCallOrder[1],
    )
    expect(hook.modelId.value).toBe('second')
  })

  it('clears the Python ID when switching to a non-Python model', async () => {
    const hook = useFnnxModel()
    await hook.createModelFromFile(file)
    getManifest.mockReturnValue({ variant: 'onnx' })
    await hook.createModelFromFile(file)
    expect(deinitialize).toHaveBeenCalledWith('first')
    expect(hook.modelId.value).toBeNull()
    await hook.deinit()
    expect(deinitialize).toHaveBeenCalledTimes(1)
  })

  it('removes a model once and clears its state after deinitialization', async () => {
    const hook = useFnnxModel()
    await hook.createModelFromFile(file)
    await hook.removeModel()
    await hook.deinit()
    expect(deinitialize).toHaveBeenCalledExactlyOnceWith('first')
    expect(hook.modelId.value).toBeNull()
    expect(hook.getModel.value).toBeNull()
    expect(hook.currentTag.value).toBeNull()
  })

  it('shares simultaneous cleanup instead of deleting the same model twice', async () => {
    const hook = useFnnxModel()
    await hook.createModelFromFile(file)
    let resolve!: () => void
    deinitialize.mockReturnValue(
      new Promise<void>((done) => {
        resolve = done
      }),
    )
    const first = hook.deinit()
    const second = hook.removeModel()
    expect(deinitialize).toHaveBeenCalledTimes(1)
    resolve()
    await Promise.all([first, second])
    expect(hook.modelId.value).toBeNull()
  })

  it('keeps the old model available for retry if cleanup fails and does not initialize a replacement', async () => {
    const hook = useFnnxModel()
    await hook.createModelFromFile(file)
    const previous = hook.getModel.value
    deinitialize.mockRejectedValueOnce(new Error('Cleanup failed'))
    await expect(hook.createModelFromFile(file)).rejects.toThrow('Cleanup failed')
    expect(hook.modelId.value).toBe('first')
    expect(hook.getModel.value).toBe(previous)
    expect(initialize).toHaveBeenCalledTimes(1)
    await hook.removeModel()
    expect(deinitialize).toHaveBeenCalledTimes(2)
    expect(hook.modelId.value).toBeNull()
  })

  it('does not remove a model when the replacement has an invalid extension', async () => {
    const hook = useFnnxModel()
    await hook.createModelFromFile(file)
    await expect(hook.createModelFromFile(new File([], 'invalid.zip'))).rejects.toThrow(
      'Incorrect file format',
    )
    expect(deinitialize).not.toHaveBeenCalled()
    expect(hook.modelId.value).toBe('first')
  })
})

it('deinitializes a model that finishes uploading after page cleanup was requested', async () => {
  let resolve!: (value: unknown) => void
  initialize.mockReturnValue(
    new Promise((done) => {
      resolve = done
    }),
  )
  deinitialize.mockResolvedValue({ status: 'success' })
  const hook = useFnnxModel()
  const pending = hook.createModelFromFile(file)
  await flushPromises()
  await hook.deinit()
  resolve({ status: 'success', model_id: 'late' })
  await pending
  expect(deinitialize).toHaveBeenCalledExactlyOnceWith('late')
  expect(hook.modelId.value).toBeNull()
})
