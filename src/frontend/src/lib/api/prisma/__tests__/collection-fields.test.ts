import { describe, it, expect } from 'vitest'
import type {
  RunConfig,
  RunCreate,
  PendingUpload,
  UploadReadyEvent,
} from '@/lib/api/prisma/prisma.interfaces'

describe('RunConfig collection fields', () => {
  it('includes luml collection fields', () => {
    const config: RunConfig = {
      max_depth: 3,
      max_children_per_fork: 2,
      max_debug_retries: 1,
      max_concurrency: 1,
      run_command_template: 'uv run main.py',
      agent_id: 'a',
      auto_mode: false,
      auto_terminate_timeout: 300,
      implement_timeout: 1800,
      run_timeout: 0,
      debug_timeout: 1800,
      fork_timeout: 900,
      primary_metric: 'metric',
      luml_collection_id: 'col-1',
      luml_organization_id: 'org-1',
      luml_orbit_id: 'orb-1',
    }
    expect(config.luml_collection_id).toBe('col-1')
    expect(config.luml_organization_id).toBe('org-1')
    expect(config.luml_orbit_id).toBe('orb-1')
  })

  it('allows null collection fields', () => {
    const config: RunConfig = {
      max_depth: 3,
      max_children_per_fork: 2,
      max_debug_retries: 1,
      max_concurrency: 1,
      run_command_template: '',
      agent_id: 'a',
      auto_mode: false,
      auto_terminate_timeout: 300,
      implement_timeout: 1800,
      run_timeout: 0,
      debug_timeout: 1800,
      fork_timeout: 900,
      primary_metric: 'metric',
      luml_collection_id: null,
      luml_organization_id: null,
      luml_orbit_id: null,
    }
    expect(config.luml_collection_id).toBeNull()
  })
})

describe('RunCreate collection fields', () => {
  it('accepts optional collection fields', () => {
    const create: RunCreate = {
      repository_id: 'repo-1',
      name: 'test',
      objective: 'test objective',
      luml_collection_id: 'col-1',
      luml_organization_id: 'org-1',
      luml_orbit_id: 'orb-1',
    }
    expect(create.luml_collection_id).toBe('col-1')
  })

  it('works without collection fields', () => {
    const create: RunCreate = {
      repository_id: 'repo-1',
      name: 'test',
      objective: 'test objective',
    }
    expect(create.luml_collection_id).toBeUndefined()
  })
})

describe('PendingUpload interface', () => {
  it('has all required fields', () => {
    const upload: PendingUpload = {
      id: 'u1',
      run_id: 'r1',
      node_id: 'n1',
      model_path: '/tmp/model.luml',
      experiment_ids: ['exp-1', 'exp-2'],
      file_size: 1024,
      status: 'pending',
      error: null,
      retry_count: 0,
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    }
    expect(upload.id).toBe('u1')
    expect(upload.experiment_ids).toEqual(['exp-1', 'exp-2'])
    expect(upload.error).toBeNull()
  })
})

describe('UploadReadyEvent interface', () => {
  it('has all required fields', () => {
    const event: UploadReadyEvent = {
      upload_id: 'u1',
      run_id: 'r1',
      node_id: 'n1',
      file_size: 2048,
      experiment_ids: ['exp-1'],
      collection_id: 'col-1',
      organization_id: 'org-1',
      orbit_id: 'orb-1',
      manifest: { type: 'model', variant: 'test' },
      file_index: { 'manifest.json': [0, 100] },
    }
    expect(event.collection_id).toBe('col-1')
    expect(event.file_size).toBe(2048)
  })
})
