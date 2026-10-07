import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/data-processing/DataProcessingWorker', () => ({
  DataProcessingWorker: { startTraining: vi.fn() },
}))

import { DataProcessingWorker } from '@/lib/data-processing/DataProcessingWorker'
import { promptFusionService } from '../PromptFusionService'

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
