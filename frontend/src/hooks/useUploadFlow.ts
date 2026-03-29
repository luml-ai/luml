import { ref, computed } from 'vue'
import { api } from '@/lib/api'
import type {
  UploadReadyEvent,
  PendingUpload,
} from '@/lib/api/data-agent/data-agent.interfaces'
import type { CreateArtifactResponse } from '@/lib/api/artifacts/interfaces'
import { ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces'

export interface UploadEntry {
  uploadId: string
  runId: string
  nodeId: string
  status: 'pending' | 'uploading' | 'completed' | 'failed'
  error: string | null
}

export function useUploadFlow() {
  const uploads = ref<Map<string, UploadEntry>>(new Map())
  const worktreesPendingMessage = ref<string | null>(null)

  const activeUploads = computed(() => Array.from(uploads.value.values()))
  const failedUploads = computed(() =>
    Array.from(uploads.value.values()).filter((u) => u.status === 'failed'),
  )

  function _setUpload(entry: UploadEntry) {
    const next = new Map(uploads.value)
    next.set(entry.uploadId, entry)
    uploads.value = next
  }

  function _removeUpload(uploadId: string) {
    const next = new Map(uploads.value)
    next.delete(uploadId)
    uploads.value = next
  }

  async function _requestPresignedAndPost(event: UploadReadyEvent): Promise<void> {
    _setUpload({
      uploadId: event.upload_id,
      runId: event.run_id,
      nodeId: event.node_id,
      status: 'uploading',
      error: null,
    })

    let artifactResponse: CreateArtifactResponse
    try {
      artifactResponse = await api.artifacts.create(
        event.organization_id,
        event.orbit_id,
        event.collection_id,
        {
          type: ArtifactTypeEnum.model,
          name: `agent-model-${event.node_id}`,
          description: `Model from agent run ${event.run_id}, node ${event.node_id}`,
          file_name: `model-${event.node_id}.luml`,
          file_hash: '',
          size: event.file_size,
          manifest: {} as any,
          file_index: {},
          extra_values: { experiment_ids: event.experiment_ids as any },
          tags: ['agent-upload'],
        },
      )
    } catch {
      _setUpload({
        uploadId: event.upload_id,
        runId: event.run_id,
        nodeId: event.node_id,
        status: 'failed',
        error: 'Failed to create artifact on LUML backend',
      })
      return
    }

    const presignedUrl = artifactResponse.upload_details.url
    try {
      const status = await api.dataAgent.postUploadUrl(event.run_id, event.upload_id, presignedUrl)
      if (status === 409) {
        _setUpload({
          uploadId: event.upload_id,
          runId: event.run_id,
          nodeId: event.node_id,
          status: 'uploading',
          error: null,
        })
      }
    } catch {
      _setUpload({
        uploadId: event.upload_id,
        runId: event.run_id,
        nodeId: event.node_id,
        status: 'failed',
        error: 'Failed to send presigned URL to agent-backend',
      })
    }
  }

  function handleUploadReady(data: UploadReadyEvent): void {
    _setUpload({
      uploadId: data.upload_id,
      runId: data.run_id,
      nodeId: data.node_id,
      status: 'pending',
      error: null,
    })
    _requestPresignedAndPost(data)
  }

  async function handleUploadCompleted(data: {
    upload_id: string
    run_id: string
    node_id: string
  }): Promise<void> {
    _setUpload({
      uploadId: data.upload_id,
      runId: data.run_id,
      nodeId: data.node_id,
      status: 'completed',
      error: null,
    })
    setTimeout(() => _removeUpload(data.upload_id), 5000)
  }

  function handleUploadFailed(data: {
    upload_id: string
    run_id: string
    node_id: string
    error: string
    status: string
  }): void {
    _setUpload({
      uploadId: data.upload_id,
      runId: data.run_id,
      nodeId: data.node_id,
      status: 'failed',
      error: data.error,
    })
  }

  function handleWorktreesPendingUpload(data: { run_id: string; message?: string }): void {
    worktreesPendingMessage.value =
      data.message ?? 'Worktrees will be cleaned up after uploads complete'
  }

  async function retryUpload(
    uploadId: string,
    event: UploadReadyEvent,
  ): Promise<void> {
    await _requestPresignedAndPost(event)
  }

  async function resumePendingUploads(
    runId: string,
    collectionId: string,
    organizationId: string,
    orbitId: string,
  ): Promise<void> {
    let pending: PendingUpload[]
    try {
      pending = await api.dataAgent.getPendingUploads(runId)
    } catch {
      return
    }

    for (const upload of pending) {
      const event: UploadReadyEvent = {
        upload_id: upload.id,
        run_id: upload.run_id,
        node_id: upload.node_id,
        file_size: upload.file_size,
        experiment_ids: upload.experiment_ids,
        collection_id: collectionId,
        organization_id: organizationId,
        orbit_id: orbitId,
      }
      handleUploadReady(event)
    }
  }

  function handleEvent(eventType: string, data: Record<string, any>): void {
    switch (eventType) {
      case 'upload_ready':
        handleUploadReady(data as UploadReadyEvent)
        break
      case 'upload_completed':
        handleUploadCompleted(data as { upload_id: string; run_id: string; node_id: string })
        break
      case 'upload_failed':
        handleUploadFailed(
          data as {
            upload_id: string
            run_id: string
            node_id: string
            error: string
            status: string
          },
        )
        break
      case 'worktrees_pending_upload':
        handleWorktreesPendingUpload(data as { run_id: string; message?: string })
        break
    }
  }

  return {
    uploads,
    activeUploads,
    failedUploads,
    worktreesPendingMessage,
    handleEvent,
    handleUploadReady,
    handleUploadCompleted,
    handleUploadFailed,
    handleWorktreesPendingUpload,
    retryUpload,
    resumePendingUploads,
  }
}
