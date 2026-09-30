import axios, { type AxiosRequestConfig } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { useArtifactUpload } from '../useArtifactUpload'
import { ArtifactStatusEnum, ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces'

const harness = vi.hoisted(() => ({
  initiate: vi.fn(),
  confirm: vi.fn(),
  cancel: vi.fn(),
  createModel: vi.fn(),
}))
vi.mock('@/stores/artifacts', () => ({
  useArtifactsStore: () => ({
    initiateCreateArtifact: harness.initiate,
    confirmArtifactUpload: harness.confirm,
    cancelArtifactUpload: harness.cancel,
  }),
}))
vi.mock('@/helpers/helpers', () => ({ getSha256: vi.fn().mockResolvedValue('hash') }))
vi.mock('@/lib/fnnx/FnnxService', () => ({
  FnnxService: { createModelFromFile: harness.createModel, getRegistryMetrics: () => ({}) },
}))
vi.mock('@/lib/tar-handler/TarHandler', () => ({
  TarHandler: class {
    scan() {
      return new Map()
    }
  },
}))

describe('useArtifactUpload', () => {
  let file: File
  const requestInfo = { organizationId: 'org', orbitId: 'orbit', collectionId: 'collection' }

  beforeEach(() => {
    file = new File(['model'], 'model.luml')
    file.arrayBuffer = vi.fn().mockResolvedValue(new ArrayBuffer(5))
    harness.createModel.mockReset().mockResolvedValue({ getManifest: () => ({}) })
    harness.initiate.mockReset().mockResolvedValue({
      artifact: { id: 'artifact' },
      upload_details: { url: 'https://storage.example.com/model' },
    })
    harness.confirm.mockReset().mockResolvedValue(undefined)
    harness.cancel.mockReset().mockResolvedValue(undefined)
    vi.spyOn(axios, 'put').mockResolvedValue({})
  })

  function startUpload(hook: ReturnType<typeof useArtifactUpload>, signal?: AbortSignal) {
    return hook.upload(
      file,
      'Model',
      ArtifactTypeEnum.model,
      'Description',
      ['tag'],
      requestInfo,
      signal,
    )
  }

  it('passes the abort signal to the storage request and reports progress', async () => {
    const hook = useArtifactUpload()
    const controller = new AbortController()
    vi.mocked(axios.put).mockImplementation(async (_url, _buffer, config) => {
      expect(config?.signal).toBe(controller.signal)
      config?.onUploadProgress?.({ loaded: 42, total: 100, bytes: 42, lengthComputable: true })
      expect(hook.progress.value).toBe(42)
    })
    await startUpload(hook, controller.signal)
    expect(harness.confirm).toHaveBeenCalledWith(
      expect.objectContaining({ status: ArtifactStatusEnum.uploaded }),
      requestInfo,
    )
    expect(hook.progress.value).toBeNull()
  })

  it('aborts an active request and marks the artifact failed without confirming it', async () => {
    const hook = useArtifactUpload()
    const controller = new AbortController()
    vi.mocked(axios.put).mockImplementation(
      (_url, _buffer, config) =>
        new Promise((_resolve, reject) => {
          config?.signal?.addEventListener?.('abort', () =>
            reject(new axios.CanceledError('Cancelled')),
          )
        }),
    )
    const upload = startUpload(hook, controller.signal)
    const rejected = expect(upload).rejects.toThrow('Cancelled')
    await flushPromises()
    controller.abort()
    await rejected
    expect(harness.cancel).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'artifact', status: ArtifactStatusEnum.upload_failed }),
      requestInfo,
    )
    expect(harness.confirm).not.toHaveBeenCalled()
    expect(hook.progress.value).toBeNull()
  })

  it('does not create an artifact when already cancelled', async () => {
    const controller = new AbortController()
    controller.abort()
    await expect(startUpload(useArtifactUpload(), controller.signal)).rejects.toMatchObject({
      name: 'AbortError',
    })
    expect(harness.createModel).not.toHaveBeenCalled()
    expect(harness.initiate).not.toHaveBeenCalled()
  })

  it('stops before artifact creation when cancelled during file preparation', async () => {
    const controller = new AbortController()
    harness.createModel.mockImplementation(async () => {
      controller.abort()
      return { getManifest: () => ({}) }
    })
    await expect(startUpload(useArtifactUpload(), controller.signal)).rejects.toMatchObject({
      name: 'AbortError',
    })
    expect(harness.initiate).not.toHaveBeenCalled()
    expect(axios.put).not.toHaveBeenCalled()
  })

  it('cleans up when cancelled during artifact creation', async () => {
    const controller = new AbortController()
    harness.initiate.mockImplementation(async () => {
      controller.abort()
      return {
        artifact: { id: 'artifact' },
        upload_details: { url: 'https://storage.example.com/model' },
      }
    })
    await expect(startUpload(useArtifactUpload(), controller.signal)).rejects.toMatchObject({
      name: 'AbortError',
    })
    expect(axios.put).not.toHaveBeenCalled()
    expect(harness.cancel).toHaveBeenCalled()
    expect(harness.confirm).not.toHaveBeenCalled()
  })

  it('ignores old progress and cleanup when another upload has started', async () => {
    const hook = useArtifactUpload()
    const controller = new AbortController()
    let oldConfig: AxiosRequestConfig | undefined
    let rejectOld: (error: Error) => void = () => {}
    let resolveNew: () => void = () => {}
    vi.mocked(axios.put)
      .mockImplementationOnce(
        (_url, _buffer, config) =>
          new Promise((_resolve, reject) => {
            oldConfig = config
            rejectOld = reject
          }),
      )
      .mockImplementationOnce(
        (_url, _buffer, config) =>
          new Promise((resolve) => {
            config?.onUploadProgress?.({
              loaded: 50,
              total: 100,
              bytes: 50,
              lengthComputable: true,
            })
            resolveNew = () => resolve({})
          }),
      )
    const oldUpload = startUpload(hook, controller.signal)
    const rejected = expect(oldUpload).rejects.toThrow('Cancelled')
    await flushPromises()
    controller.abort()
    const newUpload = startUpload(hook)
    await flushPromises()
    oldConfig?.onUploadProgress?.({ loaded: 99, total: 100, bytes: 99, lengthComputable: true })
    expect(hook.progress.value).toBe(50)
    rejectOld(new axios.CanceledError('Cancelled'))
    await rejected
    expect(hook.progress.value).toBe(50)
    resolveNew()
    await newUpload
    expect(hook.progress.value).toBeNull()
  })

  it('preserves storage failures and cleanup for callers without an abort signal', async () => {
    vi.mocked(axios.put).mockRejectedValue(new Error('Storage failed'))
    const hook = useArtifactUpload()
    await expect(startUpload(hook)).rejects.toThrow('Storage failed')
    expect(harness.cancel).toHaveBeenCalled()
    expect(harness.confirm).not.toHaveBeenCalled()
    expect(hook.progress.value).toBeNull()
  })
})
