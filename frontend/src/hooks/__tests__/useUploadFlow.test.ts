import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useUploadFlow } from '@/hooks/useUploadFlow'
import type { UploadReadyEvent } from '@/lib/api/prisma/prisma.interfaces'

vi.mock('@/lib/api', () => ({
  api: {
    artifacts: {
      create: vi.fn(),
    },
    dataAgent: {
      postUploadUrl: vi.fn(),
      getPendingUploads: vi.fn(),
    },
  },
}))

import { api } from '@/lib/api'

const mockArtifactsCreate = vi.mocked(api.artifacts.create)
const mockPostUploadUrl = vi.mocked(api.dataAgent.postUploadUrl)
const mockGetPendingUploads = vi.mocked(api.dataAgent.getPendingUploads)

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
    ...overrides,
  }
}

describe('useUploadFlow', () => {
  let flow: ReturnType<typeof useUploadFlow>

  beforeEach(() => {
    vi.clearAllMocks()
    flow = useUploadFlow()
  })

  describe('handleUploadReady', () => {
    it('creates artifact and posts presigned URL to agent-backend', async () => {
      mockArtifactsCreate.mockResolvedValue({
        artifact: {} as any,
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
        artifact: {} as any,
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
        artifact: {} as any,
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
        artifact: {} as any,
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
    it('fetches pending uploads and triggers upload flow for each', async () => {
      mockGetPendingUploads.mockResolvedValue([
        {
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
        },
      ])
      mockArtifactsCreate.mockResolvedValue({
        artifact: {} as any,
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
        expect.objectContaining({ size: 2048 }),
      )
    })

    it('handles getPendingUploads failure gracefully', async () => {
      mockGetPendingUploads.mockRejectedValue(new Error('Network error'))

      await flow.resumePendingUploads('run-1', 'col-1', 'org-1', 'orb-1')

      expect(flow.activeUploads.value).toHaveLength(0)
    })
  })

  describe('retryUpload', () => {
    it('re-triggers the presigned URL flow', async () => {
      mockArtifactsCreate.mockResolvedValue({
        artifact: {} as any,
        upload_details: {
          url: 'https://presigned.example.com/retry',
          multipart: false,
          bucket_location: 'bucket',
          bucket_secret_id: 'secret',
        },
      })
      mockPostUploadUrl.mockResolvedValue(202)

      const event = makeUploadReadyEvent()
      await flow.retryUpload('upload-1', event)

      await vi.waitFor(() => {
        expect(mockPostUploadUrl).toHaveBeenCalledWith(
          'run-1',
          'upload-1',
          'https://presigned.example.com/retry',
        )
      })
    })
  })
})
