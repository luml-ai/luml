import { describe, expect, it, vi } from 'vitest'

import { deleteExperimentConfirmOptions } from '@/confirm/confirm'
import type { Experiment } from '@/store/experiments/experiments.interface'

function experiment(metadata: Record<string, unknown>): Experiment {
  return {
    id: 'experiment-1',
    name: 'evaluate',
    created_at: '2026-08-29T00:00:00Z',
    tags: ['main', 'evaluate'],
    models: null,
    duration: 1,
    description: '',
    static_params: null,
    dynamic_params: null,
    status: 'completed',
    source: null,
    group_name: 'churn',
    group_id: 'group-1',
    metadata,
  }
}

describe('experiment deletion confirmation', () => {
  it('names the producing flow, cell, and lane', () => {
    const selected = experiment({
      lumlflow: {
        flow: 'churn',
        slug: 'evaluate',
        lane: 'main',
      },
    })

    const options = deleteExperimentConfirmOptions(vi.fn(), [selected])

    expect(options.message).toContain('churn / evaluate on lane main')
  })

  it('keeps the generic confirmation for experiments without complete lumlflow metadata', () => {
    const selected = experiment({ lumlflow: { flow: 'churn', slug: 'evaluate' } })

    const options = deleteExperimentConfirmOptions(vi.fn(), [selected])

    expect(options.message).toBe('This action is permanent and cannot be undone.')
  })
})
