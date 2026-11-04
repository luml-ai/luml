import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useUploadFlow } from '@/hooks/useUploadFlow'
import type { CreateArtifactResponse } from '@/lib/api/artifacts/interfaces'
import type { UploadReadyEvent } from '@/lib/api/prisma/prisma.interfaces'

vi.mock('@/lib/api', () => ({
  api: {
    artifacts: {
      create: vi.fn(),
    },
    dataAgent: {
      postUploadUrl: vi.fn(),
      getPendingUploads: vi.fn(),
      dismissUpload: vi.fn(),
    },
  },
}))

import { api } from '@/lib/api'

const mockArtifactsCreate = vi.mocked(api.artifacts.create)
const mockPostUploadUrl = vi.mocked(api.dataAgent.postUploadUrl)
const mockGetPendingUploads = vi.mocked(api.dataAgent.getPendingUploads)
const mockDismissUpload = vi.mocked(api.dataAgent.dismissUpload)

function makeUploadReadyEvent(overrides: Partial<UploadReadyEvent> = {}): UploadReadyEvent {
  return {
    upload_id: 'upload-1',
    run_id: 'run-1',
    node_id: 'node-1',
    file_size: 1024,
    experiment_ids: ['exp-1'],
    collection_id: 'col-1',
    organization_id: 'org-1',
    orbit_id: 'orb-1',
    manifest: {
      variant: 'pyfunc',
      producer_name: 'luml.ai',
      producer_version: '0.3.0',
      producer_tags: ['training'],
      inputs: [],
      outputs: [],
      dynamic_attributes: [],
      env_vars: [],
    },
    file_index: { 'manifest.json': [0, 128], 'model.pkl': [128, 896] },
    ...overrides,
  }
}

describe('useUploadFlow', () => {
  let flow: ReturnType<typeof useUploadFlow>

  beforeEach(() => {
    vi.resetAllMocks()
    mockArtifactsCreate.mockResolvedValue({
      artifact: { id: 'artifact-1' },
      upload_details: { url: 'https://presigned.example.com/upload' },
    } as CreateArtifactResponse)
    mockPostUploadUrl.mockResolvedValue(202)
    flow = useUploadFlow()
  })

  describe('handleUploadReady', () => {
    it.each(['manifest', 'file_index'] as const)(
      'refuses artifact creation when %s is missing',
      async (field) => {
        const event = makeUploadReadyEvent()
        delete (event as Partial<UploadReadyEvent>)[field]

        flow.handleUploadReady(event)
        await flow.retryUpload(event.upload_id)

        expect(mockArtifactsCreate).not.toHaveBeenCalled()
        expect(mockPostUploadUrl).not.toHaveBeenCalled()
        expect(flow.uploads.value.get(event.upload_id)?.status).toBe('failed')
      },
    )

    it('creates artifact and posts presigned URL to agent-backend', async () => {
      mockArtifactsCreate.mockResolvedValue({
        artifact: {} as unknown,
        upload_details: {
          url: 'https://presigned.example.com/upload',
          multipart: false,
          bucket_location: 'bucket',
          bucket_secret_id: 'secret',
        },
      })
      mockPostUploadUrl.mockResolvedValue(202)

      const event = makeUploadReadyEvent()
      flow.handleUploadReady(event)

      await vi.waitFor(() => {
        expect(mockArtifactsCreate).toHaveBeenCalledOnce()
      })

      expect(mockArtifactsCreate).toHaveBeenCalledWith(
        'org-1',
        'orb-1',
        'col-1',
        expect.objectContaining({
          type: 'model',
          size: 1024,
        }),
      )
      expect(mockPostUploadUrl).toHaveBeenCalledWith(
        'run-1',
        'upload-1',
        'https://presigned.example.com/upload',
      )
    })

    it('sets status to failed when artifact creation fails', async () => {
      mockArtifactsCreate.mockRejectedValue(new Error('Network error'))

      const event = makeUploadReadyEvent()
      flow.handleUploadReady(event)

      await vi.waitFor(() => {
        const entry = flow.uploads.value.get('upload-1')
        expect(entry?.status).toBe('failed')
      })

      expect(flow.failedUploads.value).toHaveLength(1)
      expect(flow.failedUploads.value[0].error).toBe('Failed to create artifact on LUML backend')
    })

    it('handles 409 conflict (another tab claimed upload)', async () => {
      mockArtifactsCreate.mockResolvedValue({
        artifact: {} as unknown,
        upload_details: {
          url: 'https://presigned.example.com/upload',
          multipart: false,
          bucket_location: 'bucket',
          bucket_secret_id: 'secret',
        },
      })
      mockPostUploadUrl.mockResolvedValue(409)

      const event = makeUploadReadyEvent()
      flow.handleUploadReady(event)

      await vi.waitFor(() => {
        expect(mockPostUploadUrl).toHaveBeenCalledOnce()
      })

      const entry = flow.uploads.value.get('upload-1')
      expect(entry?.status).toBe('uploading')
      expect(entry?.error).toBeNull()
    })

    it('sets status to failed when postUploadUrl throws', async () => {
      mockArtifactsCreate.mockResolvedValue({
        artifact: {} as unknown,
        upload_details: {
          url: 'https://presigned.example.com/upload',
          multipart: false,
          bucket_location: 'bucket',
          bucket_secret_id: 'secret',
        },
      })
      mockPostUploadUrl.mockRejectedValue(new Error('Connection refused'))

      const event = makeUploadReadyEvent()
      flow.handleUploadReady(event)

      await vi.waitFor(() => {
        const entry = flow.uploads.value.get('upload-1')
        expect(entry?.status).toBe('failed')
      })

      expect(flow.failedUploads.value[0].error).toBe(
        'Failed to send presigned URL to agent-backend',
      )
    })
  })

  describe('handleUploadCompleted', () => {
    it('marks upload as completed', async () => {
      flow.handleUploadReady(makeUploadReadyEvent())

      await flow.handleUploadCompleted({
        upload_id: 'upload-1',
        run_id: 'run-1',
        node_id: 'node-1',
      })

      const entry = flow.uploads.value.get('upload-1')
      expect(entry?.status).toBe('completed')
    })
  })

  describe('handleUploadFailed', () => {
    it('marks upload as failed with error message', () => {
      flow.handleUploadFailed({
        upload_id: 'upload-1',
        run_id: 'run-1',
        node_id: 'node-1',
        error: 'Timeout uploading to S3',
        status: 'pending',
      })

      const entry = flow.uploads.value.get('upload-1')
      expect(entry?.status).toBe('failed')
      expect(entry?.error).toBe('Timeout uploading to S3')
      expect(flow.failedUploads.value).toHaveLength(1)
    })
  })

  describe('handleWorktreesPendingUpload', () => {
    it('sets worktrees pending message', () => {
      flow.handleWorktreesPendingUpload({
        run_id: 'run-1',
        message: 'Waiting for 2 uploads to complete',
      })
      expect(flow.worktreesPendingMessage.value).toBe('Waiting for 2 uploads to complete')
    })

    it('uses default message when none provided', () => {
      flow.handleWorktreesPendingUpload({ run_id: 'run-1' })
      expect(flow.worktreesPendingMessage.value).toBe(
        'Worktrees will be cleaned up after uploads complete',
      )
    })
  })

  describe('handleEvent', () => {
    it('dispatches upload_ready events', () => {
      mockArtifactsCreate.mockResolvedValue({
        artifact: {} as unknown,
        upload_details: {
          url: 'https://presigned.example.com/upload',
          multipart: false,
          bucket_location: 'bucket',
          bucket_secret_id: 'secret',
        },
      })
      mockPostUploadUrl.mockResolvedValue(202)

      const event = makeUploadReadyEvent()
      flow.handleEvent('upload_ready', event)
      const entry = flow.uploads.value.get('upload-1')
      expect(entry).toBeDefined()
      expect(entry?.runId).toBe('run-1')
    })

    it('dispatches upload_completed events', async () => {
      flow.handleEvent('upload_ready', makeUploadReadyEvent({ upload_id: 'u1' }))
      flow.handleEvent('upload_completed', { upload_id: 'u1', run_id: 'r1', node_id: 'n1' })
      const entry = flow.uploads.value.get('u1')
      expect(entry?.status).toBe('completed')
    })

    it('dispatches upload_failed events', () => {
      const data = {
        upload_id: 'u1',
        run_id: 'r1',
        node_id: 'n1',
        error: 'fail',
        status: 'pending',
      }
      flow.handleEvent('upload_failed', data)
      const entry = flow.uploads.value.get('u1')
      expect(entry?.status).toBe('failed')
      expect(entry?.error).toBe('fail')
    })

    it('dispatches worktrees_pending_upload events', () => {
      const data = { run_id: 'r1', message: 'Pending cleanup' }
      flow.handleEvent('worktrees_pending_upload', data)
      expect(flow.worktreesPendingMessage.value).toBe('Pending cleanup')
    })

    it('ignores unknown event types', () => {
      flow.handleEvent('unknown_event', { foo: 'bar' })
      expect(flow.activeUploads.value).toHaveLength(0)
    })
  })

  describe('resumePendingUploads', () => {
    const resumableUpload = {
      id: 'upload-a',
      run_id: 'run-1',
      node_id: 'node-1',
      model_path: '/tmp/model.luml',
      experiment_ids: ['exp-1'],
      file_size: 2048,
      status: 'pending',
      error: null,
      retry_count: 0,
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
      manifest: {
        variant: 'pyfunc',
        producer_name: 'luml.ai',
        producer_version: '0.3.0',
        producer_tags: [],
        inputs: [],
        outputs: [],
        dynamic_attributes: [],
        env_vars: [],
      },
      file_index: { 'manifest.json': [0, 128] as [number, number] },
    }

    it('dismisses pending uploads the engine reports without their archive metadata', async () => {
      mockGetPendingUploads.mockResolvedValue([
        { ...resumableUpload, manifest: null, file_index: null },
      ])
      mockDismissUpload.mockResolvedValue()

      await flow.resumePendingUploads('run-1', 'col-1', 'org-1', 'orb-1')

      expect(mockArtifactsCreate).not.toHaveBeenCalled()
      expect(mockDismissUpload).toHaveBeenCalledWith('run-1', 'upload-a')
      expect(flow.activeUploads.value).toHaveLength(0)
    })

    it('fetches pending uploads and triggers upload flow for each', async () => {
      mockGetPendingUploads.mockResolvedValue([resumableUpload])
      mockArtifactsCreate.mockResolvedValue({
        artifact: {} as unknown,
        upload_details: {
          url: 'https://presigned.example.com/upload-a',
          multipart: false,
          bucket_location: 'bucket',
          bucket_secret_id: 'secret',
        },
      })
      mockPostUploadUrl.mockResolvedValue(202)

      await flow.resumePendingUploads('run-1', 'col-1', 'org-1', 'orb-1')

      expect(mockGetPendingUploads).toHaveBeenCalledWith('run-1')

      await vi.waitFor(() => {
        expect(mockArtifactsCreate).toHaveBeenCalledOnce()
      })

      expect(mockArtifactsCreate).toHaveBeenCalledWith(
        'org-1',
        'orb-1',
        'col-1',
        expect.objectContaining({
          size: 2048,
          manifest: resumableUpload.manifest,
          file_index: resumableUpload.file_index,
          extra_values: { experiment_ids: ['exp-1'] },
        }),
      )
    })

    it('handles getPendingUploads failure gracefully', async () => {
      mockGetPendingUploads.mockRejectedValue(new Error('Network error'))

      await flow.resumePendingUploads('run-1', 'col-1', 'org-1', 'orb-1')

      expect(flow.activeUploads.value).toHaveLength(0)
    })
  })

  describe('retryUpload', () => {
    const artifactResponse = {
      artifact: { id: 'artifact-1' },
      upload_details: { url: 'https://presigned.example.com/retry' },
    } as CreateArtifactResponse

    it.each(['create', 'post', 'upload'])(
      'preserves the original metadata after a %s failure',
      async (stage) => {
        mockArtifactsCreate.mockResolvedValue(artifactResponse)
        mockPostUploadUrl.mockResolvedValue(202)
        if (stage === 'create')
          mockArtifactsCreate.mockRejectedValueOnce(new Error('Network error'))
        if (stage === 'post')
          mockPostUploadUrl.mockRejectedValueOnce(new Error('Connection refused'))

        const event = makeUploadReadyEvent()
        flow.handleUploadReady(event)
        await vi.waitFor(() => {
          if (stage === 'upload') {
            expect(mockPostUploadUrl).toHaveBeenCalledOnce()
          } else {
            expect(flow.uploads.value.get(event.upload_id)?.status).toBe('failed')
          }
        })
        if (stage === 'upload') {
          flow.handleUploadFailed({ ...event, status: 'pending', error: 'S3 upload failed' })
        }

        await flow.retryUpload(event.upload_id)

        expect(mockArtifactsCreate).toHaveBeenLastCalledWith(
          'org-1',
          'orb-1',
          'col-1',
          expect.objectContaining({
            size: event.file_size,
            manifest: event.manifest,
            file_index: event.file_index,
            extra_values: { experiment_ids: event.experiment_ids },
          }),
        )
        expect(mockArtifactsCreate).toHaveBeenCalledTimes(2)
        expect(mockPostUploadUrl).toHaveBeenLastCalledWith(
          'run-1',
          'upload-1',
          'https://presigned.example.com/retry',
        )
      },
    )

    it('refuses to create an artifact when no upload-ready event was received', async () => {
      flow.handleUploadFailed({
        upload_id: 'upload-1',
        run_id: 'run-1',
        node_id: 'node-1',
        status: 'pending',
        error: 'Upload failed',
      })

      await flow.retryUpload('upload-1')
      await flow.retryUpload('unknown-upload')

      expect(mockArtifactsCreate).not.toHaveBeenCalled()
      expect(mockPostUploadUrl).not.toHaveBeenCalled()
      expect(flow.uploads.value.get('upload-1')?.status).toBe('failed')
    })

    it('preserves metadata when retrying a resumed upload', async () => {
      const event = makeUploadReadyEvent()
      mockGetPendingUploads.mockResolvedValue([
        {
          id: event.upload_id,
          run_id: event.run_id,
          node_id: event.node_id,
          file_size: event.file_size,
          experiment_ids: event.experiment_ids,
          manifest: event.manifest,
          file_index: event.file_index,
        } as Awaited<ReturnType<typeof api.dataAgent.getPendingUploads>>[number],
      ])
      mockArtifactsCreate.mockRejectedValueOnce(new Error('Network error'))
      await flow.resumePendingUploads('run-1', 'col-1', 'org-1', 'orb-1')
      await vi.waitFor(() => expect(flow.uploads.value.get('upload-1')?.status).toBe('failed'))
      mockArtifactsCreate.mockResolvedValue(artifactResponse)
      mockPostUploadUrl.mockResolvedValue(202)

      await flow.retryUpload('upload-1')

      expect(mockArtifactsCreate).toHaveBeenLastCalledWith(
        'org-1',
        'orb-1',
        'col-1',
        expect.objectContaining({
          size: event.file_size,
          manifest: event.manifest,
          file_index: event.file_index,
          extra_values: { experiment_ids: event.experiment_ids },
        }),
      )
    })
  })
})
