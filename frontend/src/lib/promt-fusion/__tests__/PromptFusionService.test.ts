import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/data-processing/DataProcessingWorker', () => ({
  DataProcessingWorker: {
    startTraining: vi.fn(),
    deallocateModels: vi.fn().mockResolvedValue([null]),
  },
}))

import { DataProcessingWorker } from '@/lib/data-processing/DataProcessingWorker'
import { promptFusionService } from '../PromptFusionService'
import { WEBWORKER_ROUTES_ENUM } from '@/lib/data-processing/interfaces'

afterEach(() => vi.useRealTimers())

describe('prompt fusion first-use loading', () => {
  it('keeps training active during initialization and clears it after initialization fails', async () => {
    vi.useFakeTimers()
    let reject!: (reason: Error) => void
    vi.mocked(DataProcessingWorker.startTraining).mockReturnValue(
      new Promise((_resolve, fail) => {
        reject = fail
      }),
    )
    const states = vi.fn()
    promptFusionService.on('CHANGE_TRAINING_STATE', states)
    const pending = promptFusionService.runOptimization()
    await vi.runAllTimersAsync()
    expect(states).toHaveBeenLastCalledWith(true)
    reject(new Error('Download failed'))
    await expect(pending).rejects.toThrow('Download failed')
    await vi.runAllTimersAsync()
    expect(states).toHaveBeenLastCalledWith(false)
    promptFusionService.off('CHANGE_TRAINING_STATE', states)
  })
})

describe('prompt fusion cleanup', () => {
  it('deallocates the stored prompt model while resetting its ID', async () => {
    promptFusionService.modelId = 'prompt'
    await promptFusionService.resetState()
    expect(DataProcessingWorker.deallocateModels).toHaveBeenCalledExactlyOnceWith(
      ['prompt'],
      WEBWORKER_ROUTES_ENUM.STORE_DEALLOCATE,
    )
    expect(promptFusionService.modelId).toBeNull()
    vi.mocked(DataProcessingWorker.deallocateModels).mockClear()
    await promptFusionService.resetState()
    expect(DataProcessingWorker.deallocateModels).toHaveBeenCalledWith(
      [],
      WEBWORKER_ROUTES_ENUM.STORE_DEALLOCATE,
    )
  })

  it('propagates cleanup failures', async () => {
    promptFusionService.modelId = 'prompt'
    vi.mocked(DataProcessingWorker.deallocateModels).mockRejectedValueOnce(
      new Error('Cleanup failed'),
    )
    await expect(promptFusionService.resetState()).rejects.toThrow('Cleanup failed')
    expect(promptFusionService.modelId).toBeNull()
    await promptFusionService.resetState()
  })
})

it('resets state immediately and preserves new state while cleanup is pending', async () => {
  let resolve!: (value: []) => void
  vi.mocked(DataProcessingWorker.deallocateModels).mockReturnValueOnce(
    new Promise((done) => {
      resolve = done
    }),
  )
  promptFusionService.modelId = 'old'
  promptFusionService.taskDescription = 'old task'
  const pending = promptFusionService.resetState()
  expect(promptFusionService.modelId).toBeNull()
  expect(promptFusionService.taskDescription).toBe('')
  promptFusionService.modelId = 'new'
  promptFusionService.taskDescription = 'new task'
  resolve([])
  await pending
  expect(promptFusionService.modelId).toBe('new')
  expect(promptFusionService.taskDescription).toBe('new task')
  await promptFusionService.resetState()
})
